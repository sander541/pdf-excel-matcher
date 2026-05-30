from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Mapping, Optional


@dataclass
class PipelineOptions:
    excel_path: Path
    pdf_paths: List[Path]
    output_path: Path
    code_column: str
    header_row: int
    annotated_dir: Optional[Path] = None
    max_row: Optional[int] = None
    max_word_span: int = 4
    ocr_zoom: float = 2.0
    ocr_confidence: int = 70
    ocr_angles: List[int] = field(default_factory=lambda: [0, 90, 180, 270])
    enable_ocr: bool = False
    enable_vector_ocr: bool = False
    count_column: Optional[str] = None  # Column with expected occurrence counts (e.g., "D")
    specifier_column: Optional[str] = None  # Column whose value disambiguates duplicate codes
    specifier_radius: float = 80.0  # Search radius (pt) for nearby specifier values


@dataclass
class PipelineResult:

    report_path: Path
    notes: List[str]
    annotated_pdfs: Mapping[str, Path]
