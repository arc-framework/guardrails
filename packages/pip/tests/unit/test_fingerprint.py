"""Unit tests for the code-injection fingerprint helper."""

from __future__ import annotations

import string

from arc_guard.inspectors.code_injection import compute_fingerprint


def _bucket_sum(fingerprint: dict[str, object]) -> int:
    bucket = fingerprint["char_class"]
    assert isinstance(bucket, dict)
    return sum(int(v) for v in bucket.values())


def test_hash_is_stable_across_calls() -> None:
    a = compute_fingerprint("DROP TABLE users")
    b = compute_fingerprint("DROP TABLE users")
    assert a["hash"] == b["hash"]
    assert a["hash"].startswith("sha256:")


def test_hash_differs_on_different_inputs() -> None:
    assert compute_fingerprint("a")["hash"] != compute_fingerprint("b")["hash"]


def test_length_chars_vs_length_bytes_diverge_on_unicode() -> None:
    fp = compute_fingerprint("héllo")
    assert fp["length_chars"] == 5
    assert fp["length_bytes"] == 6


def test_length_chars_equals_length_bytes_for_ascii() -> None:
    fp = compute_fingerprint("hello world")
    assert fp["length_chars"] == fp["length_bytes"] == 11


def test_char_class_buckets_are_mutually_exclusive_and_sum_to_length() -> None:
    sample = "Hello, world! 123\n\t" + string.punctuation
    fp = compute_fingerprint(sample)
    assert _bucket_sum(fp) == len(sample)


def test_alpha_bucket_covers_unicode_letters() -> None:
    fp = compute_fingerprint("héllo")
    assert fp["char_class"]["alpha"] == 5
    assert fp["char_class"]["digit"] == 0
    assert fp["char_class"]["punct"] == 0


def test_digit_bucket_counts_only_digits() -> None:
    fp = compute_fingerprint("abc123")
    assert fp["char_class"]["alpha"] == 3
    assert fp["char_class"]["digit"] == 3


def test_whitespace_bucket_counts_spaces_tabs_newlines() -> None:
    fp = compute_fingerprint(" \t\n")
    assert fp["char_class"]["whitespace"] == 3
    assert fp["char_class"]["alpha"] == 0


def test_punct_bucket_counts_ascii_punctuation() -> None:
    fp = compute_fingerprint("!?.,;")
    assert fp["char_class"]["punct"] == 5


def test_non_printable_bucket_counts_control_chars() -> None:
    fp = compute_fingerprint("\x00\x01")
    assert fp["char_class"]["non_printable"] == 2
    assert _bucket_sum(fp) == 2


def test_empty_string_yields_zero_buckets_and_stable_hash() -> None:
    fp = compute_fingerprint("")
    assert fp["length_chars"] == 0
    assert fp["length_bytes"] == 0
    assert _bucket_sum(fp) == 0
    assert fp["hash"] == ("sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")


def test_fingerprint_has_documented_keys() -> None:
    fp = compute_fingerprint("x")
    assert set(fp.keys()) == {"hash", "length_chars", "length_bytes", "char_class"}
    assert set(fp["char_class"].keys()) == {
        "alpha",
        "digit",
        "punct",
        "whitespace",
        "non_printable",
    }
