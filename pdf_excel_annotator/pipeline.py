"""Core pipeline helpers for the PDF ↔ Excel annotator."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

from .config import PipelineOptions, PipelineResult
from . import (
    annotate_matches,
    build_match_results,
    extract_pdf_occurrences,
    load_excel_codes,
    write_report,
)
from .pdf_reader import consume_ocr_warning
from .utils import generate_code_variants

logger = logging.getLogger(__name__)


def run_pipeline(
    options: PipelineOptions,
    progress_callback: Callable[[str], None] | None = None,
) -> PipelineResult:
    """Execute the annotator pipeline using the provided options."""

    def emit(message: str) -> None:
        if progress_callback:
            progress_callback(message)
        else:
            logger.info(message)

    excel_path = options.excel_path
    emit(f"Loading Excel workbook: {excel_path}")
    excel_entries = load_excel_codes(
        str(excel_path),
        options.code_column,
        options.header_row,
        max_row=options.max_row,
        count_column=options.count_column,
        specifier_column=options.specifier_column,
    )
    if not excel_entries:
        message = "No codes found in the Excel workbook."
        emit(message)
        raise ValueError(message)

    target_codes: set[str] = set()
    for entry in excel_entries:
        variants = generate_code_variants(entry.code_norm) or [entry.code_norm]
        target_codes.update(variants)

    combined_occurrences: Dict[str, List] = {}
    for pdf_path in options.pdf_paths:
        emit(f"Scanning PDF for codes: {pdf_path}")

        def _progress(msg: str, *, name=Path(pdf_path).name) -> None:
            emit(f"[{name}] {msg}")

        occurrences = extract_pdf_occurrences(
            str(pdf_path),
            target_codes,
            max_word_span=options.max_word_span,
            ocr_zoom=options.ocr_zoom,
            ocr_confidence=options.ocr_confidence,
            ocr_angles=options.ocr_angles,
            enable_ocr=options.enable_ocr,
            enable_vector_ocr=options.enable_vector_ocr,
            specifier_radius=options.specifier_radius,
            progress_callback=_progress,
        )
        for code, occs in occurrences.items():
            combined_occurrences.setdefault(code, []).extend(occs)

    rows, notes, details = build_match_results(excel_entries, combined_occurrences)
    ocr_warning = consume_ocr_warning()
    if ocr_warning:
        notes.append(ocr_warning)
    metadata = {
        "pdf_paths": [str(path) for path in options.pdf_paths],
        "excel_path": str(excel_path),
        "code_column": options.code_column.upper(),
        "header_row": options.header_row,
        "max_row": options.max_row,
    }
    report_path = write_report(options.output_path, rows, notes, metadata)
    emit(f"Report written to {report_path}")

    annotated_paths: Dict[str, Path] = {}
    if options.annotated_dir:
        if details:
            annotated_paths = annotate_matches(details, options.annotated_dir, count_column=options.count_column)
            for original, annotated in annotated_paths.items():
                emit(f"Annotated PDF saved: {annotated} (from {original})")
        else:
            emit("Skipping annotated PDFs because no matches were found.")

    return PipelineResult(
        report_path=report_path,
        notes=notes,
        annotated_pdfs=annotated_paths,
    )
