from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import PipelineOptions
from .pipeline import run_pipeline
from .utils import is_valid_code_column


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--excel-path", required=True, help="Path to Excel workbook")
    parser.add_argument(
        "--pdf-path",
        dest="pdf_paths",
        nargs="+",
        required=True,
        help="One or more paths to floorplan PDFs (space-separated)",
    )
    parser.add_argument(
        "--output-path",
        required=True,
        help="Destination text report path",
    )
    parser.add_argument("--annotated-dir", help="Directory for annotated PDFs")
    parser.add_argument(
        "--code-column",
        required=True,
        help="Excel column letter that stores codes",
    )
    parser.add_argument(
        "--count-column",
        default=None,
        help="Optional Excel column letter with expected occurrence counts (e.g., D).",
    )
    parser.add_argument(
        "--specifier-column",
        default=None,
        help="Optional Excel column letter whose value appears near the code in the PDF.",
    )
    parser.add_argument(
        "--specifier-radius",
        type=float,
        default=80.0,
        help="Search radius in PDF points for nearby specifier values (default: 80).",
    )
    parser.add_argument(
        "--header-row",
        type=int,
        required=True,
        help="Excel row number used for headers",
    )
    parser.add_argument(
        "--max-row",
        type=int,
        default=None,
        help="Optional maximum Excel row to inspect (inclusive)",
    )
    parser.add_argument(
        "--max-word-span",
        type=int,
        default=4,
        help="How many consecutive PDF words to combine when searching for codes",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        excel_path = Path(args.excel_path)
        pdf_paths = [Path(path) for path in args.pdf_paths]
        if not excel_path.exists():
            raise FileNotFoundError(f"Excel file not found: {excel_path}")
        if not pdf_paths:
            raise ValueError("At least one --pdf-path must be provided")
        missing = [str(path) for path in pdf_paths if not path.exists()]
        if missing:
            raise FileNotFoundError(f"PDF file(s) not found: {', '.join(missing)}")
        if args.header_row < 1:
            raise ValueError("header-row must be >= 1")
        if not is_valid_code_column(args.code_column):
            raise ValueError("code-column must be Excel letters, e.g., C or AA")
        if args.count_column and not is_valid_code_column(args.count_column):
            raise ValueError("count-column must be Excel letters, e.g., D or AA")
        if args.specifier_column and not is_valid_code_column(args.specifier_column):
            raise ValueError("specifier-column must be Excel letters, e.g., A or AA")
        if args.max_word_span < 1:
            raise ValueError("max-word-span must be >= 1")
        max_row = args.max_row
        if max_row is not None and max_row < args.header_row:
            raise ValueError("max-row must be >= header-row when provided")

        options = PipelineOptions(
            excel_path=excel_path,
            pdf_paths=pdf_paths,
            output_path=Path(args.output_path),
            annotated_dir=Path(args.annotated_dir).expanduser()
            if args.annotated_dir
            else None,
            code_column=args.code_column,
            count_column=args.count_column,
            specifier_column=args.specifier_column,
            specifier_radius=args.specifier_radius,
            header_row=args.header_row,
            max_row=max_row,
            max_word_span=args.max_word_span,
        )

        logging.basicConfig(level=logging.INFO, format="%(message)s")
        result = run_pipeline(options, progress_callback=lambda m: print(m, flush=True))
        if result.notes:
            print("Notes:")
            for note in result.notes:
                print(f" - {note}")
        return 0
    except Exception as exc:  # pragma: no cover - CLI safeguard
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
