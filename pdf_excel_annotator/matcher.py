"""Matching logic between Excel codes and PDF occurrences."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from .excel_reader import ExcelCodeEntry
from .pdf_reader import PdfCodeOccurrence
from .utils import generate_code_variants


@dataclass
class MatchRow:
    """Represents a row in the final report."""

    excel_row: int
    code: str
    matched: bool
    detection_source: str | None = None


@dataclass
class MatchDetail:
    """Details about a matched Excel entry and PDF occurrence."""

    excel_entry: ExcelCodeEntry
    occurrence: PdfCodeOccurrence


def build_match_results(
    excel_entries: Sequence[ExcelCodeEntry],
    pdf_occurrences: Dict[str, List[PdfCodeOccurrence]],
) -> Tuple[List[MatchRow], List[str], List[MatchDetail]]:
    """Return table rows plus notes about mismatched counts."""

    rows: List[MatchRow] = []
    notes: List[str] = []
    details: List[MatchDetail] = []
    excel_counts: Counter[str] = Counter()
    display_map: Dict[str, str] = {}
    unmatched_counts: Counter[str] = Counter()

    available_occurrences: Dict[str, List[PdfCodeOccurrence]] = {
        key: list(value) for key, value in pdf_occurrences.items()
    }
    pdf_counts: Dict[str, int] = {key: len(value) for key, value in pdf_occurrences.items()}
    usage_counts: Counter[str] = Counter()

    for entry in excel_entries:
        excel_counts[entry.code_norm] += 1
        display_map.setdefault(entry.code_norm, entry.code_raw)
        variants = generate_code_variants(entry.code_norm) or [entry.code_norm]
        matched_key = None
        matched_occurrence: PdfCodeOccurrence | None = None
        for variant in variants:
            occ_list = available_occurrences.get(variant)
            if occ_list:
                matched_occurrence = occ_list.pop()
                matched_key = variant
                usage_counts[variant] += 1
                break
        matched = matched_key is not None
        if not matched:
            unmatched_counts[entry.code_norm] += 1
        elif matched_occurrence:
            details.append(MatchDetail(excel_entry=entry, occurrence=matched_occurrence))
        rows.append(
            MatchRow(
                excel_row=entry.excel_row,
                code=entry.code_raw,
                matched=matched,
                detection_source=matched_occurrence.source if matched_occurrence else None,
            )
        )

    # Notes for Excel codes that still lacked matches
    for code_norm, missing_count in unmatched_counts.items():
        total = excel_counts.get(code_norm, 0)
        display = display_map.get(code_norm, code_norm)
        if missing_count:
            notes.append(
                f"Code `{display}` matched {total - missing_count} of {total} expected entries."
            )

    # Notes for PDF codes whose counts differ from matched Excel entries
    for code_norm, pdf_count in pdf_counts.items():
        matched_count = usage_counts.get(code_norm, 0)
        if pdf_count != matched_count:
            notes.append(
                f"Code `{code_norm}` occurs {pdf_count} time(s) in PDF but matched to {matched_count} Excel entries."
            )

    return rows, notes, details
