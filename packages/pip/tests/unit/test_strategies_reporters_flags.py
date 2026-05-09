from __future__ import annotations

import logging
from pathlib import Path

import pytest
from arc_guard_core.types import Finding, GuardResult, RiskLevel

from arc_guard.flags.env_provider import EnvFlagProvider
from arc_guard.flags.static_provider import StaticFlagProvider
from arc_guard.reporters.log_reporter import LogReporter
from arc_guard.reporters.null_reporter import NullReporter
from arc_guard.strategies.block import BlockStrategy
from arc_guard.strategies.hash import HashStrategy
from arc_guard.strategies.redact import RedactStrategy

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _finding(
    entity_type: str,
    start: int,
    end: int,
    risk: RiskLevel = RiskLevel.MEDIUM,
) -> Finding:
    return Finding(
        entity_type=entity_type,
        start=start,
        end=end,
        risk_level=risk,
        inspector="test",
    )


def _result(findings: tuple[Finding, ...] = (), action: str = "pass") -> GuardResult:  # type: ignore[assignment]
    return GuardResult(text="hello", action=action, findings=findings)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# RedactStrategy
# ---------------------------------------------------------------------------


class TestRedactStrategy:
    def test_no_findings_returns_text_unchanged(self) -> None:
        strategy = RedactStrategy()
        text = "hello world"
        result, decisions = strategy.apply(text, ())
        assert result == text
        assert strategy.name == "redact"

    def test_single_finding_replaced(self) -> None:
        strategy = RedactStrategy()
        text = "Call 4111111111111111 now"
        f = _finding("CREDIT_CARD", 5, 21)
        result, decisions = strategy.apply(text, (f,))
        assert result == "Call [CREDIT_CARD] now"
        assert strategy.name == "redact"

    def test_multiple_non_overlapping_findings(self) -> None:
        strategy = RedactStrategy()
        text = "Name: Alice, SSN: 123-45-6789"
        findings = (
            _finding("PERSON", 6, 11),
            _finding("US_SSN", 18, 29),
        )
        result, decisions = strategy.apply(text, findings)
        assert "[PERSON]" in result
        assert "[US_SSN]" in result
        assert strategy.name == "redact"

    def test_overlapping_findings_handled_right_to_left(self) -> None:
        # Overlapping: outer span [0:10], inner span [2:5]
        # Sorted descending by start: first replace [2:5], then [0:10]
        # After replacing [2:5] the text shifts, but we handle right-to-left
        strategy = RedactStrategy()
        text = "0123456789"
        findings = (
            _finding("OUTER", 0, 10),
            _finding("INNER", 2, 5),
        )
        result, decisions = strategy.apply(text, findings)
        # Right-to-left: INNER (start=2) replaced first, then OUTER (start=0)
        # After INNER: "01[INNER]56789" — but then OUTER replaces [0:10] in ORIGINAL text
        # Since we do right-to-left on ORIGINAL text, OUTER replaces original [0:10]
        # which overlaps. The net effect: OUTER replaces the whole original span.
        assert strategy.name == "redact"
        assert "[OUTER]" in result

    def test_entity_type_used_as_placeholder(self) -> None:
        strategy = RedactStrategy()
        text = "secret"
        f = _finding("MY_CUSTOM_ENTITY", 0, 6)
        result, _ = strategy.apply(text, (f,))
        assert result == "[MY_CUSTOM_ENTITY]"


# ---------------------------------------------------------------------------
# HashStrategy
# ---------------------------------------------------------------------------


class TestHashStrategy:
    def test_no_findings_returns_text_unchanged(self) -> None:
        strategy = HashStrategy()
        text = "hello"
        result, decisions = strategy.apply(text, ())
        assert result == text
        assert strategy.name == "hash"

    def test_single_finding_replaced_with_hex_digest(self) -> None:
        strategy = HashStrategy()
        text = "secret data here"
        f = _finding("SECRET", 0, 6)
        result, decisions = strategy.apply(text, (f,))
        assert strategy.name == "hash"
        # The hash strategy now emits `[HASH:<8hex>]`
        replaced_token = result.split(" ")[0]
        assert replaced_token.startswith("[HASH:")
        assert replaced_token.endswith("]")
        digest_part = replaced_token[len("[HASH:") : -1]
        assert len(digest_part) == 8
        assert all(c in "0123456789abcdef" for c in digest_part)

    def test_same_span_produces_same_hash(self) -> None:
        strategy = HashStrategy()
        text = "hello world"
        f = _finding("WORD", 0, 5)
        result1, _ = strategy.apply(text, (f,))
        result2, _ = strategy.apply(text, (f,))
        assert result1 == result2

    def test_key_loaded_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import hashlib
        import hmac

        key = b"\x01" * 32
        monkeypatch.setenv("GUARD_HASH_KEY", key.hex())
        strategy = HashStrategy()
        text = "abc"
        f = _finding("X", 0, 3)
        result, _ = strategy.apply(text, (f,))
        expected_digest = hmac.new(key, b"abc", hashlib.sha256).hexdigest()[:8]
        assert result == f"[HASH:{expected_digest}]"

    def test_key_auto_generated_and_written_to_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        key_file = tmp_path / "guard_hash_key"
        monkeypatch.delenv("GUARD_HASH_KEY", raising=False)
        monkeypatch.setenv("GUARD_HASH_KEY_FILE", str(key_file))
        HashStrategy()
        assert key_file.exists()
        # The key file should contain valid hex for 32 bytes (64 chars)
        assert len(key_file.read_text().strip()) == 64

    def test_key_read_from_file(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        import hashlib
        import hmac

        key = b"\xde\xad\xbe\xef" * 8
        key_file = tmp_path / "guard_hash_key"
        key_file.write_text(key.hex())
        monkeypatch.delenv("GUARD_HASH_KEY", raising=False)
        monkeypatch.setenv("GUARD_HASH_KEY_FILE", str(key_file))
        strategy = HashStrategy()
        text = "test"
        f = _finding("X", 0, 4)
        result, _ = strategy.apply(text, (f,))
        expected_digest = hmac.new(key, b"test", hashlib.sha256).hexdigest()[:8]
        assert result == f"[HASH:{expected_digest}]"

    def test_key_never_logged(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        key_file = tmp_path / "guard_hash_key"
        monkeypatch.delenv("GUARD_HASH_KEY", raising=False)
        monkeypatch.setenv("GUARD_HASH_KEY_FILE", str(key_file))
        with caplog.at_level(logging.INFO, logger="arc_guard"):
            HashStrategy()
        key_hex = key_file.read_text().strip()
        for record in caplog.records:
            assert key_hex not in record.getMessage()


# ---------------------------------------------------------------------------
# BlockStrategy
# ---------------------------------------------------------------------------


class TestBlockStrategy:
    def test_always_returns_empty_string(self) -> None:
        strategy = BlockStrategy()
        result, decisions = strategy.apply("anything", ())
        assert result == ""
        assert strategy.name == "block"

    def test_ignores_findings(self) -> None:
        strategy = BlockStrategy()
        findings = (_finding("X", 0, 3),)
        result, decisions = strategy.apply("abc", findings)
        assert result == ""
        assert strategy.name == "block"

    def test_ignores_text_content(self) -> None:
        strategy = BlockStrategy()
        result, _ = strategy.apply("VERY LONG TEXT " * 100, ())
        assert result == ""


# ---------------------------------------------------------------------------
# LogReporter
# ---------------------------------------------------------------------------


class TestLogReporter:
    async def test_no_log_when_clean(self, caplog: pytest.LogCaptureFixture) -> None:
        reporter = LogReporter()
        with caplog.at_level(logging.WARNING, logger="arc_guard"):
            await reporter.report(_result(findings=()))
        assert caplog.records == []

    async def test_logs_warning_when_findings_present(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        reporter = LogReporter()
        findings = (_finding("CREDIT_CARD", 0, 4, RiskLevel.HIGH),)
        result = GuardResult(text="", action="redact", findings=findings)
        with caplog.at_level(logging.WARNING, logger="arc_guard"):
            await reporter.report(result)
        assert len(caplog.records) == 1
        msg = caplog.records[0].getMessage()
        assert "redact" in msg
        assert "1" in msg
        assert "HIGH" in msg

    async def test_never_raises(self) -> None:
        reporter = LogReporter()
        # Even with a mangled result object, report() must not raise
        result = GuardResult(text="x", action="pass", findings=())
        await reporter.report(result)  # should not raise


# ---------------------------------------------------------------------------
# NullReporter
# ---------------------------------------------------------------------------


class TestNullReporter:
    async def test_does_nothing(self) -> None:
        reporter = NullReporter()
        result = _result(findings=(_finding("X", 0, 1),))
        await reporter.report(result)  # no assertion needed — must not raise or log

    async def test_satisfies_reporter_protocol(self) -> None:
        from arc_guard_core.protocols.reporter import Reporter

        reporter = NullReporter()
        assert isinstance(reporter, Reporter)


# ---------------------------------------------------------------------------
# Removed during the package trim — see CHANGELOG and the pyproject comment.
# WebhookReporter (httpx-based) is gone; reintroduction is a future task.
# ---------------------------------------------------------------------------


def test_webhook_reporter_removed_in_spec_002() -> None:
    with pytest.raises(ModuleNotFoundError):
        import arc_guard.reporters.webhook_reporter  # noqa: F401


# ---------------------------------------------------------------------------
# StaticFlagProvider
# ---------------------------------------------------------------------------


class TestStaticFlagProvider:
    def test_is_enabled_bool_true(self) -> None:
        p = StaticFlagProvider({"enabled": True})
        assert p.is_enabled("enabled") is True

    def test_is_enabled_bool_false(self) -> None:
        p = StaticFlagProvider({"enabled": False})
        assert p.is_enabled("enabled") is False

    def test_is_enabled_string_true_variants(self) -> None:
        for val in ("true", "True", "TRUE", "1", "yes", "YES"):
            p = StaticFlagProvider({"flag": val})
            assert p.is_enabled("flag") is True, f"Expected True for {val!r}"

    def test_is_enabled_string_false(self) -> None:
        p = StaticFlagProvider({"flag": "false"})
        assert p.is_enabled("flag") is False

    def test_is_enabled_missing_returns_default(self) -> None:
        p = StaticFlagProvider({})
        assert p.is_enabled("missing") is False
        assert p.is_enabled("missing", default=True) is True

    def test_get_string_returns_value(self) -> None:
        p = StaticFlagProvider({"strategy": "hash"})
        assert p.get_string("strategy") == "hash"

    def test_get_string_missing_returns_default(self) -> None:
        p = StaticFlagProvider({})
        assert p.get_string("missing") == ""
        assert p.get_string("missing", default="redact") == "redact"

    def test_get_list_from_list(self) -> None:
        p = StaticFlagProvider({"items": ["a", "b", "c"]})
        assert p.get_list("items") == ["a", "b", "c"]

    def test_get_list_from_string_csv(self) -> None:
        p = StaticFlagProvider({"items": "a,b, c"})
        assert p.get_list("items") == ["a", "b", "c"]

    def test_get_list_missing_returns_default(self) -> None:
        p = StaticFlagProvider({})
        assert p.get_list("missing") == []
        assert p.get_list("missing", default=["x"]) == ["x"]

    def test_satisfies_flag_provider_protocol(self) -> None:
        from arc_guard_core.protocols.flag_provider import FlagProvider

        p = StaticFlagProvider({})
        assert isinstance(p, FlagProvider)


# ---------------------------------------------------------------------------
# EnvFlagProvider
# ---------------------------------------------------------------------------


class TestEnvFlagProvider:
    def test_is_enabled_reads_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GUARD_ENABLED", "true")
        p = EnvFlagProvider()
        assert p.is_enabled("enabled") is True

    def test_is_enabled_false_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GUARD_ENABLED", "false")
        p = EnvFlagProvider()
        assert p.is_enabled("enabled") is False

    def test_is_enabled_missing_returns_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GUARD_MISSING", raising=False)
        p = EnvFlagProvider()
        assert p.is_enabled("missing") is False
        assert p.is_enabled("missing", default=True) is True

    def test_custom_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_FLAG", "1")
        p = EnvFlagProvider(prefix="MY_")
        assert p.is_enabled("flag") is True

    def test_get_string_reads_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GUARD_ACTION_STRATEGY", "hash")
        p = EnvFlagProvider()
        assert p.get_string("action_strategy") == "hash"

    def test_get_string_missing_returns_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GUARD_MISSING", raising=False)
        p = EnvFlagProvider()
        assert p.get_string("missing", default="redact") == "redact"

    def test_get_list_splits_on_comma(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GUARD_ITEMS", "a,b, c")
        p = EnvFlagProvider()
        assert p.get_list("items") == ["a", "b", "c"]

    def test_get_list_missing_returns_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GUARD_ITEMS", raising=False)
        p = EnvFlagProvider()
        assert p.get_list("items") == []
        assert p.get_list("items", default=["x"]) == ["x"]

    def test_satisfies_flag_provider_protocol(self) -> None:
        from arc_guard_core.protocols.flag_provider import FlagProvider

        p = EnvFlagProvider()
        assert isinstance(p, FlagProvider)
