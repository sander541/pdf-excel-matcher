"""Compat shim so `python main.py` still works."""

from pdf_excel_annotator.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
