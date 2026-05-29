"""PDF text extraction helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Sequence, Tuple

import fitz
import subprocess

from .utils import normalize_code


@dataclass
class PdfCodeOccurrence:
    """A text occurrence detected inside the PDF."""

    code_text: str
    code_norm: str
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    source: str
    pdf_path: str
    nearby_values: Tuple[str, ...] = ()


@dataclass
class WordEntry:
    """Single word extracted from PDF text, OCR, or vector pass."""

    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    block: int
    line: int
    word: int
    source: str


def extract_pdf_occurrences(
    pdf_path: str,
    target_codes: Iterable[str],
    max_word_span: int = 4,
    ocr_zoom: float = 2.0,
    ocr_confidence: int = 70,
    ocr_angles: Sequence[int] | None = None,
    enable_ocr: bool = False,
    enable_vector_ocr: bool = False,
    progress_callback: Callable[[str], None] | None = None,
) -> Dict[str, List[PdfCodeOccurrence]]:
    """
    Parse the PDF and return candidate occurrences matching the target codes.
    """

    normalized_targets = tuple({code for code in target_codes if code})
    if not normalized_targets:
        if progress_callback:
            progress_callback("No target codes available; skipping PDF scan.")
        return {}

    doc = fitz.open(pdf_path)
    try:
        matches: Dict[str, List[PdfCodeOccurrence]] = {}
        angles = tuple(ocr_angles) if ocr_angles else (0, 90, 180, 270)
        zoom_levels = _derive_zoom_levels(ocr_zoom) if enable_ocr else ()
        target_order = sorted(normalized_targets, key=len, reverse=True)
        total_pages = doc.page_count
        for page_index in range(total_pages):
            if progress_callback:
                progress_callback(f"Processing PDF page {page_index + 1}/{total_pages} ...")
            page = doc[page_index]
            words_raw = page.get_text("words") or []
            words: List[WordEntry] = [
                WordEntry(
                    x0=entry[0],
                    y0=entry[1],
                    x1=entry[2],
                    y1=entry[3],
                    text=entry[4],
                    block=entry[5],
                    line=entry[6],
                    word=entry[7],
                    source="text",
                )
                for entry in words_raw
            ]
            words.extend(_extract_annotation_words(page))
            if enable_ocr:
                for zoom_index, zoom_level in enumerate(zoom_levels):
                    if _OCR_WARNING:
                        break
                    words.extend(
                        _extract_ocr_words(
                            page,
                            zoom=zoom_level,
                            min_conf=ocr_confidence,
                            angles=angles,
                            block_base=(zoom_index + 1) * 10000,
                        )
                    )
            if enable_vector_ocr and not _OCR_WARNING:
                vector_words = _extract_vector_label_words(
                    page,
                    zoom=max(zoom_levels) if zoom_levels else 4.0,
                    min_conf=max(40, ocr_confidence - 15),
                    block_base=(len(zoom_levels) + 1) * 10000,
                )
                if vector_words:
                    words.extend(vector_words)
            if not words:
                continue
            # Sort by block, line, then word number to retain reading order.
            words.sort(key=lambda w: (w.block, w.line, w.word))
            lines = _group_words_by_line(words)
            page_occurrences: List[PdfCodeOccurrence] = []
            for line_words in lines.values():
                for candidate in _generate_sequences(
                    line_words, page_index, max_word_span, pdf_path
                ):
                    matched_codes = _match_target_codes(candidate.code_norm, target_order)
                    if not matched_codes:
                        continue
                    for code in matched_codes:
                        occ = PdfCodeOccurrence(
                            code_text=candidate.code_text,
                            code_norm=code,
                            page=candidate.page,
                            x0=candidate.x0,
                            y0=candidate.y0,
                            x1=candidate.x1,
                            y1=candidate.y1,
                            source=candidate.source,
                            pdf_path=candidate.pdf_path,
                        )
                        page_occurrences.append(occ)
                        matches.setdefault(code, []).append(occ)
            _populate_nearby_values(page_occurrences, words)
        if progress_callback:
            progress_callback("Finished PDF text extraction.")
        return matches
    finally:
        doc.close()


def _group_words_by_line(words: Sequence[WordEntry]) -> Dict[Tuple[int, int], List[WordEntry]]:
    grouped: Dict[Tuple[int, int], List[WordEntry]] = {}
    for word in words:
        text = word.text.strip()
        if not text:
            continue
        key = (word.block, word.line)
        grouped.setdefault(key, []).append(word)
    # Ensure each line respects word order
    for word_list in grouped.values():
        word_list.sort(key=lambda w: w.word)
    return grouped


def _generate_sequences(
    line_words: Sequence[WordEntry],
    page_index: int,
    max_span: int,
    pdf_path: str,
) -> Iterable[PdfCodeOccurrence]:
    cleaned_words = [word for word in line_words if word.text.strip()]
    total = len(cleaned_words)
    if not total:
        return []
    occurrences: List[PdfCodeOccurrence] = []
    for start in range(total):
        for length in range(1, max_span + 1):
            end = start + length
            if end > total:
                break
            texts = [cleaned_words[idx].text.strip() for idx in range(start, end)]
            combined = " ".join(texts).strip()
            if not combined:
                continue
            normalized = normalize_code(combined)
            if not normalized:
                continue
            x0 = min(cleaned_words[idx].x0 for idx in range(start, end))
            y0 = min(cleaned_words[idx].y0 for idx in range(start, end))
            x1 = max(cleaned_words[idx].x1 for idx in range(start, end))
            y1 = max(cleaned_words[idx].y1 for idx in range(start, end))
            sources = {cleaned_words[idx].source for idx in range(start, end)}
            source_label = sources.pop() if len(sources) == 1 else "mixed"
            occurrences.append(
                PdfCodeOccurrence(
                    code_text=combined,
                    code_norm=normalized,
                    page=page_index + 1,
                    x0=x0,
                    y0=y0,
                    x1=x1,
                    y1=y1,
                    source=source_label,
                    pdf_path=pdf_path,
                )
            )
    return occurrences


def _extract_ocr_words(
    page: fitz.Page,
    zoom: float = 2.0,
    min_conf: int = 70,
    angles: Sequence[int] = (0, 90, 180, 270),
    block_base: int = 0,
) -> List[WordEntry]:
    """Render the page multiple times and run OCR via the tesseract CLI."""

    words: List[WordEntry] = []
    if zoom <= 0:
        zoom = 2.0

    for idx, angle in enumerate(angles):
        matrix = fitz.Matrix(zoom, zoom)
        if angle:
            matrix = matrix.prerotate(angle)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        png_bytes = pix.tobytes("png")

        records = _run_tesseract_tsv(png_bytes, zoom)
        if not records:
            continue

        inv = fitz.Matrix(matrix)
        inv.invert()
        block_offset = block_base + (idx + 1) * 1000
        for rec in records:
            text = rec["text"]
            conf = rec["conf"]
            if conf < min_conf:
                continue
            left = rec["left"]
            top = rec["top"]
            width = rec["width"]
            height = rec["height"]
            if width <= 0 or height <= 0:
                continue
            p0 = fitz.Point(left, top)
            p1 = fitz.Point(left + width, top + height)
            p0.transform(inv)
            p1.transform(inv)
            block = block_offset + rec["block"]
            line = rec["line"]
            word = rec["word"]
            words.append(
                WordEntry(
                    x0=p0.x,
                    y0=p0.y,
                    x1=p1.x,
                    y1=p1.y,
                    text=text,
                    block=block,
                    line=line,
                    word=word,
                    source="ocr",
                )
            )
    return words


def _extract_vector_label_words(
    page: fitz.Page,
    zoom: float = 6.0,
    min_conf: int = 60,
    block_base: int = 0,
) -> List[WordEntry]:
    """OCR cropped regions that are likely vector-based labels (e.g., red door codes)."""

    rects = _collect_vector_label_rects(page)
    if not rects:
        return []
    merged_rects = _merge_rectangles(rects, margin=3.0)
    words: List[WordEntry] = []
    block_offset = block_base
    for idx, rect in enumerate(merged_rects):
        if rect.width < 8 or rect.height < 8:
            continue
        if rect.width > 250 or rect.height > 250:
            continue
        clip = fitz.Rect(rect)
        clip.x0 = max(page.rect.x0, clip.x0 - 1)
        clip.y0 = max(page.rect.y0, clip.y0 - 1)
        clip.x1 = min(page.rect.x1, clip.x1 + 1)
        clip.y1 = min(page.rect.y1, clip.y1 + 1)
        if clip.width <= 0 or clip.height <= 0:
            continue
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip, alpha=False)
        records = _run_tesseract_tsv(pix.tobytes("png"), zoom)
        if not records:
            continue
        block_offset += 100
        for rec in records:
            text = rec["text"]
            conf = rec["conf"]
            if conf < min_conf:
                continue
            width = rec["width"]
            height = rec["height"]
            if width <= 0 or height <= 0:
                continue
            left = rec["left"]
            top = rec["top"]
            x0 = clip.x0 + left / zoom
            y0 = clip.y0 + top / zoom
            x1 = clip.x0 + (left + width) / zoom
            y1 = clip.y0 + (top + height) / zoom
            words.append(
                WordEntry(
                    x0=x0,
                    y0=y0,
                    x1=x1,
                    y1=y1,
                    text=text,
                    block=block_offset,
                    line=rec["line"],
                    word=rec["word"],
                    source="vector-ocr",
                )
            )
    return words


def _run_tesseract_tsv(png_bytes: bytes, zoom: float) -> List[Dict[str, float]]:
    """Execute tesseract and return parsed TSV rows."""

    global _OCR_WARNING
    try:
        result = subprocess.run(
            [
                "tesseract",
                "stdin",
                "stdout",
                "--psm",
                "6",
                "--dpi",
                str(int(72 * zoom)),
                "-l",
                "eng",
                "tsv",
            ],
            input=png_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except FileNotFoundError:
        if not _OCR_WARNING:
            _OCR_WARNING = "OCR skipped because Tesseract is not installed or not on PATH."
        return []
    except subprocess.CalledProcessError as exc:
        if not _OCR_WARNING:
            _OCR_WARNING = (
                "OCR skipped because Tesseract failed to run. "
                "Check your installation and logs for details."
            )
        return []

    lines = result.stdout.decode("utf-8", errors="ignore").splitlines()
    if not lines:
        return []
    header = lines[0].split("\t")
    field_index = {name: idx for idx, name in enumerate(header)}
    required = {
        "text",
        "conf",
        "left",
        "top",
        "width",
        "height",
        "block_num",
        "line_num",
        "word_num",
    }
    if not required.issubset(field_index):
        return []

    records: List[Dict[str, float]] = []
    for raw in lines[1:]:
        if not raw.strip():
            continue
        parts = raw.split("\t")
        text = parts[field_index["text"]].strip()
        if not text:
            continue
        try:
            record = {
                "text": text,
                "conf": float(parts[field_index["conf"]]),
                "left": float(parts[field_index["left"]]),
                "top": float(parts[field_index["top"]]),
                "width": float(parts[field_index["width"]]),
                "height": float(parts[field_index["height"]]),
                "block": int(parts[field_index["block_num"]]),
                "line": int(parts[field_index["line_num"]]),
                "word": int(parts[field_index["word_num"]]),
            }
        except ValueError:
            continue
        records.append(record)
    return records


def _derive_zoom_levels(base_zoom: float) -> Tuple[float, ...]:
    """Return a tuple of zoom levels to run OCR with (deduped)."""

    zoom = base_zoom if base_zoom and base_zoom > 0 else 2.0
    levels: List[float] = [zoom]
    if zoom < 3.0:
        extra = max(3.0, zoom * 2)
        if extra not in levels:
            levels.append(extra)
    # Preserve order but drop near-duplicates
    deduped: List[float] = []
    for level in levels:
        add_level = round(level, 2)
        if add_level not in deduped:
            deduped.append(add_level)
    return tuple(deduped)


def _match_target_codes(
    normalized_text: str,
    targets: Sequence[str],
) -> List[str]:
    """Return target codes that appear inside the normalized text."""

    hits: List[str] = []
    if not normalized_text:
        return hits
    for code in targets:
        start = 0
        code_len = len(code)
        if not code_len:
            continue
        while True:
            idx = normalized_text.find(code, start)
            if idx == -1:
                break
            before = normalized_text[idx - 1] if idx > 0 else ""
            after_pos = idx + code_len
            after = normalized_text[after_pos] if after_pos < len(normalized_text) else ""
            if (before and before.isalnum()) or (after and after.isalnum()):
                start = idx + 1
                continue
            hits.append(code)
            break
    return hits


_NEARBY_PROXIMITY: float = 80.0


def _populate_nearby_values(
    occurrences: List[PdfCodeOccurrence],
    words: List[WordEntry],
    proximity: float = _NEARBY_PROXIMITY,
) -> None:
    """Populate each occurrence's nearby_values with normalized text of close words."""
    for occ in occurrences:
        cx = (occ.x0 + occ.x1) / 2
        cy = (occ.y0 + occ.y1) / 2
        nearby: List[str] = []
        for word in words:
            wx = (word.x0 + word.x1) / 2
            wy = (word.y0 + word.y1) / 2
            if abs(cx - wx) <= proximity and abs(cy - wy) <= proximity:
                norm = normalize_code(word.text)
                if norm and norm != occ.code_norm:
                    nearby.append(norm)
        occ.nearby_values = tuple(dict.fromkeys(nearby))


def _extract_annotation_words(page: fitz.Page) -> List[WordEntry]:
    """Extract words from PDF annotation /Contents fields."""
    words: List[WordEntry] = []
    block_base = 90000
    for idx, annot in enumerate(page.annots()):
        content = annot.info.get("content", "").strip()
        if not content:
            continue
        rect = annot.rect
        for word_idx, token in enumerate(content.split()):
            words.append(
                WordEntry(
                    x0=rect.x0,
                    y0=rect.y0,
                    x1=rect.x1,
                    y1=rect.y1,
                    text=token,
                    block=block_base + idx,
                    line=0,
                    word=word_idx,
                    source="annotation",
                )
            )
    return words


def _collect_vector_label_rects(page: fitz.Page) -> List[fitz.Rect]:
    """Return rectangles that likely correspond to vector labels."""

    rects: List[fitz.Rect] = []
    for drawing in page.get_drawings():
        rect = drawing.get("rect")
        if not rect:
            continue
        box = fitz.Rect(rect)
        if box.width <= 1 or box.height <= 1:
            continue
        if box.width > 300 or box.height > 300:
            continue
        rects.append(box)
    return rects


def _merge_rectangles(rects: Sequence[fitz.Rect], margin: float = 2.0) -> List[fitz.Rect]:
    """Merge rectangles that overlap or are within the given margin."""

    if not rects:
        return []
    result: List[fitz.Rect] = []
    for rect in sorted(rects, key=lambda r: (r.y0, r.x0)):
        expanded = fitz.Rect(rect)
        expanded.x0 -= margin
        expanded.y0 -= margin
        expanded.x1 += margin
        expanded.y1 += margin
        merged = False
        for idx, existing in enumerate(result):
            if expanded.intersects(existing):
                result[idx] = existing | rect
                merged = True
                break
        if not merged:
            result.append(fitz.Rect(rect))
    return result


_OCR_WARNING: str | None = None


def consume_ocr_warning() -> str | None:
    """Return and clear any captured OCR warning message."""

    global _OCR_WARNING
    message = _OCR_WARNING
    _OCR_WARNING = None
    return message
