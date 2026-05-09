import pytest
from pydantic import ValidationError

from arc_guard_service.examples_loader import ExpectedOutcome


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


from arc_guard_service.examples_loader import CorpusPrompt


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


from pathlib import Path

from arc_guard_service.examples_loader import CorpusError, load_corpus


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
