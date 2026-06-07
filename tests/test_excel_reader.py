"""Tests for load_excel_codes — annotation_columns filtering and count exclusion."""

from __future__ import annotations

import tempfile
from pathlib import Path

import openpyxl
import pytest

from pdf_excel_annotator.excel_reader import load_excel_codes, read_column_headers


# ── Fixture: create a small test workbook ─────────────────────────────────────

def _make_workbook(rows: list[list]) -> Path:
    """Write rows to a temp xlsx and return its path."""
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    wb.save(tmp.name)
    tmp.close()
    return Path(tmp.name)


@pytest.fixture()
def simple_workbook():
    """
    Row 1 (header): Door | Code | Count | Room | Level
    Row 2:          101  | SU-1 | 3     | Lobby | 1
    Row 3:          102  | VU-2 | 1     | Office | 1
    """
    path = _make_workbook([
        ["Door", "Code", "Count", "Room", "Level"],
        ["101", "SU-1", 3, "Lobby", "1"],
        ["102", "VU-2", 1, "Office", "1"],
    ])
    yield path
    path.unlink(missing_ok=True)


# ── read_column_headers ────────────────────────────────────────────────────────

def test_read_column_headers(simple_workbook):
    headers = read_column_headers(simple_workbook, header_row=1)
    assert headers[0] == ("A", "Door")
    assert headers[1] == ("B", "Code")
    assert headers[2] == ("C", "Count")
    assert headers[3] == ("D", "Room")
    assert headers[4] == ("E", "Level")


# ── Default behaviour: count column excluded ───────────────────────────────────

def test_count_column_excluded_by_default(simple_workbook):
    entries = load_excel_codes(
        simple_workbook,
        code_column="B",
        header_row=1,
        count_column="C",
    )
    for entry in entries:
        col_keys = {h for h, _ in entry.row_data}
        assert "Count" not in col_keys, "Count column should be excluded from row_data by default"


def test_code_column_present_by_default(simple_workbook):
    """Code column is included in row_data unless explicitly excluded via annotation_columns."""
    entries = load_excel_codes(
        simple_workbook,
        code_column="B",
        header_row=1,
    )
    for entry in entries:
        col_keys = {h for h, _ in entry.row_data}
        assert "Code" in col_keys


# ── annotation_columns filter ──────────────────────────────────────────────────

def test_annotation_columns_restricts_to_selection(simple_workbook):
    entries = load_excel_codes(
        simple_workbook,
        code_column="B",
        header_row=1,
        annotation_columns=frozenset({"A", "D"}),
    )
    for entry in entries:
        col_keys = {h for h, _ in entry.row_data}
        assert col_keys == {"Door", "Room"}


def test_count_column_included_when_in_annotation_columns(simple_workbook):
    """When count column is explicitly in the selection it should appear in row_data."""
    entries = load_excel_codes(
        simple_workbook,
        code_column="B",
        header_row=1,
        count_column="C",
        annotation_columns=frozenset({"B", "C", "D"}),
    )
    for entry in entries:
        col_keys = {h for h, _ in entry.row_data}
        assert "Count" in col_keys, "Count column should be present when explicitly selected"


def test_empty_annotation_columns_shows_nothing(simple_workbook):
    entries = load_excel_codes(
        simple_workbook,
        code_column="B",
        header_row=1,
        annotation_columns=frozenset(),
    )
    for entry in entries:
        assert entry.row_data == []


# ── Count column parsing ───────────────────────────────────────────────────────

def test_expected_count_read_from_count_column(simple_workbook):
    entries = load_excel_codes(
        simple_workbook,
        code_column="B",
        header_row=1,
        count_column="C",
    )
    counts = {e.code_raw: e.expected_count for e in entries}
    assert counts["SU-1"] == 3
    assert counts["VU-2"] == 1


def test_expected_count_defaults_to_one_without_count_column(simple_workbook):
    entries = load_excel_codes(
        simple_workbook,
        code_column="B",
        header_row=1,
    )
    for entry in entries:
        assert entry.expected_count == 1
