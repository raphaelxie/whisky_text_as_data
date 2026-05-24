#!/usr/bin/env python3
"""
Batch archive crawler for whiskyfun.com — extends the pilot parser.

Examples:
  python whiskyfun_archive_crawl.py discover --shallow --urls-out archive_urls.jsonl
  python whiskyfun_archive_crawl.py crawl --urls-file archive_urls.jsonl \\
      --out-dir whiskyfun_archive_2012_2025 --start-year 2012 --end-year 2025 --sleep 0.5

Modes:
  discover --shallow: one homepage GET, extract all archive hrefs (fast, ~500 URLs).
  discover: optional BFS (--max-discover) to follow links; --probe adds canonical URL probes.
  crawl: reads JSONL (or archive_urls.jsonl if present), fetches each page, writes reviews_YYYY_MM.csv.

Segment caveat: review_date is the day header in HTML; slice boundaries follow file order
(see whiskyfun_pilot_scraper). robots.txt allows general access (verify before large runs).

TODO: optional Parquet; third day-header variant for rare pages; anchor-based dates.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import logging
import random
import re
import sys
import time
from collections import deque
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, TextIO
from urllib.parse import urljoin, urlparse

import csv
import requests
from bs4 import BeautifulSoup

from whiskyfun_pilot_scraper import (
    USER_AGENT,
    extract_reviews_from_day_fragment,
    split_html_by_day,
)

# Match relative or absolute archive HTML links in raw HTML.
ARCHIVE_LINK_RE = re.compile(
    r"(?i)(?:https?://(?:www\.)?whiskyfun\.com/)?"
    r"(archive(?:january|february|march|april|may|june|july|august|september|october|november|december)"
    r"\d{2}-\d+(?:-[a-zA-Z0-9\-]+)?\.html)",
)

# archivejanuary12-1.html or ArchiveJanuary12-1.html -> year 2012, month january, part 1
ARCHIVE_FILENAME_RE = re.compile(
    r"(?i)archive(january|february|march|april|may|june|july|august|september|october|november|december)(\d{2})-(\d+)",
)

MONTHS = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)

BASE = "https://www.whiskyfun.com/"
log = logging.getLogger("whiskyfun_archive")


def year_from_yy(yy: int) -> int:
    """Map two-digit archive year to full year (site range ~2002–2026)."""
    if yy >= 70:
        return 1900 + yy
    return 2000 + yy


def parse_archive_url_year(url: str) -> int | None:
    m = ARCHIVE_FILENAME_RE.search(url)
    if not m:
        return None
    return year_from_yy(int(m.group(2)))


def normalize_archive_url(href: str) -> str | None:
    href = (href or "").strip()
    if not href.lower().startswith("http"):
        href = urljoin(BASE, href)
    p = urlparse(href)
    if p.netloc.lower().replace("www.", "") != "whiskyfun.com":
        return None
    path = p.path or ""
    if not path.lower().endswith(".html"):
        return None
    low = path.lower()
    if "/archive" not in low and not low.startswith("/archive"):
        if "archive" not in low:
            return None
    # Slug paths are case-sensitive on Apache (e.g. ...-Port-Ellen-...); preserve path casing.
    return f"{p.scheme or 'https'}://{p.netloc}{path}"


def extract_archive_urls_from_html(html_text: str) -> set[str]:
    found: set[str] = set()
    for m in ARCHIVE_LINK_RE.finditer(html_text):
        n = normalize_archive_url(m.group(0))
        if n:
            found.add(n)
    soup = BeautifulSoup(html_text, "html.parser")
    for a in soup.find_all("a", href=True):
        n = normalize_archive_url(a["href"])
        if n and re.search(r"archive(?:january|february|march|april|may|june|july|august|september|october|november|december)\d{2}-\d+", n, re.I):
            found.add(n)
    return found


def fetch_page(
    url: str,
    *,
    timeout: float = 30.0,
    pause: float = 1.0,
    max_retries: int = 4,
    jitter: float = 0.25,
) -> tuple[str, str] | None:
    """GET url; return (raw_html, title) or None after retries."""
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            r.raise_for_status()
            if not r.encoding or r.encoding.lower() == "iso-8859-1":
                r.encoding = r.apparent_encoding or "iso-8859-1"
            raw = r.text
            final_path = urlparse(r.url).path or "/"
            if "/archive" in url.lower() and final_path.rstrip("/") in ("", "/"):
                log.warning("archive URL followed redirects to site root: %s", url)
                time.sleep(pause + random.uniform(0, jitter))
                return None
            title_m = re.search(r"<title>([^<]*)</title>", raw, re.I)
            title = html.unescape(title_m.group(1).strip()) if title_m else ""
            time.sleep(pause + random.uniform(0, jitter))
            return raw, title
        except requests.RequestException as e:
            last_err = e
            wait = min(60.0, 2.0**attempt + random.uniform(0, 1))
            log.warning("fetch %s attempt %s/%s: %s", url, attempt + 1, max_retries, e)
            time.sleep(wait)
    log.error("fetch failed permanently: %s (%s)", url, last_err)
    return None


def _is_archive_page_url(url: str) -> bool:
    return bool(ARCHIVE_FILENAME_RE.search(url))


def discover_urls_bfs(
    *,
    seed_urls: list[str],
    max_pages: int = 800,
    pause: float = 0.8,
) -> list[str]:
    """Breadth-first crawl of same-host archive HTML links."""
    fetched: set[str] = set()
    out_set: set[str] = set()
    q: deque[str] = deque()

    for s in seed_urls:
        s = (s or "").strip()
        if not s:
            continue
        if s.rstrip("/") in ("https://www.whiskyfun.com", "http://www.whiskyfun.com", "https://whiskyfun.com"):
            q.append(BASE)
        else:
            n = normalize_archive_url(s)
            if n:
                q.append(n)
    if not q:
        q.append(BASE)

    while q and len(fetched) < max_pages:
        url = q.popleft()
        if url in fetched:
            continue
        res = fetch_page(url, pause=pause, max_retries=3)
        if not res:
            continue
        raw, _title = res
        fetched.add(url)
        if _is_archive_page_url(url):
            out_set.add(url)
        for nxt in extract_archive_urls_from_html(raw):
            if nxt not in fetched:
                q.append(nxt)
    # Sort stable: by year desc, month, part
    def sort_key(u: str) -> tuple:
        y = parse_archive_url_year(u) or 0
        m = ARCHIVE_FILENAME_RE.search(u)
        if not m:
            return (y, 0, 0, u)
        mon = m.group(1).lower()
        month = MONTHS.index(mon) if mon in MONTHS else 0
        part = int(m.group(3))
        return (y, month, part, u)

    return sorted(out_set, key=sort_key)


def probe_canonical_urls(
    years: Iterable[int],
    *,
    pause: float = 0.5,
) -> set[str]:
    """HEAD/GET short-form archive{month}{yy}-{1|2}.html if not already known."""
    found: set[str] = set()
    headers = {"User-Agent": USER_AGENT}
    for year in years:
        yy = year % 100
        for month in MONTHS:
            for part in (1, 2):
                path = f"archive{month}{yy:02d}-{part}.html"
                url = BASE + path
                try:
                    r = requests.get(url, headers=headers, timeout=20, stream=True)
                    ok = r.status_code == 200
                    r.close()
                except requests.RequestException:
                    ok = False
                if ok:
                    found.add(url if url.startswith("http") else normalize_archive_url(url) or url)
                time.sleep(pause + random.uniform(0, 0.15))
    return found


def filter_urls_by_year(urls: list[str], start_year: int | None, end_year: int | None) -> list[str]:
    if start_year is None and end_year is None:
        return urls
    out = []
    for u in urls:
        y = parse_archive_url_year(u)
        if y is None:
            continue
        if start_year is not None and y < start_year:
            continue
        if end_year is not None and y > end_year:
            continue
        out.append(u)
    return out


def review_date_in_range(d: date, since: date | None, until: date | None) -> bool:
    if since is not None and d < since:
        return False
    if until is not None and d > until:
        return False
    return True


def chunk_key_for_date(d: date) -> str:
    return f"{d.year:04d}_{d.month:02d}"


def load_processed(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def append_processed(path: Path, url: str) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(url + "\n")


def load_hashes(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def row_dedupe_hash(rec: dict) -> str:
    body = re.sub(r"\s+", " ", (rec.get("review_text") or "").strip())
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def crawl_archives(
    urls: list[str],
    out_dir: Path,
    *,
    since: date | None,
    until: date | None,
    pause: float,
    resume_file: Path,
    dedupe_file: Path,
    dry_run: bool = False,
) -> dict:
    """Process each archive URL; append rows to per-(year-month) CSV files."""
    out_dir.mkdir(parents=True, exist_ok=True)
    processed = load_processed(resume_file)
    seen_hashes = load_hashes(dedupe_file)

    stats = {
        "urls_total": len(urls),
        "urls_skipped_resume": 0,
        "urls_fetched": 0,
        "urls_failed": 0,
        "rows_written": 0,
        "rows_skipped_date": 0,
        "rows_duplicate": 0,
        "segments_total": 0,
        "pages_zero_segments": [],
        "pages_low_reviews": [],  # (url, count) count < 2 and segments>0
    }

    writers: dict[str, csv.DictWriter] = {}
    files_open: dict[str, TextIO] = {}
    dedupe_buffer: list[str] = []

    def get_writer(key: str) -> csv.DictWriter:
        if key not in writers:
            path = out_dir / f"reviews_{key}.csv"
            exists = path.is_file()
            f = open(path, "a", newline="", encoding="utf-8")
            files_open[key] = f
            fieldnames = [
                "whisky_name_raw",
                "review_text",
                "score",
                "review_date",
                "source_url",
                "dedupe_hash",
            ]
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            if not exists:
                w.writeheader()
            writers[key] = w
        return writers[key]

    try:
        for url in urls:
            if url in processed:
                stats["urls_skipped_resume"] += 1
                continue
            if dry_run:
                log.info("dry-run skip fetch %s", url)
                stats["urls_fetched"] += 1
                append_processed(resume_file, url)
                continue

            res = fetch_page(url, pause=pause, max_retries=4)
            if not res:
                stats["urls_failed"] += 1
                continue
            raw, title = res
            stats["urls_fetched"] += 1

            segments = split_html_by_day(raw)
            stats["segments_total"] += len(segments)
            if len(segments) == 0:
                stats["pages_zero_segments"].append(url)
                log.warning("zero day segments: %s | title=%s", url, title[:80])

            page_reviews = 0
            for seg_date, frag in segments:
                rows = extract_reviews_from_day_fragment(frag)
                for c in rows:
                    if not review_date_in_range(seg_date, since, until):
                        stats["rows_skipped_date"] += 1
                        continue
                    rec = {
                        "whisky_name_raw": c["whisky_name_raw"],
                        "review_text": c["review_text"],
                        "score": c["score"],
                        "review_date": seg_date.isoformat(),
                        "source_url": url,
                    }
                    dh = row_dedupe_hash(rec)
                    if dh in seen_hashes:
                        stats["rows_duplicate"] += 1
                        continue
                    seen_hashes.add(dh)
                    rec["dedupe_hash"] = dh
                    key = chunk_key_for_date(seg_date)
                    w = get_writer(key)
                    w.writerow(rec)
                    stats["rows_written"] += 1
                    dedupe_buffer.append(dh)
                    if len(dedupe_buffer) >= 500:
                        with dedupe_file.open("a", encoding="utf-8") as dfh:
                            dfh.write("\n".join(dedupe_buffer) + "\n")
                        dedupe_buffer.clear()
                    page_reviews += 1

            if len(segments) > 0 and page_reviews < 2:
                stats["pages_low_reviews"].append((url, page_reviews))

            append_processed(resume_file, url)
            for fh in files_open.values():
                fh.flush()

        if dedupe_buffer:
            with dedupe_file.open("a", encoding="utf-8") as dfh:
                dfh.write("\n".join(dedupe_buffer) + "\n")
            dedupe_buffer.clear()
    finally:
        for f in files_open.values():
            f.close()

    return stats


def discover_shallow_homepage(*, pause: float) -> list[str]:
    """Single GET of homepage; all archive links (typically ~200+)."""
    res = fetch_page(BASE, pause=pause, max_retries=4)
    if not res:
        log.error("homepage fetch failed")
        return []
    raw, _title = res
    urls = extract_archive_urls_from_html(raw)

    def sort_key(u: str) -> tuple:
        y = parse_archive_url_year(u) or 0
        m = ARCHIVE_FILENAME_RE.search(u)
        if not m:
            return (y, 0, 0, u)
        mon = m.group(1).lower()
        month = MONTHS.index(mon) if mon in MONTHS else 0
        part = int(m.group(3))
        return (y, month, part, u)

    return sorted(urls, key=sort_key)


def cmd_discover(args: argparse.Namespace) -> None:
    if getattr(args, "shallow", False):
        urls = discover_shallow_homepage(pause=args.sleep)
        log.info("shallow discover: %s URLs from homepage", len(urls))
    else:
        seeds = [BASE] + ([args.extra_seed] if args.extra_seed else [])
        urls = discover_urls_bfs(seed_urls=seeds, max_pages=args.max_discover, pause=args.sleep)
    if args.probe:
        pyears = range(args.probe_start_year, args.probe_end_year + 1)
        extra = probe_canonical_urls(pyears, pause=max(0.2, args.sleep * 0.5))
        before = len(urls)
        urls = sorted(set(urls) | extra)
        log.info("probe added %s urls (total %s)", len(urls) - before, len(urls))

    out_path = Path(args.urls_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for u in urls:
            y = parse_archive_url_year(u)
            f.write(json.dumps({"url": u, "archive_year": y}, ensure_ascii=False) + "\n")
    print(f"Wrote {len(urls)} URLs -> {out_path}")


def cmd_crawl(args: argparse.Namespace) -> None:
    out_dir = Path(args.out_dir)
    resume_file = out_dir / args.resume_file
    dedupe_file = out_dir / args.dedupe_file

    urls: list[str] = []
    if args.urls_file:
        urls_path = Path(args.urls_file)
        if not urls_path.is_file():
            log.error("URLs file not found: %s", urls_path)
            sys.exit(1)
        for line in urls_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                urls.append(obj["url"])
            except json.JSONDecodeError:
                urls.append(line)
    else:
        default_list = Path("archive_urls.jsonl")
        if default_list.is_file():
            for line in default_list.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    urls.append(json.loads(line)["url"])
                except (json.JSONDecodeError, KeyError):
                    urls.append(line)
        else:
            log.info("no archive_urls.jsonl; discovering via BFS from homepage")
            urls = discover_urls_bfs(seed_urls=[BASE], max_pages=args.max_discover, pause=args.sleep)

    urls = filter_urls_by_year(urls, args.start_year, args.end_year)

    since = until = None
    if args.since:
        p = [int(x) for x in args.since.split("-")]
        since = date(p[0], p[1], p[2])
    if args.until:
        p = [int(x) for x in args.until.split("-")]
        until = date(p[0], p[1], p[2])

    stats = crawl_archives(
        urls,
        out_dir,
        since=since,
        until=until,
        pause=args.sleep,
        resume_file=resume_file,
        dedupe_file=dedupe_file,
        dry_run=args.dry_run,
    )

    csv_files: dict[str, int] = {}
    for p in sorted(out_dir.glob("reviews_*.csv")):
        try:
            csv_files[p.name] = max(0, sum(1 for _ in p.open(encoding="utf-8")) - 1)
        except OSError:
            csv_files[p.name] = -1

    manifest = {
        "stats": stats,
        "out_dir": str(out_dir),
        "since": args.since,
        "until": args.until,
        "start_year": args.start_year,
        "end_year": args.end_year,
        "csv_files": csv_files,
    }
    man_path = out_dir / "crawl_manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=2))
    print(f"Manifest -> {man_path}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Whiskyfun archive discovery + batch crawl")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("discover", help="Discover archive URLs and write JSONL")
    d.add_argument("--urls-out", default="archive_urls.jsonl")
    d.add_argument("--sleep", type=float, default=0.85, help="Pause between requests during BFS")
    d.add_argument(
        "--shallow",
        action="store_true",
        help="Only parse links from one homepage fetch (fast); omit for BFS closure",
    )
    d.add_argument("--max-discover", type=int, default=800, help="Max fetches in BFS mode (ignored with --shallow)")
    d.add_argument("--probe", action="store_true", help="Also probe canonical month/part URLs")
    d.add_argument("--probe-start-year", type=int, default=2012)
    d.add_argument("--probe-end-year", type=int, default=2026)
    d.add_argument("--extra-seed", default=None, help="Extra seed URL for BFS")
    d.set_defaults(func=cmd_discover)

    c = sub.add_parser("crawl", help="Fetch archives and write chunked CSVs")
    c.add_argument(
        "--urls-file",
        default=None,
        help="JSONL from discover (default: archive_urls.jsonl if that file exists, else BFS from homepage)",
    )
    c.add_argument("--out-dir", default="whiskyfun_archive_out")
    c.add_argument("--sleep", type=float, default=1.0)
    c.add_argument("--start-year", type=int, default=None)
    c.add_argument("--end-year", type=int, default=None)
    c.add_argument("--since", default=None, help="Min review_date YYYY-MM-DD inclusive")
    c.add_argument("--until", default=None, help="Max review_date YYYY-MM-DD inclusive")
    c.add_argument("--resume-file", default="processed_urls.txt")
    c.add_argument("--dedupe-file", default="dedupe_hashes.txt")
    c.add_argument("--max-discover", type=int, default=800)
    c.add_argument("--dry-run", action="store_true", help="Mark URLs processed without HTTP GET")
    c.set_defaults(func=cmd_crawl)

    return p


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
