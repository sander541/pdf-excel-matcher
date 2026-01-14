# PDF ↔ Excel Annotator (Prototype)

Command-line helper that checks whether door codes stored in an Excel workbook
appear inside a floor-plan PDF, then writes a Markdown report describing which
codes matched.

## Requirements

- Python 3.10+ (tested with 3.11)
- `pip` plus the libraries listed in `requirements.txt` (PyMuPDF, openpyxl)
- Tesseract OCR binary available in `$PATH`

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
python -m pdf_excel_annotator.cli \
  --excel-path "/path/to/locks.xlsx" \
  --pdf-path "/path/to/floorplan-level1.pdf" "/path/to/floorplan-level2.pdf" \
  --code-column C \
  --header-row 1 \
  --output-path /path/to/output/report.txt \
  --max-word-span 4
```

Arguments:

- `--excel-path`: path to the Excel workbook (defaults to the sample file)
- `--pdf-path`: one or more floorplan PDF paths (space-separated; defaults to the sample file)
- `--code-column`: Excel column letter containing door codes (required)
- `--header-row`: row number that stores headers; data starts on the next row
- `--max-row`: optional maximum row (inclusive) to scan in Excel; defaults to the sheet’s last row
- `--output-path`: text report destination (defaults to `resource/output/report.txt`)
- `--annotated-dir`: optional directory where highlighted PDF copies will be saved
- `--max-word-span`: how many consecutive PDF words to join when searching for codes (default: 4)
- `--ocr-zoom`: base rasterization zoom used before OCR fallback (default: 2.0). Values below 3 also trigger an additional higher-zoom pass automatically; only used if `--enable-ocr` is set.
- `--ocr-confidence`: minimum OCR confidence score required to include a word (default: 70).
- `--enable-ocr`: opt-in flag to run raster OCR when native text search isn’t enough (disabled by default).
- `--enable-vector-ocr`: opt-in flag to OCR the colored vector door labels (disabled by default; requires `--enable-ocr` for best results).
- `--ocr-angles`: comma-separated list of rotation angles (degrees) used when OCRing each page (default: 0,90,180,270)

The script prints the final report path and any mismatch notes. The text file
contains a summary block plus an ASCII table with one row per Excel entry, a
`Source` column describing whether the match came from inherent PDF text,
standard OCR, or the vector-label OCR fallback, and an optional notes list
highlighting count differences.

## GUI

A simple PySide6 GUI is available for users who prefer not to run the CLI:

```bash
python gui.py
```

The GUI lets you pick the Excel workbook, manage multiple PDFs, and tweak the
same options as the CLI. OCR-related controls live under “Advanced Options”.
