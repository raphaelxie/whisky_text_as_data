#!/usr/bin/env python3
"""
Spot-check cleaned archive CSVs (plan: 2017-12, 2018-01, 2023-12).

Quick sanity check: row counts vs raw, first few cleaned names, no Angus-prefixed names left
in 2023-12. Not a substitute for full data QA.

Run after:

  python whiskyfun_clean_archive.py --in-dir whiskyfun_archive_2012_2025 \\
      --out-dir whiskyfun_archive_2012_2025_clean

Optional full re-crawl is not required once cleaning is applied; re-run
`whiskyfun_archive_crawl.py crawl` only if you need fresh HTML from the site
(e.g. pages changed) — the parser in whiskyfun_pilot_scraper.py is fixed for
new scrapes regardless.
"""

from __future__ import annotations

import csv
from pathlib import Path


def count_rows(path: Path) -> int:
    if not path.is_file():
        return -1
    with path.open(encoding="utf-8", newline="") as f:
        return max(0, sum(1 for _ in f) - 1)


def sample_names(path: Path, n: int = 3) -> list[str]:
    with path.open(encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        out: list[str] = []
        for i, row in enumerate(r):
            if i >= n:
                break
            out.append((row.get("whisky_name_raw") or "")[:100])
        return out


def main() -> None:
    base = Path(__file__).resolve().parent
    raw = base / "whiskyfun_archive_2012_2025"
    clean = base / "whiskyfun_archive_2012_2025_clean"
    for name in ("reviews_2017_12.csv", "reviews_2018_01.csv", "reviews_2023_12.csv"):
        rp, cp = raw / name, clean / name
        print(f"{name}: raw_rows={count_rows(rp)} clean_rows={count_rows(cp)}")
        print(f"  first names (clean): {sample_names(cp)}")
    angus_in_names = 0
    p12 = clean / "reviews_2023_12.csv"
    if p12.is_file():
        with p12.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                n = (row.get("whisky_name_raw") or "").lower()
                if n.startswith("angus"):
                    angus_in_names += 1
        print(f"reviews_2023_12.csv rows with whisky_name starting 'angus': {angus_in_names}")


if __name__ == "__main__":
    main()
