"""
Shared parsing helpers for whiskyfun.com archive text (titles, merged reviews).

Used by whiskyfun_pilot_scraper (live scrape) and whiskyfun_clean_archive (CSV backfill).

Problem context (see project plan):
  1) Newer HTML often puts the Serge/Angus intro *inside* the same span/cell as the bottle line.
     We only want the bottle identifier (through the closing `)` of the `(NN%, …)` block).
  2) "Angus's Corner" posts sometimes pack several full tasting notes in one <td>. We detect
     multiple `SGP: … points` tails and split; rows whose *name* is the Angus banner are dropped
     in the cleaner, not here.

Title logic centres on the first `(NN%` in the text before `Colour:` — that marks the official
metadata parenthetical; we pair parens to find its end, then optionally strip a leading PREVIEW.
"""

from __future__ import annotations

import re
from typing import Final

# ABV token inside parentheses, e.g. (51%, or (57.80%,
ABV_IN_PARENS: Final[re.Pattern[str]] = re.compile(r"\(\d{1,2}(?:\.\d+)?%")

# Full SGP score tail (one review block typically ends with this). Hyphen or en-dash.
SGP_POINTS_TAIL: Final[re.Pattern[str]] = re.compile(
    r"SGP\s*:?\s*\d+\s*[-–]\s*\d{1,3}\s*points\s*\.?",
    re.IGNORECASE,
)

_PREVIEW_PREFIX: Final[re.Pattern[str]] = re.compile(r"^\s*preview\s+", re.IGNORECASE)


def normalize_ws(t: str) -> str:
    """Collapse internal whitespace; HTML/cell dumps often have runs of spaces/newlines."""
    return re.sub(r"\s+", " ", t).strip()


def first_colour_index(text: str) -> int | None:
    """Start index of first 'Colour:' / 'Color:' tasting marker, or None."""
    m = re.search(r"\bcolour\s*:", text, re.IGNORECASE)
    if m:
        return m.start()
    m = re.search(r"\bcolor\s*:", text, re.IGNORECASE)
    return m.start() if m else None


def head_before_colour(text: str) -> str:
    """Text before the first tasting-note Colour/Color marker (single-spaced)."""
    t = normalize_ws(text)
    idx = first_colour_index(t)
    if idx is None:
        return t
    return normalize_ws(t[:idx])


def strip_preview_prefix(title: str) -> str:
    """Site sometimes prefixes unreleased bottles with PREVIEW (still one real review)."""
    return normalize_ws(_PREVIEW_PREFIX.sub("", title))


def _close_paren_from_open(s: str, open_idx: int) -> int | None:
    """Given index of '(', return index of matching ')' or None."""
    if open_idx < 0 or open_idx >= len(s) or s[open_idx] != "(":
        return None
    depth = 0
    for j in range(open_idx, len(s)):
        ch = s[j]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return j
    return None


def extract_clean_bottle_title(head: str) -> tuple[str, bool]:
    """
    From prose before Colour:/Color:, extract the bottle line only.

    Strategy:
      - Locate `(NN%` … `)` via paren depth (handles nested parens inside the metadata block).
      - `prefix` is everything before that opening `(`. If it contains sentence punctuation,
        keep only the *last* sentence (e.g. "…masters. Cutty Black " → "Cutty Black "). If it
        has no `.?!`, treat the whole prefix as the name (e.g. "Uitvlugt 26 yo … " before `(51%`).

    Returns (title, low_confidence). low_confidence True when the `(NN%` rule did not apply
    (_fallback_title_no_abv).
    """
    h = normalize_ws(head)
    if not h:
        return "", True

    m = ABV_IN_PARENS.search(h)
    if not m:
        return _fallback_title_no_abv(h)

    # m.start() is the `(` immediately before the strength percentage.
    open_idx = m.start()
    close_idx = _close_paren_from_open(h, open_idx)
    if close_idx is None:
        return strip_preview_prefix(h), True

    prefix = h[:open_idx].strip()
    meta = h[open_idx : close_idx + 1]
    if not prefix:
        title = meta
    elif re.search(r"[.!?…]", prefix):
        # Lead essay before the bottle name (Cutty Black, etc.): last clause is the name.
        segs = re.split(r"(?<=[.!?…])\s+", prefix)
        name_part = segs[-1].strip() if segs else prefix
        title = normalize_ws(f"{name_part} {meta}".strip())
    else:
        # Blurb lives after the closing `)` of meta (typical Uitvlugt pattern); keep full prefix.
        title = normalize_ws(f"{prefix} {meta}".strip())
    title = strip_preview_prefix(title)
    return (title, False)


def _fallback_title_no_abv(h: str) -> tuple[str, bool]:
    """
    When there is no (NN% pattern): take up to first ')' that looks like end of a label line,
    else return stripped head (caller may drop low-quality rows).
    """
    h = strip_preview_prefix(h)
    m = re.search(r"\)\s+(['\u2018\u2019]?[A-Za-z])", h)
    if m:
        return normalize_ws(h[: m.start() + 1]), False
    if ")" in h:
        idx = h.find(")")
        if idx < 220:
            return normalize_ws(h[: idx + 1]), True
    return h, True


def looks_like_tasting_segment(text: str) -> bool:
    """Minimal structure check for a single review chunk."""
    if "Colour:" not in text and "Color:" not in text:
        return False
    if "Nose:" not in text:
        return False
    if "Mouth" not in text and "Palate:" not in text:
        return False
    if len(normalize_ws(text)) < 80:
        return False
    return True


def is_angus_corner_header_row(whisky_name_raw: str) -> bool:
    """
    True when the scraper used the whole Angus column banner as the bottle name.

    We only match this prefix (ASCII or typographic apostrophe), not the word "Angus" inside
    a normal review title (e.g. "…citizen Angus…").
    """
    n = (whisky_name_raw or "").strip()
    if not n:
        return False
    low = n.lower()
    return low.startswith("angus's corner") or low.startswith("angus\u2019s corner")


def find_second_review_start(full_text: str, search_from: int) -> int | None:
    """
    After the first `SGP: … points` match ends at `search_from`, find where a *second* full
    tasting note begins (next bottle title + Colour:/Nose:/… + its own SGP tail).

    We scan forward from stripped whitespace: try each position that could start a distillery
    word, take text up to the next Colour:, run the same title extractor, and require a
    structured segment plus another SGP block so we do not split on false positives.
    """
    raw_tail = full_text[search_from:]
    tail = raw_tail.lstrip(" \n\t\r\f\v.")
    if not tail:
        return None
    # Map index inside `tail` back to absolute index in `full_text`.
    delta = len(raw_tail) - len(tail)

    for i in range(len(tail)):
        if not tail[i].isalnum():
            continue
        abs_start = search_from + delta + i
        sub = tail[i:]
        cidx = first_colour_index(sub)
        if cidx is None or cidx <= 0:
            continue
        head_cand = normalize_ws(sub[:cidx])
        title, _ = extract_clean_bottle_title(head_cand)
        if len(title) < 8:
            continue
        if "(" not in title or ")" not in title:
            continue
        seg = full_text[abs_start:]
        sample = seg[: min(len(seg), 12000)]
        if not looks_like_tasting_segment(sample):
            continue
        if not SGP_POINTS_TAIL.search(seg):
            continue
        return abs_start
    return None


def rebuild_review_text(text: str, title: str) -> str:
    """
    After we know the canonical `title`, rewrite the opening of `review_text` so it matches:
    `title` + optional blurb that sat *after* the bottle line in the head + unchanged tail
    from the first `Colour:` onward. Keeps hashes/content stable except for the fixed prefix.
    """
    t_full = normalize_ws(text)
    ci = first_colour_index(t_full)
    if ci is None:
        return t_full
    tail = t_full[ci:].lstrip()
    head = normalize_ws(t_full[:ci])
    h_stripped = strip_preview_prefix(head)
    if h_stripped.startswith(title):
        blurb = normalize_ws(h_stripped[len(title) :])
    else:
        blurb = normalize_ws(head[len(title) :]) if head.startswith(title) else ""
    mid = f"{title} {blurb}".strip() if blurb else title
    return normalize_ws(f"{mid} {tail}")


def extract_score_from_text(text: str) -> int | None:
    """Numeric points from the SGP tail; site uses ASCII hyphen or en-dash (–)."""
    m = re.search(
        r"SGP\s*:?\s*\d+\s*[-–]\s*(\d{1,3})\s*points\s*\.?",
        text,
        re.IGNORECASE,
    )
    return int(m.group(1)) if m else None


def split_review_text_multi_sgp(full_text: str, max_splits: int = 6) -> list[str]:
    """
    Split one table cell's text when it contains several complete reviews (each ends with SGP).

    Greedy loop: while the current slice still has ≥2 SGP tails, peel off the first physical
    review (from start through the character before the next bottle title). `max_splits` caps
    work on corrupted text.
    """
    text = normalize_ws(full_text)
    if not text:
        return [text]

    segments: list[str] = []
    cur = text
    guard = 0
    while guard < max_splits:
        guard += 1
        ms = list(SGP_POINTS_TAIL.finditer(cur))
        if len(ms) < 2:
            if cur:
                segments.append(cur)
            break
        ns = find_second_review_start(cur, ms[0].end())
        if ns is None:
            if cur:
                segments.append(cur)
            break
        first_part = normalize_ws(cur[:ns])
        if first_part:
            segments.append(first_part)
        cur = normalize_ws(cur[ns:])
        if not cur:
            break

    return segments if segments else [text]
