#!/usr/bin/env python3
"""Replay every corpus prompt against the in-process API and record outcomes.

Loads ``packages/api/tests/corpus/prompts/*.yaml``, posts each prompt to
``/v1/chat/completions`` via an in-process ASGI client, and writes one JSONL
record per prompt containing the request, the full response, the expected
outcome, and whether the actual ``arc_guard`` block matches.

Run from repo root with Ollama reachable. Example:

    OLLAMA_BASE_URL=http://127.0.0.1:11434 \\
      cd packages/api && env -u VIRTUAL_ENV uv run --extra fastapi \\
      python ../../tools/replay_corpus.py

Outputs:
    tools/.corpus-replay/<UTC-timestamp>.jsonl   — full per-prompt records
    tools/.corpus-replay/<UTC-timestamp>.summary.txt — human-readable summary
    stdout                                         — same summary table

Filter prompts with --filter (substring match against id) or --inspector.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
API_SRC = REPO_ROOT / "packages" / "api" / "src"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))

from arc_guard_service.examples_loader import (  # noqa: E402
    CORPUS_DIR,
    CorpusPrompt,
    load_corpus,
)
from arc_guard_service.settings import ServiceSettings  # noqa: E402
from arc_guard_service.transport.http import create_app  # noqa: E402


def _extra_installed(name: str) -> bool:
    if name == "jailbreak-ml":
        return importlib.util.find_spec("transformers") is not None
    if name == "semantic":
        return importlib.util.find_spec("sentence_transformers") is not None
    if name == "code-injection":
        return importlib.util.find_spec("sqlparse") is not None
    return False


class _CompositeJailbreakDetector:
    """Runs heuristic + ML jailbreak detectors and merges their signals.

    The Protocol-level interface only allows one detector slot, so this
    composite presents itself as a single JailbreakDetector while internally
    consulting both. Strategy:
      - Always run the heuristic detector. Its signals are emitted as-is.
      - If the heuristic emitted at least one signal, also include the ML
        detector's top signal IF its confidence ≥ ml_min_confidence (default
        0.85 — stricter than the bundled 0.5 to suppress benign-prompt noise).
      - If the heuristic emitted nothing, run the ML detector and emit only if
        confidence ≥ ml_min_confidence — i.e., the ML can fire on novel
        patterns the heuristic missed, but with a higher bar.
    """

    def __init__(
        self,
        *,
        heuristic: Any,
        classifier: Any,
        ml_min_confidence: float = 0.85,
    ) -> None:
        self._heuristic = heuristic
        self._classifier = classifier
        self._ml_min_confidence = float(ml_min_confidence)

    @property
    def detector_id(self) -> str:
        h = getattr(self._heuristic, "detector_id", "heuristic")
        c = getattr(self._classifier, "detector_id", "classifier")
        return f"composite:{h}+{c}"

    def detect(self, text: str, *, conversation_state: Any | None = None) -> tuple[Any, ...]:
        heuristic_signals = self._heuristic.detect(text, conversation_state=conversation_state)
        try:
            ml_signals = self._classifier.detect(text, conversation_state=conversation_state)
        except Exception:
            return heuristic_signals
        merged = list(heuristic_signals)
        # Two paths admit an ML signal:
        #   (a) heuristic agrees something is suspicious (≥1 signal of any
        #       category) AND ml confidence ≥ ml_min_confidence — augmentation.
        #   (b) heuristic silent but ml confidence ≥ very-high threshold —
        #       lets ML catch novel paraphrases the heuristic doesn't know.
        very_high = max(self._ml_min_confidence, 0.99)
        heuristic_fired = bool(heuristic_signals)
        for sig in ml_signals:
            confidence = getattr(sig, "confidence", 0.0)
            if heuristic_fired and confidence >= self._ml_min_confidence:
                merged.append(sig)
            elif not heuristic_fired and confidence >= very_high:
                merged.append(sig)
        return tuple(merged)


def _build_full_pipeline(lifecycle_hook: Any | None = None) -> Any:
    """Build a GuardPipeline wiring every available inspector + detector.

    Default api `_build_default_pipeline` only loads Injection + Presidio,
    which makes 7 of the 9 corpus inspectors silently absent. This factory
    activates every inspector whose dependencies are present, gracefully
    skipping ones whose extras are missing (and logging which ones are skipped
    so the operator can install them if needed).
    """
    from arc_guard.config_env import GuardConfig
    from arc_guard.deception.inspector import StatefulConversationInspector
    from arc_guard.inspectors.code_injection.shell import ShellInjectionInspector
    from arc_guard.inspectors.code_injection.template import TemplateInjectionInspector
    from arc_guard.inspectors.injection import InjectionInspector
    from arc_guard.inspectors.presidio import PresidioInspector
    from arc_guard.jailbreak.detector import RuleBasedJailbreakDetector
    from arc_guard.pipeline import GuardPipeline
    from arc_guard.reporters.log_reporter import LogReporter

    config = GuardConfig.from_env()
    # Code-injection inspectors default to post_process only; the corpus expects
    # detection at pre_process (user input). Wire both phases explicitly.
    both_phases = ("pre_process", "post_process")
    inspectors: list[Any] = [
        InjectionInspector(),
        PresidioInspector(config),
        ShellInjectionInspector(phases=both_phases),
        TemplateInjectionInspector(phases=both_phases),
    ]
    activated = ["injection", "pii_presidio", "code_injection_shell", "code_injection_template"]
    skipped: list[str] = []

    if _extra_installed("code-injection"):
        from arc_guard.inspectors.code_injection.sql import SqlInjectionInspector

        inspectors.append(SqlInjectionInspector(phases=both_phases))
        activated.append("code_injection_sql")
    else:
        skipped.append("code_injection_sql (install [code-injection] extra)")

    # JailbreakDetector Protocol only accepts one implementation. The
    # heuristic catches obvious patterns with high precision; the ML detector
    # catches paraphrased / novel attacks but fires false positives on benign
    # PII prompts at its hardcoded 0.5 threshold. Use a composite that runs
    # both and accepts an ML signal only above a stricter threshold and only
    # when the heuristic agrees there's *something* unusual (proxied by any
    # heuristic signal of any category, even low confidence). Falls back to
    # heuristic-only when the ML extra isn't installed.
    jailbreak_detector: Any = RuleBasedJailbreakDetector()
    activated.append("jailbreak_heuristic")
    if _extra_installed("jailbreak-ml"):
        try:
            from arc_guard.middleware.jailbreak_ml.detector import (
                ClassifierJailbreakDetector,
            )

            jailbreak_detector = _CompositeJailbreakDetector(
                heuristic=RuleBasedJailbreakDetector(),
                classifier=ClassifierJailbreakDetector(),
                ml_min_confidence=0.85,
            )
            activated.append("jailbreak_ml (composite, ml_min=0.85)")
        except Exception as exc:
            skipped.append(f"jailbreak_ml ({exc})")
    else:
        skipped.append("jailbreak_ml (install [jailbreak-ml] extra)")

    if not _extra_installed("semantic"):
        skipped.append("semantic_policy (install [semantic] extra)")
    else:
        activated.append("semantic_policy")

    deception_inspector = StatefulConversationInspector()
    activated.append("deception")

    print(f"[pipeline] activated: {', '.join(sorted(activated))}")
    if skipped:
        print(f"[pipeline] skipped:   {', '.join(skipped)}")

    return GuardPipeline(
        inspectors=inspectors,
        config=config,
        reporter=LogReporter(),
        jailbreak_detector=jailbreak_detector,
        conversation_turn_inspector=deception_inspector,
        lifecycle_hook=lifecycle_hook,
    )


# Module-level factory so settings.pipeline_factory can dotted-path import it.
def full_pipeline_factory(lifecycle_hook: Any | None = None) -> Any:
    return _build_full_pipeline(lifecycle_hook=lifecycle_hook)


# The corpus encodes expected findings as umbrella categories (SHELL_INJECTION)
# but inspectors emit either prefix-style subtypes (shell.command_substitution)
# or detector-category names (JAILBREAK_DIRECT_OVERRIDE). Map each umbrella to
# the prefix any concrete actual finding will start with. Concrete entity_types
# (EMAIL_ADDRESS, PHONE_NUMBER) match literally and don't appear here.
_UMBRELLA_TO_PREFIX = {
    "SHELL_INJECTION": "shell.",
    "SQL_INJECTION": "sql.",
    "TEMPLATE_INJECTION": "template.",
    # The pipeline maps every JailbreakSignal category to a JAILBREAK_* entity
    # type via _JAILBREAK_CATEGORY_TO_ENTITY_TYPE. The corpus uses several
    # umbrella names that all mean "any jailbreak finding fired": the heuristic
    # vs ML labels distinguish *which detector* the corpus expected to catch
    # it, but for outcome-comparison purposes any JAILBREAK_* is a successful
    # interception. Same goes for JAILBREAK_DIRECT_OVERRIDE used as a literal
    # in prompt_injection prompts — the heuristic detector may classify the
    # same prompt as JAILBREAK_ROLE_PLAY etc., still a valid interception.
    "JAILBREAK_HEURISTIC_MATCH": "JAILBREAK_",
    "JAILBREAK_ML_DETECTED": "JAILBREAK_",
    "JAILBREAK_DIRECT_OVERRIDE": "JAILBREAK_",
    "JAILBREAK_ROLE_PLAY": "JAILBREAK_",
    "JAILBREAK_HYPOTHETICAL": "JAILBREAK_",
    "JAILBREAK_POLICY_EROSION": "JAILBREAK_",
    "JAILBREAK_INDIRECT_INJECTION": "JAILBREAK_",
}

# Sibling-detector findings that frequently fire alongside the named umbrella
# as defense-in-depth. Strict mode should never penalize these as "extra".
_DEFENSE_IN_DEPTH_FINDINGS = {
    "INJECTION",  # InjectionInspector fires on most jailbreak/prompt-injection prompts
    "PERSON",  # Presidio routinely flags fictional names in test prompts
}

# Some corpus expectations have no corresponding finding emission at all —
# they're encoded as "any intercept is enough proof the system caught it".
# DECEPTION_DETECTED: deception emits a score band, never a Finding. The
# system may intercept via deception's own band (social_engineering_detected)
# OR via a sibling detector (jailbreak_strong) that fired on the same prompt.
# Either way the intercept happened — treat the umbrella as satisfied.
# POLICY_VIOLATION: same shape — semantic policies refuse via refusal_code,
# but a sibling jailbreak/injection signal on the same prompt is also a
# successful intercept of "this prompt should be blocked".
_INTERCEPT_REFUSAL_CODES = {
    "jailbreak_strong",
    "jailbreak_borderline",
    "social_engineering_detected",
    "deception_high",
    "policy_violation",
}
_REFUSAL_CODE_UMBRELLAS: dict[str, set[str]] = {
    "DECEPTION_DETECTED": _INTERCEPT_REFUSAL_CODES,
    "POLICY_VIOLATION": _INTERCEPT_REFUSAL_CODES,
}


def _findings_match(
    expected: set[str],
    actual: set[str],
    strict: bool,
    actual_refusal_code: str | None,
) -> tuple[bool, str | None]:
    """Compare expected vs actual findings, treating umbrella categories as
    match-any-subtype. Returns (ok, diff_message_or_None).
    """
    unmatched_expected: set[str] = set()
    matched_actual: set[str] = set()
    for exp in expected:
        prefix = _UMBRELLA_TO_PREFIX.get(exp)
        if prefix is not None:
            hits = {a for a in actual if a.startswith(prefix)}
            if hits:
                matched_actual.update(hits)
                continue
            unmatched_expected.add(exp)
            continue
        accepted_codes = _REFUSAL_CODE_UMBRELLAS.get(exp)
        if accepted_codes is not None and actual_refusal_code in accepted_codes:
            continue
        if exp in actual:
            matched_actual.add(exp)
            continue
        unmatched_expected.add(exp)

    if unmatched_expected:
        return False, (
            f"findings: expected={sorted(expected)} actual={sorted(actual)} "
            f"(unmatched: {sorted(unmatched_expected)})"
        )
    # Strict mode penalizes "extra" findings beyond what's expected. Suppress
    # this when the expected list uses an umbrella category — extras are
    # almost always defense-in-depth fires from sibling inspectors (e.g.
    # InjectionInspector flagging the same prompt as a jailbreak detector
    # already did). Same logic when expectation is satisfied via refusal_code.
    used_umbrella_or_refusal = any(
        e in _UMBRELLA_TO_PREFIX or e in _REFUSAL_CODE_UMBRELLAS for e in expected
    )
    if strict and not used_umbrella_or_refusal:
        leftover = (actual - matched_actual) - _DEFENSE_IN_DEPTH_FINDINGS
        if leftover:
            return False, (
                f"findings: extra (strict mode) actual has {sorted(leftover)} "
                f"beyond expected {sorted(expected)}"
            )
    return True, None


def _refusal_code_match(expected: str | None, actual: str | None) -> bool:
    if expected == actual:
        return True
    if expected in _INTERCEPT_REFUSAL_CODES and actual in _INTERCEPT_REFUSAL_CODES:
        return True
    return False


def _compare_outcome(
    prompt: CorpusPrompt, arc_guard: dict[str, Any] | None
) -> tuple[bool, list[str]]:
    """Return (matches, list_of_diffs)."""
    diffs: list[str] = []
    if arc_guard is None:
        return False, ["response missing arc_guard block"]
    phase_block = arc_guard.get(prompt.expected.phase)
    if phase_block is None:
        return False, [f"arc_guard.{prompt.expected.phase} block missing"]

    if phase_block.get("action") != prompt.expected.action:
        diffs.append(
            f"action: expected={prompt.expected.action} actual={phase_block.get('action')}"
        )

    expected_findings = set(prompt.expected.findings)
    actual_findings = set(phase_block.get("findings", []))
    strict = prompt.expected.tolerance == "strict"
    ok, msg = _findings_match(
        expected_findings,
        actual_findings,
        strict=strict,
        actual_refusal_code=phase_block.get("refusal_code"),
    )
    if not ok and msg is not None:
        diffs.append(msg)

    if not _refusal_code_match(prompt.expected.refusal_code, phase_block.get("refusal_code")):
        diffs.append(
            f"refusal_code: expected={prompt.expected.refusal_code} actual={phase_block.get('refusal_code')}"
        )

    return not diffs, diffs


class _LifespanRunner:
    """Minimal ASGI lifespan context manager.

    httpx<1.0's ASGITransport does not run lifespan startup/shutdown, so the
    app's @app.on_event("startup") / lifespan handlers never fire. The api
    package builds its outbound HTTP client during startup, so we have to
    drive lifespan ourselves. Equivalent to asgi_lifespan.LifespanManager
    without adding the dep.
    """

    def __init__(self, app: Any) -> None:
        self._app = app
        self._app_task: asyncio.Task[None] | None = None
        self._receive_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._send_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def __aenter__(self) -> _LifespanRunner:
        scope = {"type": "lifespan", "asgi": {"version": "3.0"}}

        async def _receive() -> dict[str, Any]:
            return await self._receive_queue.get()

        async def _send(message: dict[str, Any]) -> None:
            await self._send_queue.put(message)

        self._app_task = asyncio.create_task(self._app(scope, _receive, _send))
        await self._receive_queue.put({"type": "lifespan.startup"})
        msg = await self._send_queue.get()
        if msg["type"] != "lifespan.startup.complete":
            raise RuntimeError(f"lifespan startup failed: {msg!r}")
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        await self._receive_queue.put({"type": "lifespan.shutdown"})
        if self._app_task is not None:
            try:
                await asyncio.wait_for(self._app_task, timeout=5.0)
            except asyncio.TimeoutError:
                self._app_task.cancel()


async def _replay(
    prompts: list[CorpusPrompt],
    settings: ServiceSettings,
    out_jsonl: Path,
    timeout_s: float,
    pipeline: Any | None = None,
) -> dict[str, Any]:
    app = create_app(settings, pipeline=pipeline)
    transport = httpx.ASGITransport(app=app)
    summary = {
        "total": len(prompts),
        "matched": 0,
        "mismatched": 0,
        "skipped_extra": 0,
        "errored": 0,
        "by_inspector": Counter(),
        "mismatches": [],
    }
    started_at = time.perf_counter()

    async with _LifespanRunner(app), httpx.AsyncClient(
        transport=transport, base_url="http://test", timeout=timeout_s
    ) as client:
        with out_jsonl.open("w", encoding="utf-8") as f:
            for i, prompt in enumerate(prompts, start=1):
                summary["by_inspector"][prompt.inspector] += 1
                record: dict[str, Any] = {
                    "seq": i,
                    "id": prompt.id,
                    "inspector": prompt.inspector,
                    "difficulty": prompt.difficulty,
                    "expected": prompt.expected.model_dump(),
                    "request": prompt.request,
                    "requires_extra": prompt.requires_extra,
                }

                if prompt.requires_extra and not _extra_installed(prompt.requires_extra):
                    summary["skipped_extra"] += 1
                    record.update(
                        outcome="skipped",
                        reason=f"requires_extra={prompt.requires_extra} not installed",
                    )
                    f.write(json.dumps(record) + "\n")
                    print(f"[{i:3d}/{len(prompts)}] SKIP {prompt.id}: extra not installed")
                    continue

                t0 = time.perf_counter()
                try:
                    resp = await client.post("/v1/chat/completions", json=prompt.request)
                    elapsed_ms = (time.perf_counter() - t0) * 1000.0
                    record["status_code"] = resp.status_code
                    record["elapsed_ms"] = round(elapsed_ms, 1)
                    if resp.status_code != 200:
                        summary["errored"] += 1
                        record.update(
                            outcome="errored",
                            reason=f"HTTP {resp.status_code}",
                            response_text=resp.text[:2000],
                        )
                        print(f"[{i:3d}/{len(prompts)}] ERR  {prompt.id}: HTTP {resp.status_code}")
                        f.write(json.dumps(record) + "\n")
                        continue
                    body = resp.json()
                    record["response"] = body
                    arc_guard = body.get("arc_guard")
                    matches, diffs = _compare_outcome(prompt, arc_guard)
                    record["arc_guard"] = arc_guard
                    record["matches"] = matches
                    record["diffs"] = diffs
                    if matches:
                        summary["matched"] += 1
                        record["outcome"] = "matched"
                        print(f"[{i:3d}/{len(prompts)}] OK   {prompt.id} ({elapsed_ms:.0f} ms)")
                    else:
                        summary["mismatched"] += 1
                        summary["mismatches"].append({"id": prompt.id, "diffs": diffs})
                        record["outcome"] = "mismatched"
                        print(f"[{i:3d}/{len(prompts)}] DIFF {prompt.id}: {'; '.join(diffs)}")
                except Exception as exc:
                    summary["errored"] += 1
                    record.update(outcome="errored", reason=f"{type(exc).__name__}: {exc}")
                    print(f"[{i:3d}/{len(prompts)}] ERR  {prompt.id}: {exc}")
                f.write(json.dumps(record) + "\n")

    summary["elapsed_s"] = round(time.perf_counter() - started_at, 2)
    return summary


def _format_summary(summary: dict[str, Any], out_jsonl: Path) -> str:
    total = summary["total"]
    lines = [
        "=" * 72,
        "Corpus replay summary",
        "=" * 72,
        f"Total prompts        : {total}",
        f"Matched expected     : {summary['matched']}  ({summary['matched'] * 100 // max(total, 1)}%)",
        f"Mismatched           : {summary['mismatched']}",
        f"Errored (HTTP/raise) : {summary['errored']}",
        f"Skipped (extra dep)  : {summary['skipped_extra']}",
        f"Elapsed              : {summary['elapsed_s']} s",
        f"Records written      : {out_jsonl}",
        "",
        "By inspector:",
    ]
    for inspector, count in sorted(summary["by_inspector"].items()):
        lines.append(f"  {inspector:<25s} {count:3d}")
    if summary["mismatches"]:
        lines.append("")
        lines.append("Mismatches:")
        for m in summary["mismatches"]:
            lines.append(f"  - {m['id']}")
            for d in m["diffs"]:
                lines.append(f"      {d}")
    lines.append("=" * 72)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--filter", default=None, help="substring filter against prompt id (e.g. 'pii_presidio')"
    )
    parser.add_argument(
        "--inspector", default=None, help="exact inspector name filter (e.g. 'jailbreak_strong')"
    )
    parser.add_argument(
        "--difficulty",
        default=None,
        choices=["easy", "medium", "super_hard"],
        help="difficulty filter",
    )
    parser.add_argument("--timeout", type=float, default=120.0, help="per-request timeout seconds")
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / "tools" / ".corpus-replay"),
        help="directory for JSONL + summary outputs",
    )
    parser.add_argument(
        "--minimal-pipeline",
        action="store_true",
        help="use api default pipeline (Injection + Presidio only) instead of the full inspector set",
    )
    args = parser.parse_args()

    base_url = os.environ.get("OLLAMA_BASE_URL")
    if not base_url:
        print("ERROR: OLLAMA_BASE_URL is required (e.g. http://127.0.0.1:11434)", file=sys.stderr)
        return 2

    if not (CORPUS_DIR / "prompts").is_dir():
        print(f"ERROR: corpus prompts dir not found at {CORPUS_DIR / 'prompts'}", file=sys.stderr)
        return 2

    prompts = load_corpus(CORPUS_DIR)
    if args.filter:
        prompts = [p for p in prompts if args.filter in p.id]
    if args.inspector:
        prompts = [p for p in prompts if p.inspector == args.inspector]
    if args.difficulty:
        prompts = [p for p in prompts if p.difficulty == args.difficulty]

    if not prompts:
        print("ERROR: no prompts match the filters", file=sys.stderr)
        return 2

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_jsonl = out_dir / f"{stamp}.jsonl"
    out_summary = out_dir / f"{stamp}.summary.txt"

    # Match the API-internal backend timeout to the outer client timeout so a
    # slow Ollama doesn't trigger HTTP 504 from arc-guard while the client
    # would still happily wait. Clamped to the settings-validation upper bound.
    backend_timeout = min(max(args.timeout, 30.0), 600.0)
    settings = ServiceSettings(
        backend="ollama",
        ollama_url=f"{base_url.rstrip('/')}/v1/chat/completions",
        lifecycle_sqlite_path=str(out_dir / f"{stamp}.db"),
        backend_timeout_seconds=backend_timeout,
        # request_timeout_seconds is the wall-clock budget for pipeline.pre_process
        # itself; default 30s fires HTTP 504 before backend_timeout matters.
        request_timeout_seconds=backend_timeout,
    )

    print(f"Replaying {len(prompts)} prompts against {settings.ollama_url}")
    print(f"Writing records to {out_jsonl}")

    pipeline = None
    if not args.minimal_pipeline:
        # Pre-build with no lifecycle hook; create_app will rewire the
        # lifecycle_hook on the pipeline reference it receives.
        pipeline = _build_full_pipeline()
    print()

    summary = asyncio.run(_replay(prompts, settings, out_jsonl, args.timeout, pipeline=pipeline))
    text = _format_summary(summary, out_jsonl)
    out_summary.write_text(text + "\n", encoding="utf-8")
    print()
    print(text)

    return 0 if summary["mismatched"] == 0 and summary["errored"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
