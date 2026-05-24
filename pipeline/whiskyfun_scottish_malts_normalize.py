"""
Normalization for matching Whiskyfun index entries to the date-scraped corpus.

Rules align with the project plan: lowercase, collapse whitespace, normalize quotes,
strip risky punctuation where safe, normalize ABV/percent, drop terminal score phrases,
remove SGP codes for fuzzy comparison.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Final


def parse_ddmmyy_anchor(code: str) -> date | None:
    """
    Whiskyfun archive anchors are typically DDMMYY (six digits). YY mapping matches archive crawl.
    """
    c = (code or "").strip()
    if len(c) != 6 or not c.isdigit():
        return None
    dd, mm, yy = int(c[:2]), int(c[2:4]), int(c[4:6])
    year = 2000 + yy if yy < 70 else 1900 + yy
    try:
        return date(year, mm, dd)
    except ValueError:
        return None

# Strip SGP blocks like "SGP:466 - 92 points" or "SGP:520 - 29 points."
SGP_POINTS_TAIL: Final[re.Pattern[str]] = re.compile(
    r"\s*SGP\s*:?\s*\d+\s*[-–]\s*\d{1,3}\s*points\s*\.?",
    re.IGNORECASE,
)
SGP_ONLY: Final[re.Pattern[str]] = re.compile(r"\s*SGP\s*:?\s*\d+\s*[-–]\s*\d+", re.IGNORECASE)

# Terminal "90 points" without SGP (rare)
POINTS_TAIL: Final[re.Pattern[str]] = re.compile(
    r"\s*[-–]\s*\d{1,3}\s*points\s*\.?\s*$",
    re.IGNORECASE,
)

QUOTE_MAP = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u00ab": '"',
        "\u00bb": '"',
    }
)


def normalize_whisky_name_for_match(s: str) -> str:
    """Aggressive normalization for tier-2/3 matching keys."""
    if not s:
        return ""
    t = unicodedata.normalize("NFKC", s)
    t = t.translate(QUOTE_MAP)
    t = t.lower().strip()
    # normalize percent / abv spacing
    t = re.sub(r"(\d)\s*%", r"\1%", t)
    t = re.sub(r"\babv\b", "%", t)
    # remove SGP mentions inline
    t = SGP_ONLY.sub(" ", t)
    t = SGP_POINTS_TAIL.sub(" ", t)
    t = POINTS_TAIL.sub("", t)
    # remove parenthetical score remnants
    t = re.sub(r"\(\s*\d{1,3}\s*points\s*\)", "", t, flags=re.I)
    # punctuation to space (keep alphanumeric and basic separators)
    t = re.sub(r"[^\w\s%\-+#]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def normalize_text_snippet_for_match(s: str, max_chars: int = 200) -> str:
    """First ~max_chars of normalized review-like text for tier 3."""
    base = normalize_whisky_name_for_match(s)
    if len(base) > max_chars:
        return base[:max_chars]
    return base


def normalize_source_url(url: str) -> str:
    """Canonical base archive URL: https host, no fragment, no trailing slash on path."""
    from urllib.parse import urlparse, urlunparse

    if not (url or "").strip():
        return ""
    p = urlparse(url.strip())
    if not p.netloc:
        return ""
    path = (p.path or "").rstrip("/") or "/"
    netloc = p.netloc.lower()
    if netloc.startswith("www.whiskyfun.com"):
        netloc = "www.whiskyfun.com"
    scheme = (p.scheme or "https").lower()
    return urlunparse((scheme, netloc, path, "", "", ""))


def normalize_source_url_loose(url: str) -> str:
    """Case-insensitive path for archive filenames that differ only by case."""
    u = normalize_source_url(url)
    from urllib.parse import urlparse, urlunparse

    p = urlparse(u)
    low_path = (p.path or "").lower()
    return urlunparse((p.scheme, p.netloc.lower(), low_path, "", "", ""))


def score_string_to_int(s: str | int | float | None) -> int | None:
    if s is None or s == "":
        return None
    if isinstance(s, int):
        return s
    if isinstance(s, float):
        return int(s)
    try:
        return int(str(s).strip())
    except ValueError:
        return None
