# PDF ↔ Excel Annotator

CLI and GUI tool that reads codes from an Excel workbook, scans one or more
floor‑plan PDFs for those codes, writes a plain‑text match report, and can
optionally export highlighted PDF copies for visual review.

## Download (packaged app)

Pre-built installers are available for all platforms on the
[releases page](https://github.com/sander541/pdf-excel-matcher/releases/latest):

| Platform | File |
|----------|------|
| Windows | `pdf-excel-annotator-setup.exe` (Inno Setup installer) |
| macOS | `pdf-excel-annotator-macos.zip` (`.app` bundle) |
| Linux | `pdf-excel-annotator-linux.tar.gz` |

The app checks for updates automatically on launch and installs them silently
on Windows. See [DISTRIBUTION.md](DISTRIBUTION.md) for full release and
update documentation.

---

## Requirements (running from source)

- Python 3.10+ (tested with 3.11)
- `pip` plus the libraries listed in `requirements.txt` (PyMuPDF, openpyxl, PySide6)
- Optional: Tesseract OCR in your `$PATH` (only needed if you enable OCR features)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## CLI Usage

```bash
python -m pdf_excel_annotator.cli \
  --excel-path "/path/to/locks.xlsx" \
  --pdf-path "/path/to/floorplan-l1.pdf" "/path/to/floorplan-l2.pdf" \
  --code-column C \
  --header-row 1 \
  --output-path "/path/to/output/report.txt" \
  --max-word-span 4
```

Arguments:

- `--excel-path`: **required** path to the workbook to scan (single-sheet assumed)
- `--pdf-path`: **required** one or more PDF files to check (space-separated)
- `--code-column`: **required** Excel column letter(s) that contain the codes (e.g. `C`, `AA`)
- `--header-row`: **required** row number whose cells hold the headers
- `--max-row`: optional maximum row (inclusive) to inspect; omit to read the full sheet
- `--output-path`: **required** destination for the plain-text report (`.txt`)
- `--annotated-dir`: optional directory where highlighted PDF copies are saved; if omitted, only the report is written
- `--max-word-span`: how many consecutive PDF words to join when searching for codes (default: 4)
- `--ocr-zoom`: base rasterization zoom used before OCR fallback (default: 2.0). Values below 3 also trigger an additional higher-zoom pass automatically; only used if `--enable-ocr` is set.
- `--ocr-confidence`: minimum OCR confidence score required to include a word (default: 90 in CLI/GUI).
- `--enable-ocr`: opt-in flag to run raster OCR when native text search isn’t enough (disabled by default).
- `--enable-vector-ocr`: opt-in flag to OCR the colored vector door labels (disabled by default; requires `--enable-ocr` for best results).
- `--ocr-angles`: comma-separated list of rotation angles (degrees) used when OCRing each page (default: 0,90,180,270)

### Output

- Report: a plain‑text table with metadata that opens cleanly in any editor.
- Annotated PDFs: when `--annotated-dir` (CLI) or the checkbox (GUI) is used,
  highlighted copies are saved there with a timestamped suffix, e.g.
  `floorplan_annotated_20250101123456.pdf`.
- The CLI prints progress messages and, at the end, a Notes section summarizing
  count mismatches and any OCR warnings (e.g., when Tesseract is unavailable).

## GUI

A simple PySide6 GUI is available if you prefer not to run the CLI:

```bash
python gui.py
```

Features:

- Drag and drop PDFs directly into the list or use “Add PDF…”.
- Validation for Excel path, PDF set, output directory, code column, and header row.
- “Limit rows” checkbox to cap Excel scanning without guessing `0 = all`.
- “Advanced Options” panel that hides OCR/vector tuning until needed.
- Live log area with timestamps, plus a clear button, so long runs stay readable.
- Option to save annotated PDFs into the same directory as the report (enabled by default).

Launch it from the project root with `python gui.py`.

## How Matching Works

- Normalization: Excel codes and PDF text are normalized by removing whitespace
  and upper‑casing to increase matching tolerance (e.g., `V MP U-1` → `VMPU-1`).
- Variants: When a code has dot‑suffixes, shorter fallbacks are also considered
  (`ABC.01.02` → tries `ABC.01.02`, then `ABC.01`, then `ABC`).
- Boundaries: Matches require non‑alphanumeric boundaries so that substrings in
  longer words don’t trigger false positives.

## Notes on OCR

- OCR is disabled by default. Enable it with `--enable-ocr` (CLI) or the
  “Enable OCR” checkbox (GUI) when PDFs lack a text layer or labels are embedded
  as images.
- Tesseract is only required when OCR is enabled. If it’s missing or fails to
  run, the tool skips OCR and adds a warning to the Notes section.
- The GUI defaults to `OCR confidence = 90` and the CLI’s default matches that.
  Lower the confidence to keep more borderline OCR words at the expense of noise.

## Tips

- For tiny labels, increase `--ocr-zoom` (and consider enabling OCR). Values
  below 3 also trigger an additional higher‑zoom pass automatically.
- Increase `--max-word-span` if codes are fragmented across OCR tokens.
- Use `--annotated-dir` to produce visual PDFs that highlight where each match
  was found and include related Excel details in the annotation popup.

## Alternative Launch

You can also run the CLI via the shim: `python main.py`.
