"""Tests for build_match_results — matching, variant fallback, note generation."""

from __future__ import annotations

from pdf_excel_annotator.excel_reader import ExcelCodeEntry
from pdf_excel_annotator.matcher import MatchDetail, build_match_results
from pdf_excel_annotator.pdf_reader import PdfCodeOccurrence


# ── Helpers ───────────────────────────────────────────────────────────────────

def _entry(code: str, expected: int = 1, row: int = 2) -> ExcelCodeEntry:
    return ExcelCodeEntry(
        code_raw=code,
        code_norm=code.upper(),
        excel_row=row,
        row_data=[],
        expected_count=expected,
    )


def _occ(code: str, pdf: str = "plan.pdf", page: int = 1) -> PdfCodeOccurrence:
    return PdfCodeOccurrence(
        code_text=code,
        code_norm=code.upper(),
        page=page,
        x0=0, y0=0, x1=10, y1=10,
        source="text",
        pdf_path=pdf,
    )


# ── Basic matching ─────────────────────────────────────────────────────────────

def test_exact_match():
    entries = [_entry("ABC")]
    occurrences = {"ABC": [_occ("ABC")]}
    rows, notes, details = build_match_results(entries, occurrences)
    assert rows[0].matched is True
    assert rows[0].actual_count == 1
    assert not any("ABC" in n and "0 of" in n for n in notes)


def test_no_match():
    entries = [_entry("ABC")]
    rows, notes, details = build_match_results(entries, {})
    assert rows[0].matched is False
    assert rows[0].actual_count == 0
    assert any("ABC" in n for n in notes)


def test_count_fully_satisfied():
    entries = [_entry("ABC", expected=3)]
    occurrences = {"ABC": [_occ("ABC"), _occ("ABC"), _occ("ABC")]}
    rows, notes, details = build_match_results(entries, occurrences)
    assert rows[0].actual_count == 3
    assert rows[0].matched is True
    assert not any("ABC" in n and "matched" in n for n in notes)


def test_count_partially_satisfied():
    entries = [_entry("ABC", expected=3)]
    occurrences = {"ABC": [_occ("ABC")]}
    rows, notes, details = build_match_results(entries, occurrences)
    assert rows[0].actual_count == 1
    assert rows[0].matched is True  # found at least 1
    assert any("1 of 3" in n for n in notes)


# ── Variant fallback ───────────────────────────────────────────────────────────

def test_variant_fallback_to_base():
    """SU-3.V not in PDF; bare SU-3 should be used as fallback."""
    entries = [_entry("SU-3.V", expected=2)]
    occurrences = {"SU-3": [_occ("SU-3"), _occ("SU-3")]}
    rows, notes, details = build_match_results(entries, occurrences)
    assert rows[0].actual_count == 2
    assert rows[0].matched is True


def test_variant_fallback_partial():
    """SU-3.V has 1 exact hit but needs 3; fallback to SU-3 fills the rest."""
    entries = [_entry("SU-3.V", expected=3)]
    occurrences = {
        "SU-3.V": [_occ("SU-3.V")],
        "SU-3": [_occ("SU-3"), _occ("SU-3")],
    }
    rows, notes, details = build_match_results(entries, occurrences)
    assert rows[0].actual_count == 3
    assert rows[0].matched is True


# ── Bare-code note suppression ─────────────────────────────────────────────────

def test_bare_code_note_suppressed_when_suffixed_matched():
    """SU-3 in PDF should NOT generate an unmatched note when SU-3.P was matched."""
    entries = [_entry("SU-3.P", expected=2)]
    occurrences = {
        "SU-3.P": [_occ("SU-3.P"), _occ("SU-3.P")],
        "SU-3": [_occ("SU-3")] * 5,
    }
    rows, notes, details = build_match_results(entries, occurrences)
    assert not any("SU-3" in n and "matched to 0" in n for n in notes)


def test_bare_code_note_shown_when_not_a_known_variant():
    """XYZ-99 in PDF with no Excel entry should still generate a note."""
    entries = [_entry("ABC", expected=1)]
    occurrences = {
        "ABC": [_occ("ABC")],
        "XYZ-99": [_occ("XYZ-99")],
    }
    rows, notes, details = build_match_results(entries, occurrences)
    assert any("XYZ-99" in n for n in notes)


# ── Details ────────────────────────────────────────────────────────────────────

def test_details_populated_on_match():
    entries = [_entry("ABC")]
    occurrences = {"ABC": [_occ("ABC")]}
    _, _, details = build_match_results(entries, occurrences)
    assert len(details) == 1
    assert isinstance(details[0], MatchDetail)


def test_details_empty_on_no_match():
    entries = [_entry("ABC")]
    _, _, details = build_match_results(entries, {})
    assert details == []
