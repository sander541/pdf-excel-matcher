"""PDF text extraction helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Sequence, Tuple

import fitz

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
    """Single word extracted from PDF text or annotation fields."""

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
    specifier_radius: float = 80.0,
    progress_callback: Callable[[str], None] | None = None,
) -> Dict[str, List[PdfCodeOccurrence]]:
    """
    Parse the PDF and return candidate occurrences matching the target codes.
    Uses the native text layer and annotation fields only.
    """

    normalized_targets = tuple({code for code in target_codes if code})
    if not normalized_targets:
        if progress_callback:
            progress_callback("No target codes available; skipping PDF scan.")
        return {}

    doc = fitz.open(pdf_path)
    try:
        matches: Dict[str, List[PdfCodeOccurrence]] = {}
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
            _populate_nearby_values(page_occurrences, words, proximity=specifier_radius)
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


# Annotation types whose /Contents field may carry user-typed codes.
_ANNOT_CODE_TYPES: frozenset[int] = frozenset({
    fitz.PDF_ANNOT_SQUARE,
    fitz.PDF_ANNOT_CIRCLE,
    fitz.PDF_ANNOT_FREE_TEXT,
    fitz.PDF_ANNOT_TEXT,
    fitz.PDF_ANNOT_STAMP,
    fitz.PDF_ANNOT_WIDGET,
})

# Block index offset for words extracted from annotations.
_ANNOTATION_BLOCK_BASE: int = 90_000


def _populate_nearby_values(
    occurrences: List[PdfCodeOccurrence],
    words: List[WordEntry],
    proximity: float = 80.0,
) -> None:
    """Populate each occurrence's nearby_values with normalized text of close words."""
    for occ in occurrences:
        cx = (occ.x0 + occ.x1) / 2
        cy = (occ.y0 + occ.y1) / 2
        nearby: List[str] = []
        for word in words:
            wx = (word.x0 + word.x1) / 2
            if abs(cx - wx) > proximity:
                continue
            wy = (word.y0 + word.y1) / 2
            if abs(cy - wy) > proximity:
                continue
            norm = normalize_code(word.text)
            if norm and norm != occ.code_norm:
                nearby.append(norm)
        occ.nearby_values = tuple(dict.fromkeys(nearby))


def _extract_annotation_words(page: fitz.Page) -> List[WordEntry]:
    """Extract words from PDF annotation /Contents fields.

    Only considers annotation types that are likely to carry user-typed codes
    (squares, circles, free text, stamps, widgets). Highlights, underlines,
    ink annotations, and links are skipped.
    """
    words: List[WordEntry] = []
    for idx, annot in enumerate(page.annots()):
        if annot.type[0] not in _ANNOT_CODE_TYPES:
            continue
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
                    block=_ANNOTATION_BLOCK_BASE + idx,
                    line=0,
                    word=word_idx,
                    source="annotation",
                )
            )
    return words
