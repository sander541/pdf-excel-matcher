"""Utility helpers shared across modules."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List


WHITESPACE_RE = re.compile(r"\s+")
CODE_COLUMN_RE = re.compile(r"^[A-Za-z]{1,3}$")


def normalize_code(value: str) -> str:
    """Return a normalized string used for comparisons."""
    if value is None:
        return ""
    trimmed = value.strip()
    if not trimmed:
        return ""
    no_ws = WHITESPACE_RE.sub("", trimmed)
    return no_ws.upper()


def generate_code_variants(code_norm: str) -> List[str]:
    """Generate fallback variants for a normalized code (e.g., remove suffixes)."""

    variants: List[str] = []
    if not code_norm:
        return variants
    current = code_norm
    variants.append(current)
    while "." in current:
        current = current.rsplit(".", 1)[0]
        if current and current not in variants:
            variants.append(current)
        else:
            break
    return variants


def ensure_output_path(path: str | Path) -> Path:
    """Resolve and ensure the parent directory exists."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def is_valid_code_column(value: str) -> bool:
    """Return True when the provided Excel column looks like A, AA, etc."""
    if not value:
        return False
    return bool(CODE_COLUMN_RE.fullmatch(value.strip()))
