"""Plain-text report writer."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence

from .matcher import MatchRow
from .utils import ensure_output_path


def write_report(
    output_path: str | Path,
    rows: Sequence[MatchRow],
    notes: Sequence[str],
    metadata: Mapping[str, object],
) -> Path:
    """Persist a plain-text report and return its path."""

    target_path = ensure_output_path(output_path)
    lines: list[str] = []
    heading = "PDF ↔ Excel Match Report"
    lines.append(heading)
    lines.append("=" * len(heading))
    lines.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")

    pdf_paths = metadata.get("pdf_paths")
    excel_path = metadata.get("excel_path")
    code_column = metadata.get("code_column")
    header_row = metadata.get("header_row")
    max_row = metadata.get("max_row")

    if pdf_paths:
        if isinstance(pdf_paths, (list, tuple)):
            for idx, path in enumerate(pdf_paths, start=1):
                label = "PDF" if len(pdf_paths) == 1 else f"PDF #{idx}"
                lines.append(f"{label}: {path}")
        else:
            lines.append(f"PDF: {pdf_paths}")
    if excel_path:
        lines.append(f"Excel: {excel_path}")
    if code_column is not None:
        lines.append(f"Code column: {code_column}")
    if header_row is not None:
        lines.append(f"Header row: {header_row}")
    if max_row is not None:
        lines.append(f"Max row: {max_row}")
    lines.append("")

    def _match_status(row: MatchRow) -> str:
        """Return Yes / Partial / No depending on how many occurrences were found."""
        if row.actual_count == 0:
            return "No"
        if row.actual_count < row.expected_count:
            return "Partial"
        return "Yes"

    # Show Expected/Found columns whenever a count column was used
    # (i.e. any row has expected_count > 1, or any partial/zero match exists).
    has_counts = any(row.expected_count > 1 for row in rows)

    if has_counts:
        headers = ["Excel Row", "Code", "Expected", "Found", "Matched", "Source"]
        table_rows = [
            [
                str(row.excel_row),
                row.code,
                str(row.expected_count),
                str(row.actual_count),
                _match_status(row),
                row.detection_source or "-",
            ]
            for row in rows
        ]
    else:
        headers = ["Excel Row", "Code", "Matched", "Source"]
        table_rows = [
            [
                str(row.excel_row),
                row.code,
                _match_status(row),
                row.detection_source or "-",
            ]
            for row in rows
        ]
    if not table_rows:
        table_rows.append(["N/A"] * len(headers))

    widths = [
        max(len(headers[idx]), *(len(r[idx]) for r in table_rows))
        for idx in range(len(headers))
    ]

    def border(char: str) -> str:
        segments = ["+" + char * (width + 2) for width in widths]
        return "".join(segments) + "+"

    def fmt_row(values: Sequence[str]) -> str:
        cells = [
            values[idx].ljust(widths[idx]) for idx in range(len(widths))
        ]
        return "| " + " | ".join(cells) + " |"

    lines.append(border("-"))
    lines.append(fmt_row(headers))
    lines.append(border("="))
    for row in table_rows:
        lines.append(fmt_row(row))
    lines.append(border("-"))

    if notes:
        lines.append("")
        lines.append("Notes:")
        for note in notes:
            lines.append(f"  • {note}")

    target_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target_path
