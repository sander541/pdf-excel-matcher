"""Tests for normalize_code and generate_code_variants."""

from __future__ import annotations

from pdf_excel_annotator.utils import generate_code_variants, normalize_code


# ── normalize_code ─────────────────────────────────────────────────────────────

def test_normalize_uppercases():
    assert normalize_code("abc") == "ABC"


def test_normalize_strips_whitespace():
    assert normalize_code("  V MP U-1  ") == "VMPU-1"


def test_normalize_none_returns_empty():
    assert normalize_code(None) == ""


def test_normalize_empty_returns_empty():
    assert normalize_code("   ") == ""


def test_normalize_strips_leading_zeros_from_numeric_segments():
    """SMU-01 and SMU-1 must normalize to the same string."""
    assert normalize_code("SMU-01") == normalize_code("SMU-1")


def test_normalize_leading_zeros_multi_digit():
    assert normalize_code("ABC-001") == "ABC-1"


def test_normalize_leading_zeros_with_suffix():
    assert normalize_code("SU-02.1V") == normalize_code("SU-2.1V")


def test_normalize_non_leading_zeros_unchanged():
    """100, 10, 200 have no leading zeros — must stay the same."""
    assert normalize_code("A100") == "A100"
    assert normalize_code("A010") == "A10"   # 010 → 10 (leading zero stripped)


def test_normalize_standalone_zero():
    assert normalize_code("0") == "0"


def test_normalize_double_zero():
    assert normalize_code("00") == "0"


# ── generate_code_variants ─────────────────────────────────────────────────────

def test_variants_no_dot():
    assert generate_code_variants("SMU-1") == ["SMU-1"]


def test_variants_single_dot():
    assert generate_code_variants("SU-3.V") == ["SU-3.V", "SU-3"]


def test_variants_two_dots():
    assert generate_code_variants("ABC.01.02") == ["ABC.01.02", "ABC.01", "ABC"]


def test_variants_empty():
    assert generate_code_variants("") == []
