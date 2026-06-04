"""Tests for write_report — table output and match status display."""

from __future__ import annotations

import tempfile
from pathlib import Path

from pdf_excel_annotator.matcher import MatchRow
from pdf_excel_annotator.report import write_report


def _write(rows: list[MatchRow], notes: list[str] | None = None) -> str:
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
        path = Path(f.name)
    write_report(path, rows, notes or [], {"pdf_paths": ["plan.pdf"], "excel_path": "data.xlsx", "code_column": "B", "header_row": 1})
    content = path.read_text(encoding="utf-8")
    path.unlink(missing_ok=True)
    return content


def _row(code: str, actual: int, expected: int, matched: bool = True, source: str = "text") -> MatchRow:
    return MatchRow(
        excel_row=2,
        code=code,
        matched=matched,
        detection_source=source,
        expected_count=expected,
        actual_count=actual,
    )


# ── Match status ───────────────────────────────────────────────────────────────

def test_full_match_shows_yes():
    content = _write([_row("SU-3.V", actual=66, expected=66)])
    assert "Yes" in content
    assert "Partial" not in content
    assert "No" not in content


def test_no_match_shows_no():
    content = _write([_row("SU-3.V", actual=0, expected=66, matched=False)])
    assert "No" in content
    assert "Yes" not in content


def test_partial_match_shows_partial():
    content = _write([_row("SU-3.V", actual=65, expected=66)])
    assert "Partial" in content
    assert "Yes" not in content
    assert "No" not in content


def test_single_match_no_count_column_shows_yes():
    """When expected == actual == 1 (no count column) it should show Yes."""
    content = _write([_row("ABC", actual=1, expected=1)])
    assert "Yes" in content


def test_single_no_match_no_count_column_shows_no():
    content = _write([_row("ABC", actual=0, expected=1, matched=False)])
    assert "No" in content


# ── Table columns ──────────────────────────────────────────────────────────────

def test_expected_found_columns_shown_when_counts_used():
    content = _write([_row("ABC", actual=2, expected=3)])
    assert "Expected" in content
    assert "Found" in content


def test_expected_found_columns_hidden_when_no_counts():
    content = _write([_row("ABC", actual=1, expected=1)])
    assert "Expected" not in content
    assert "Found" not in content


# ── Notes section ──────────────────────────────────────────────────────────────

def test_notes_included():
    content = _write([_row("ABC", actual=1, expected=1)], notes=["Something went wrong"])
    assert "Notes:" in content
    assert "Something went wrong" in content


def test_no_notes_section_when_empty():
    content = _write([_row("ABC", actual=1, expected=1)], notes=[])
    assert "Notes:" not in content
