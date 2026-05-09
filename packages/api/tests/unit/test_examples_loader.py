import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from arc_guard_service.examples_loader import (
    CorpusError,
    CorpusPrompt,
    ExpectedOutcome,
    load_corpus,
    to_openapi_examples,
)


def test_expected_outcome_block_requires_refusal_code():
    with pytest.raises(ValidationError, match="refusal_code"):
        ExpectedOutcome(
            action="block",
            phase="pre_process",
            refusal_code=None,
            findings=["JAILBREAK_DIRECT_OVERRIDE"],
        )


def test_expected_outcome_non_block_must_have_null_refusal_code():
    with pytest.raises(ValidationError, match="refusal_code"):
        ExpectedOutcome(
            action="redact",
            phase="pre_process",
            refusal_code="something",
            findings=["EMAIL_ADDRESS"],
        )


def test_expected_outcome_pre_process_default_tolerance_is_strict():
    eo = ExpectedOutcome(
        action="redact", phase="pre_process", refusal_code=None, findings=["EMAIL_ADDRESS"]
    )
    assert eo.tolerance == "strict"


def test_expected_outcome_post_process_default_tolerance_is_subset():
    eo = ExpectedOutcome(
        action="redact", phase="post_process", refusal_code=None, findings=[]
    )
    assert eo.tolerance == "subset"


def _valid_prompt_dict() -> dict:
    return {
        "id": "pii_presidio__easy__01",
        "inspector": "pii_presidio",
        "difficulty": "easy",
        "swagger_summary": "PII (email)",
        "swagger_description": "Plain user message containing one email.",
        "request": {
            "model": "llama3.2",
            "messages": [{"role": "user", "content": "alice@arc-corp.test"}],
        },
        "expected": {
            "action": "redact",
            "phase": "pre_process",
            "refusal_code": None,
            "findings": ["EMAIL_ADDRESS"],
        },
    }


def test_corpus_prompt_round_trip():
    p = CorpusPrompt.model_validate(_valid_prompt_dict())
    assert p.id == "pii_presidio__easy__01"
    assert p.expected.tolerance == "strict"
    assert p.tags == []
    assert p.requires_extra is None


def test_corpus_prompt_difficulty_enum():
    bad = _valid_prompt_dict()
    bad["difficulty"] = "trivial"
    with pytest.raises(ValidationError):
        CorpusPrompt.model_validate(bad)


def test_corpus_prompt_request_must_be_valid_chat_completion_request():
    bad = _valid_prompt_dict()
    bad["request"] = {"model": "llama3.2"}  # no messages
    with pytest.raises(ValidationError, match="messages"):
        CorpusPrompt.model_validate(bad)


def _write_yaml(tmp_path: Path, name: str, body: str) -> Path:
    prompts = tmp_path / "prompts"
    prompts.mkdir(parents=True, exist_ok=True)
    f = prompts / name
    f.write_text(body)
    return f


def _yaml_for(prompt_id: str) -> str:
    inspector, difficulty, _ = prompt_id.split("__")
    return f"""
id: {prompt_id}
inspector: {inspector}
difficulty: {difficulty}
swagger_summary: "test"
swagger_description: "test"
request:
  model: llama3.2
  messages:
    - role: user
      content: "alice@arc-corp.test"
expected:
  action: redact
  phase: pre_process
  refusal_code: null
  findings: [EMAIL_ADDRESS]
""".strip()


def test_load_corpus_returns_sorted_prompts(tmp_path):
    _write_yaml(tmp_path, "pii_presidio__easy__02.yaml", _yaml_for("pii_presidio__easy__02"))
    _write_yaml(tmp_path, "pii_presidio__easy__01.yaml", _yaml_for("pii_presidio__easy__01"))
    prompts = load_corpus(tmp_path)
    assert [p.id for p in prompts] == ["pii_presidio__easy__01", "pii_presidio__easy__02"]


def test_load_corpus_fail_fast_on_malformed_yaml(tmp_path):
    _write_yaml(tmp_path, "pii_presidio__easy__01.yaml", "id: pii_presidio__easy__01\n  bad: indent")
    with pytest.raises(CorpusError, match="pii_presidio__easy__01.yaml"):
        load_corpus(tmp_path)


def test_load_corpus_fail_fast_on_id_filename_mismatch(tmp_path):
    _write_yaml(tmp_path, "pii_presidio__easy__01.yaml", _yaml_for("pii_presidio__easy__99"))
    with pytest.raises(CorpusError, match="filename stem"):
        load_corpus(tmp_path)


def _yaml_for_super_hard(prompt_id: str, *, false_positive: bool) -> str:
    return f"""
id: {prompt_id}
inspector: pii_presidio
difficulty: super_hard
swagger_summary: "test"
swagger_description: "test"
request:
  model: llama3.2
  messages:
    - role: user
      content: "test"
expected:
  action: pass
  phase: pre_process
  refusal_code: null
  findings: []
  false_positive: {str(false_positive).lower()}
""".strip()


def test_load_corpus_rejects_gap_in_numbering(tmp_path):
    for n in (1, 2, 4):
        nm = f"pii_presidio__easy__{n:02d}"
        _write_yaml(tmp_path, f"{nm}.yaml", _yaml_for(nm))
    with pytest.raises(CorpusError, match=r"gap in numbering"):
        load_corpus(tmp_path)


def test_load_corpus_super_hard_requires_exactly_two_false_positive(tmp_path):
    for n in range(1, 6):
        nm = f"pii_presidio__super_hard__{n:02d}"
        _write_yaml(tmp_path, f"{nm}.yaml", _yaml_for_super_hard(nm, false_positive=False))
    with pytest.raises(CorpusError, match=r"exactly two false_positive"):
        load_corpus(tmp_path)


def test_to_openapi_examples_shape_and_description_appends_expected_block():
    p = CorpusPrompt.model_validate(_valid_prompt_dict())
    out = to_openapi_examples([p])
    assert "pii_presidio__easy__01" in out
    entry = out["pii_presidio__easy__01"]
    assert entry["summary"] == "PII (email)"
    assert "**Expected SDK behavior:**" in entry["description"]
    assert "redact" in entry["description"]
    assert "EMAIL_ADDRESS" in entry["description"]
    assert entry["value"] == p.request


def test_module_level_constants_resolve():
    from arc_guard_service import examples_loader
    assert examples_loader.CORPUS_DIR.name == "corpus"
    assert examples_loader.CORPUS_DIR.parent.name == "tests"
    assert examples_loader.CORPUS_DIR.parent.parent.name == "api"
    assert callable(examples_loader._load_openapi_examples)


def test_cli_validate_succeeds_on_empty_corpus(tmp_path, monkeypatch):
    (tmp_path / "prompts").mkdir()
    monkeypatch.setenv("ARC_GUARD_CORPUS_DIR", str(tmp_path))
    result = subprocess.run(
        [sys.executable, "-m", "arc_guard_service.examples_loader", "--validate"],
        capture_output=True, text=True,
        env={**__import__("os").environ, "ARC_GUARD_CORPUS_DIR": str(tmp_path)},
    )
    assert result.returncode == 0, result.stderr
    assert "OK: 0 prompts" in result.stdout


def test_cli_stats_prints_matrix(tmp_path, monkeypatch):
    _write_yaml(tmp_path, "pii_presidio__easy__01.yaml", _yaml_for("pii_presidio__easy__01"))
    monkeypatch.setenv("ARC_GUARD_CORPUS_DIR", str(tmp_path))
    result = subprocess.run(
        [sys.executable, "-m", "arc_guard_service.examples_loader", "--stats"],
        capture_output=True, text=True,
        env={**__import__("os").environ, "ARC_GUARD_CORPUS_DIR": str(tmp_path)},
    )
    assert result.returncode == 0, result.stderr
    assert "pii_presidio" in result.stdout
    assert "easy" in result.stdout
