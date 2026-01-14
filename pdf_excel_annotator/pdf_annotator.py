"""Helper for annotating PDF matches."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping

import fitz

from .matcher import MatchDetail


def _normalized_clamped_rect(rect: fitz.Rect, page_rect: fitz.Rect) -> fitz.Rect | None:
    """Normalize rect and clamp it to page bounds. Returns None if empty/outside."""
    r = fitz.Rect(rect)
    r.normalize()

    # If it doesn't intersect the page at all, skip.
    if not r.intersects(page_rect):
        return None

    # Clamp to page bounds.
    r.x0 = max(r.x0, page_rect.x0)
    r.y0 = max(r.y0, page_rect.y0)
    r.x1 = min(r.x1, page_rect.x1)
    r.y1 = min(r.y1, page_rect.y1)
    r.normalize()

    # Skip degenerate rectangles (some PyMuPDF versions have no Rect.get_area()).
    if (r.x1 - r.x0) <= 0 or (r.y1 - r.y0) <= 0:
        return None
    return r


def _add_highlight_annotation(
    page: fitz.Page,
    rect: fitz.Rect,
    info: str,
    highlight_color: tuple[float, float, float],
) -> bool:
    """Attempt to add a highlight annotation for the given rectangle."""

    # Normalize and clamp to the page bounds (guards against inverted/out-of-page boxes).
    page_rect = page.rect
    rect = _normalized_clamped_rect(rect, page_rect)
    if rect is None:
        return False

    try:
        # Newer PyMuPDF versions accept a Rect directly for highlight annotations.
        annot = page.add_highlight_annot(rect)
    except Exception:
        try:
            # Fallback: create a proper Quad from the rect.
            annot = page.add_highlight_annot(fitz.Quad(rect))
        except Exception:
            return False

    # PyMuPDF highlight annotations may ignore fill and do not support borders in some versions.
    # Setting them can spam warnings, so keep this minimal and compatible.
    try:
        annot.set_colors(stroke=highlight_color)
    except Exception:
        pass

    try:
        annot.set_opacity(0.45)
    except Exception:
        pass

    try:
        annot.set_info(content=info)
    except Exception:
        pass

    popup_width = 200
    popup_height = 140
    popup_x0 = min(max(rect.x1 + 6, page_rect.x0), page_rect.x1 - popup_width)
    popup_y0 = min(max(rect.y0, page_rect.y0), page_rect.y1 - popup_height)
    popup_rect = fitz.Rect(
        popup_x0,
        popup_y0,
        popup_x0 + popup_width,
        popup_y0 + popup_height,
    )
    # Popups are inconsistently supported across PDF viewers; treat as best-effort.
    try:
        # Ensure popup rect is valid and on-page.
        popup_rect = _normalized_clamped_rect(popup_rect, page_rect)
        if (
            popup_rect is not None
            and (popup_rect.x1 - popup_rect.x0) > 0
            and (popup_rect.y1 - popup_rect.y0) > 0
        ):
            popup = page.add_popup_annot(popup_rect)
            popup.set_info(content=info)
            popup.update()
            annot.set_popup(popup)
    except Exception:
        pass

    annot.update()
    return True


def annotate_matches(
    matches: Iterable[MatchDetail],
    output_dir: str | Path,
    highlight_color: tuple[float, float, float] = (1.0, 0.92, 0.23),
) -> Mapping[str, Path]:
    """
    Annotate PDFs for the provided matches.

    Returns a mapping of source PDF path -> annotated PDF path.
    """

    matches_by_pdf: dict[str, list[MatchDetail]] = {}
    for detail in matches:
        matches_by_pdf.setdefault(detail.occurrence.pdf_path, []).append(detail)

    output_mapping: dict[str, Path] = {}
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    name_counts: dict[str, int] = {}

    for pdf_path, pdf_matches in matches_by_pdf.items():
        source = Path(pdf_path)
        if not source.exists():
            continue
        doc = fitz.open(pdf_path)
        try:
            for detail in pdf_matches:
                occ = detail.occurrence
                # Defensive: skip invalid page indices.
                if occ.page < 1 or occ.page > doc.page_count:
                    continue
                page = doc[occ.page - 1]
                rect = fitz.Rect(occ.x0, occ.y0, occ.x1, occ.y1)
                details = [
                    f"{header}: {value}" for header, value in detail.excel_entry.row_data
                ]
                info = "\n".join(details) if details else detail.excel_entry.code_raw
                # Some viewers truncate long annotation content; keep it bounded.
                if info and len(info) > 2000:
                    info = info[:2000] + "…"
                success = _add_highlight_annotation(page, rect, info, highlight_color)
                if not success:
                    try:
                        annot = page.add_rect_annot(rect)
                        annot.set_colors(stroke=highlight_color, fill=(1.0, 1.0, 0.3))
                        annot.set_border(width=0.7)
                        annot.set_opacity(0.25)
                        annot.set_info(content=info)
                        annot.update()
                    except Exception:
                        pass

            base = f"{source.stem}_annotated_{timestamp}"
            count = name_counts.get(base, 0) + 1
            name_counts[base] = count
            suffix = "" if count == 1 else f"_{count}"
            output_path = target_dir / f"{base}{suffix}.pdf"
            doc.save(output_path, garbage=4, deflate=True)
            output_mapping[pdf_path] = output_path
        finally:
            doc.close()

    return output_mapping
