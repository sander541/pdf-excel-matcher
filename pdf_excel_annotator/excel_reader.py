from __future__  import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence, Tuple

from openpyxl import load_workbook
from openpyxl.utils import column_index_from_string, get_column_letter

from .utils import normalize_code


@dataclass
class ExcelCodeEntry:

    code_raw: str
    code_norm: str
    excel_row: int
    row_data: Sequence[Tuple[str, str]]
    expected_count: int = 1  # From count_column, defaults to 1 if not specified
    specifier_norm: str | None = None  # Normalized value from specifier_column


def load_excel_codes(
    workbook_path: str | Path,
    code_column: str,
    header_row: int,
    max_row: int | None = None,
    count_column: str | None = None,
    specifier_column: str | None = None,
) -> List[ExcelCodeEntry]:

    column_index = column_index_from_string(code_column.upper())
    count_col_index = column_index_from_string(count_column.upper()) if count_column else None
    specifier_col_index = column_index_from_string(specifier_column.upper()) if specifier_column else None
    workbook = load_workbook(workbook_path, data_only=True, read_only=True)
    try:
        sheet = workbook.active  # single-sheet assumption for now
        entries: List[ExcelCodeEntry] = []
        max_col = sheet.max_column
        headers: list[str] = []
        for col_idx in range(1, max_col + 1):
            header_value = sheet.cell(row=header_row, column=col_idx).value
            if header_value is None:
                header = get_column_letter(col_idx)
            else:
                header = str(header_value).strip() or get_column_letter(col_idx)
            headers.append(header)

        start_row = header_row + 1
        final_row = sheet.max_row if max_row is None else min(max_row, sheet.max_row)
        for row_idx in range(start_row, final_row + 1):
            cell = sheet.cell(row=row_idx, column=column_index)
            value = cell.value
            if value is None:
                continue
            text = str(value).strip()
            if not text:
                continue
            normalized = normalize_code(text)
            if not normalized:
                continue

            row_entries: list[Tuple[str, str]] = []
            for col_idx in range(1, max_col + 1):
                cell_value = sheet.cell(row=row_idx, column=col_idx).value
                if cell_value is None:
                    continue
                value_text = str(cell_value).strip()
                if not value_text:
                    continue
                header = headers[col_idx - 1]
                row_entries.append((header, value_text))

            # Extract expected count if count_column is specified
            expected_count = 1
            if count_col_index:
                count_cell = sheet.cell(row=row_idx, column=count_col_index)
                if count_cell.value is not None:
                    try:
                        expected_count = max(1, int(count_cell.value))
                    except (ValueError, TypeError):
                        expected_count = 1

            specifier_norm: str | None = None
            if specifier_col_index:
                spec_cell = sheet.cell(row=row_idx, column=specifier_col_index)
                if spec_cell.value is not None:
                    spec_text = str(spec_cell.value).strip()
                    specifier_norm = normalize_code(spec_text) or None

            entries.append(
                ExcelCodeEntry(
                    code_raw=text,
                    code_norm=normalized,
                    excel_row=row_idx,
                    row_data=row_entries,
                    expected_count=expected_count,
                    specifier_norm=specifier_norm,
                )
            )
        return entries
    finally:
        workbook.close()
