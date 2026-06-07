"""Tests for _match_target_codes — prefix suppression and boundary checks."""

from __future__ import annotations

from pdf_excel_annotator.pdf_reader import _match_target_codes


# ── Basic matching ─────────────────────────────────────────────────────────────

def test_exact_match():
    assert _match_target_codes("SU-021V", ["SU-021V"]) == ["SU-021V"]


def test_no_match():
    assert _match_target_codes("SU-021V", ["SU-023V"]) == []


def test_boundary_prevents_substring():
    """ABC should not match inside XABCY (alphanumeric boundary)."""
    assert _match_target_codes("XABCY", ["ABC"]) == []


def test_non_alnum_boundary_allowed():
    """ABC should match when surrounded by non-alphanumeric chars."""
    assert "ABC" in _match_target_codes("(ABC)", ["ABC"])


# ── Prefix suppression ────────────────────────────────────────────────────────

def test_base_code_suppressed_when_longer_matches():
    """
    PDF text SU-02.1V should produce only SU-02.1V, not also SU-02.
    Without suppression, SU-02 would be a separate occurrence that
    SU-02.3V could claim via variant fallback — wrong door, wrong data.
    """
    hits = _match_target_codes("SU-021V", ["SU-021V", "SU-023V", "SU-02"])
    assert "SU-021V" in hits
    assert "SU-02" not in hits


def test_base_code_kept_when_no_longer_match():
    """Bare SU-02 in PDF with no exact suffixed match — keep it."""
    hits = _match_target_codes("SU-02", ["SU-021V", "SU-023V", "SU-02"])
    assert hits == ["SU-02"]


def test_two_distinct_codes_both_kept():
    """Two different codes separated by space — both should match, base suppressed."""
    # Space acts as a non-alphanumeric boundary so both exact codes match.
    hits = _match_target_codes("SU-02.1V SU-02.3V", ["SU-02.1V", "SU-02.3V", "SU-02"])
    assert "SU-02.1V" in hits
    assert "SU-02.3V" in hits
    assert "SU-02" not in hits
