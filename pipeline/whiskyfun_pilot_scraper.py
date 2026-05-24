#!/usr/bin/env python3
"""
Pilot scraper for whiskyfun.com monthly archive pages.

TODO(post-pilot): multi-month URL discovery, distillery/author fields, disk cache, stricter dedupe.

DOM notes (archivejanuary12-1.html, HTML 4.01):
- Day markers: <font color="#660000" size="3" face="Arial"><strong><b>January 9, 2012</b></strong></font>
- Reviews: often in <table width="500">, <td> with span.textenormalfoncegras (bottle title) plus prose
  containing Colour:/Nose:/Mouth/Finish/Comments and often SGP:### - ## points.
- Quirk: segments are "from this day marker until the next marker in **file order**", not strict
  calendar order; some sessions sit under a different marker than the calendar title suggests.
  Default --date 2012-01-09 matches the eight-note Clynelish session on this page.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import time
from datetime import date
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup

# Title/score helpers live in whiskyfun_parse_utils so the batch crawler and CSV cleaner share
# one implementation (newer pages merged intro blurbs into the title span; see module docstring).
from whiskyfun_parse_utils import (
    extract_clean_bottle_title,
    extract_score_from_text,
    head_before_colour,
    rebuild_review_text,
)

# --- pilot defaults (override with --url / --date) ---
DEFAULT_ARCHIVE_URL = "https://www.whiskyfun.com/archivejanuary12-1.html"
DEFAULT_FILTER_DATE = "2012-01-09"  # eight Clynelish session rows on this page

USER_AGENT = (
    "CSSS594-WhiskyfunPilot/1.0 (+https://example.edu; educational research; respectful crawl)"
)

# Month day, year in archive day headers (font #660000 block).
# Legacy (approx. 2012 and earlier): nested strong/b inside font with face="Arial".
DAY_HEADER_PATTERN = re.compile(
    r'<font\s+color="#660000"\s+size="3"\s+face="Arial">\s*<strong>\s*<b>\s*'
    r'((?:January|February|March|April|May|June|July|August|September|October|November|December)'
    r'\s+\d{1,2},\s+\d{4})\s*</b>\s*</strong>\s*</font>',
    re.IGNORECASE | re.DOTALL,
)
# Newer archives: date directly inside font (optional face); may use double space before year.
DAY_HEADER_PATTERN_ALT = re.compile(
    r'<font\s+color="#660000"\s+size="3"[^>]*>\s*'
    r'((?:January|February|March|April|May|June|July|August|September|October|November|December)'
    r'\s+\d{1,2},\s*\d{4})\s*</font>',
    re.IGNORECASE | re.DOTALL,
)

MONTH_MAP = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def fetch_html(url: str, timeout: float = 25.0, pause: float = 0.75) -> tuple[str, str]:
    """Download page; return (raw_html, page_title)."""
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"ERROR: HTTP request failed: {e}", file=sys.stderr)
        sys.exit(1)
    time.sleep(pause)
    # Archives declare ISO-8859-1; apparent_encoding helps if header missing.
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding or "iso-8859-1"
    raw = r.text
    title_m = re.search(r"<title>([^<]*)</title>", raw, re.I)
    title = html.unescape(title_m.group(1).strip()) if title_m else ""
    return raw, title


def parse_header_date(header: str) -> date | None:
    """Parse 'January 9, 2012' -> date."""
    m = re.match(
        r"^\s*([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})\s*$",
        header.strip(),
    )
    if not m:
        return None
    mon_s, day_s, year_s = m.groups()
    mon = MONTH_MAP.get(mon_s.lower())
    if not mon:
        return None
    try:
        return date(int(year_s), mon, int(day_s))
    except ValueError:
        return None


def split_html_by_day(raw_html: str) -> list[tuple[date, str]]:
    """Split raw HTML into (date, html_fragment_after_header) segments in document order."""
    spans: list[tuple[int, int, str]] = []
    for m in DAY_HEADER_PATTERN.finditer(raw_html):
        spans.append((m.start(), m.end(), m.group(1)))
    for m in DAY_HEADER_PATTERN_ALT.finditer(raw_html):
        spans.append((m.start(), m.end(), m.group(1)))
    spans.sort(key=lambda x: x[0])
    used_starts: set[int] = set()
    merged: list[tuple[int, int, str]] = []
    for start, end, g1 in spans:
        if start in used_starts:
            continue
        used_starts.add(start)
        merged.append((start, end, g1))

    out: list[tuple[date, str]] = []
    for i, (_start, end, g1) in enumerate(merged):
        header = html.unescape(re.sub(r"\s+", " ", g1.strip()))
        d = parse_header_date(header)
        if d is None:
            continue
        frag_start = end
        frag_end = merged[i + 1][0] if i + 1 < len(merged) else len(raw_html)
        out.append((d, raw_html[frag_start:frag_end]))
    return out


def normalize_ws(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip()


def is_noise_review_text(text: str) -> bool:
    tl = text.lower()
    if "pete mcpeat" in tl or "jack washback" in tl:
        return True
    if "performer:" in tl and "track:" in tl:
        return True
    if "recommended listening:" in tl and "music" in tl[:200]:
        return True
    if "don't score wine" in tl or "don’t score wine" in tl or "do not score wine" in tl:
        return True
    if "score: we don" in tl and "wine" in tl:
        return True
    return False


def looks_like_tasting_note(text: str) -> bool:
    """Semantic gate: structured tasting note, not rambling / music."""
    if "Colour:" not in text and "Color:" not in text:
        return False
    if "Nose:" not in text:
        return False
    if "Mouth" not in text and "Palate:" not in text:
        return False
    if is_noise_review_text(text):
        return False
    # Drop tiny image-caption cells
    if len(text) < 80:
        return False
    return True


def extract_score(text: str) -> int | None:
    return extract_score_from_text(text)


def extract_whisky_name_raw(td: Any) -> str | None:
    """
    Bottle line only: parse text before the first Colour:/Color: in the cell, using the same
    `(NN%` … `)` rule as the CSV cleaner. Prefer full <td> text so we see the real structure;
    fall back to textenormalfoncegras span if needed (older pages).
    """
    raw = normalize_ws(td.get_text(" ", strip=True))
    if not raw:
        return None
    head = head_before_colour(raw)
    title, _ = extract_clean_bottle_title(head)
    if title:
        return title
    span = td.find("span", class_=re.compile(r"textenormalfoncegras", re.I))
    if span:
        raw_s = normalize_ws(span.get_text())
        title, _ = extract_clean_bottle_title(head_before_colour(raw_s))
        if title:
            return title
    return None


def extract_reviews_from_day_fragment(fragment_html: str) -> list[dict[str, Any]]:
    """Parse one day's HTML chunk; return review dicts."""
    soup = BeautifulSoup(fragment_html, "html.parser")
    seen_td: set[int] = set()
    rows: list[dict[str, Any]] = []

    def push_td(td: Any) -> None:
        tid = id(td)
        if tid in seen_td:
            return
        text = normalize_ws(td.get_text(" ", strip=True))
        if not looks_like_tasting_note(text):
            return
        name = extract_whisky_name_raw(td)
        if not name:
            h = head_before_colour(text)
            name, _ = extract_clean_bottle_title(h)
            if not name:
                name = normalize_ws(text)[:200]
        if not name:
            return
        # Align review_text opening with the cleaned title (drops merged blurb from name column).
        h2 = head_before_colour(text)
        title_body, _ = extract_clean_bottle_title(h2)
        if title_body:
            text = rebuild_review_text(text, title_body)
        score = extract_score(text)
        seen_td.add(tid)
        rows.append({"whisky_name_raw": name, "review_text": text, "score": score})

    for name_span in soup.find_all("span", class_=re.compile(r"textenormalfoncegras", re.I)):
        td = name_span.find_parent("td")
        if td is None:
            continue
        push_td(td)

    # Newer layouts: few or no textenormalfoncegras spans; scan table cells for tasting blocks.
    if not rows:
        for td in soup.find_all("td"):
            push_td(td)

    return rows


def run_scrape(
    url: str,
    filter_date: date,
    pause: float,
    csv_path: str,
    json_path: str,
) -> pd.DataFrame:
    raw, page_title = fetch_html(url, pause=pause)
    print(f"Page title: {page_title}")

    segments = split_html_by_day(raw)
    print(f"Day segments found in HTML: {len(segments)}")

    target_frag = None
    for d, frag in segments:
        if d == filter_date:
            target_frag = frag
            break

    if target_frag is None:
        print(
            f"ERROR: No section for {filter_date.isoformat()} in this page. "
            f"Dates present: {sorted({d.isoformat() for d, _ in segments})}",
            file=sys.stderr,
        )
        sys.exit(2)

    candidates = extract_reviews_from_day_fragment(target_frag)
    print(f"Candidate review blocks (after semantic filter): {len(candidates)}")
    if not candidates:
        print("ERROR: zero reviews extracted; check --date or page layout.", file=sys.stderr)
        sys.exit(3)

    records = []
    for c in candidates:
        records.append(
            {
                "whisky_name_raw": c["whisky_name_raw"],
                "review_text": c["review_text"],
                "score": c["score"],
                "review_date": filter_date.isoformat(),
                "source_url": url,
            }
        )

    df = pd.DataFrame.from_records(records)
    print("\nFirst 2 parsed records:")
    for i, rec in enumerate(records[:2]):
        preview = {k: (v if k != "review_text" else v[:220] + ("…" if len(v) > 220 else "")) for k, v in rec.items()}
        print(f"  [{i}] {preview}")

    df.to_csv(csv_path, index=False)
    df.to_json(json_path, orient="records", force_ascii=False, indent=2)
    print(f"\nWrote {len(df)} rows -> {csv_path}, {json_path}")
    return df


def main() -> None:
    p = argparse.ArgumentParser(description="Whiskyfun archive pilot scraper (single page, single date).")
    p.add_argument("--url", default=DEFAULT_ARCHIVE_URL, help="Archive HTML URL")
    p.add_argument(
        "--date",
        default=DEFAULT_FILTER_DATE,
        help="Filter to this calendar date (YYYY-MM-DD)",
    )
    p.add_argument("--sleep", type=float, default=0.75, help="Seconds to sleep after HTTP GET")
    p.add_argument("--csv", default="pilot_whiskyfun_reviews.csv")
    p.add_argument("--json", default="pilot_whiskyfun_reviews.json")
    args = p.parse_args()

    y, m, d = (int(x) for x in args.date.split("-"))
    filter_date = date(y, m, d)

    run_scrape(args.url, filter_date, args.sleep, args.csv, args.json)


if __name__ == "__main__":
    main()
