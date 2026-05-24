#!/usr/bin/env python3
"""
Post-process whiskyfun archive CSVs: clean bottle titles, drop Angus header rows,
split multi-bottle cells, recompute dedupe hashes.

Pipeline (per input row):
  1) Drop rows whose whisky_name_raw is an "Angus's Corner…" banner (multi-bottle article;
     not representable as one bottle without heavy NLP).
  2) If review_text still contains several SGP score blocks, split into one row per bottle.
  3) Re-derive whisky_name_raw from the text-before-Colour using the same rules as the scraper.
  4) Normalize review_text prefix via rebuild_review_text so it aligns with the cleaned title.
  5) Recompute dedupe_hash from review_text (same definition as whiskyfun_archive_crawl).

Usage:
  python whiskyfun_clean_archive.py --in-dir whiskyfun_archive_2012_2025 \\
      --out-dir whiskyfun_archive_2012_2025_clean

Original CSVs are left unchanged unless you pass --in-place (writes a .tmp file then replaces).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

from whiskyfun_parse_utils import (
    extract_clean_bottle_title,
    extract_score_from_text,
    head_before_colour,
    is_angus_corner_header_row,
    rebuild_review_text,
    split_review_text_multi_sgp,
)


def row_dedupe_hash(review_text: str) -> str:
    """Must match whiskyfun_archive_crawl.row_dedupe_hash so re-crawls and cleans stay comparable."""
    body = re.sub(r"\s+", " ", (review_text or "").strip())
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def clean_one_row(row: dict[str, str]) -> list[dict[str, str]]:
    """
    Turn one CSV row into one or more cleaned rows.

    Angus banner rows are filtered earlier in process_csv. Here we only handle splits and
    title/body normalization. `name_in` is a fallback when a single segment yields no title
    from review_text alone.
    """
    name_in = row.get("whisky_name_raw") or ""
    text_in = row.get("review_text") or ""

    # One segment normally; multiple when one <td> held several full notes (each with SGP tail).
    parts = split_review_text_multi_sgp(text_in)
    out: list[dict[str, str]] = []
    for part in parts:
        h = head_before_colour(part)
        title, _low = extract_clean_bottle_title(h)
        # Rare: split succeeded but this segment’s head is odd; fall back to original name.
        if not title and len(parts) == 1:
            title, _low = extract_clean_bottle_title(head_before_colour(name_in))
            if not title:
                title = name_in.strip()
        if not title:
            continue
        # Drop garbage like a lone "S" from broken HTML spans (see plan §4).
        if len(title) < 2:
            continue
        text_out = rebuild_review_text(part, title)
        score = extract_score_from_text(text_out)
        out.append(
            {
                "whisky_name_raw": title,
                "review_text": text_out,
                "score": str(score) if score is not None else "",
                "review_date": row.get("review_date", ""),
                "source_url": row.get("source_url", ""),
                "dedupe_hash": row_dedupe_hash(text_out),
            }
        )
    return out


def process_csv(
    in_path: Path,
    out_path: Path,
    log_fh,
    *,
    in_place: bool,
) -> dict[str, int]:
    """
    Read one reviews_YYYY_MM.csv, write cleaned version, append JSONL events to log_fh.

    in_place: write to same basename via a temp file then os.replace, so a failed run does
    not truncate the original mid-write.
    """
    stats = {
        "rows_in": 0,
        "rows_out": 0,
        "dropped_angus_header": 0,
        "split_multi_sgp": 0,
        "dropped_empty": 0,
    }
    fieldnames = [
        "whisky_name_raw",
        "review_text",
        "score",
        "review_date",
        "source_url",
        "dedupe_hash",
    ]

    rows = list(csv.DictReader(in_path.open(encoding="utf-8", newline="")))

    def handle_row(row: dict[str, str], writer: csv.DictWriter) -> None:
        stats["rows_in"] += 1
        name_raw = row.get("whisky_name_raw") or ""
        # Entire row is editorial header + many bottles; cleaner drops it (see plan issue 2).
        if is_angus_corner_header_row(name_raw):
            stats["dropped_angus_header"] += 1
            log_fh.write(
                json.dumps(
                    {"event": "dropped_angus_header", "file": str(in_path), "preview": name_raw[:120]},
                    ensure_ascii=False,
                )
                + "\n"
            )
            return

        cleaned = clean_one_row(row)
        # One logical input row became N output rows (multi-SGP split).
        if len(cleaned) > 1:
            stats["split_multi_sgp"] += 1
            log_fh.write(
                json.dumps(
                    {
                        "event": "split_multi_sgp",
                        "file": str(in_path),
                        "n": len(cleaned),
                        "date": row.get("review_date"),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        if not cleaned:
            stats["dropped_empty"] += 1
            return
        for c in cleaned:
            writer.writerow({k: c.get(k, "") for k in fieldnames})
            stats["rows_out"] += 1

    if in_place:
        tmp = in_path.with_suffix(in_path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8", newline="") as outf:
            writer = csv.DictWriter(outf, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                handle_row(row, writer)
        tmp.replace(in_path)
        return stats

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as outf:
        writer = csv.DictWriter(outf, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            handle_row(row, writer)
    return stats


def main() -> None:
    p = argparse.ArgumentParser(description="Clean whiskyfun archive review CSVs.")
    p.add_argument("--in-dir", type=Path, default=Path("whiskyfun_archive_2012_2025"))
    p.add_argument("--out-dir", type=Path, default=Path("whiskyfun_archive_2012_2025_clean"))
    p.add_argument("--glob", default="reviews_*.csv", help="Input glob under in-dir")
    p.add_argument("--log", type=Path, default=None, help="JSONL QA log (default: out-dir/clean_qa.jsonl)")
    p.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite files in in-dir (writes .tmp then replace)",
    )
    args = p.parse_args()

    in_dir: Path = args.in_dir
    if not in_dir.is_dir():
        print(f"ERROR: in-dir not found: {in_dir}", file=sys.stderr)
        sys.exit(1)

    out_dir: Path = args.out_dir
    if args.in_place:
        log_path = args.log or (in_dir / "clean_qa.jsonl")
    else:
        out_dir.mkdir(parents=True, exist_ok=True)
        log_path = args.log or (out_dir / "clean_qa.jsonl")
    log_path.parent.mkdir(parents=True, exist_ok=True)

    totals = {
        "rows_in": 0,
        "rows_out": 0,
        "dropped_angus_header": 0,
        "split_multi_sgp": 0,
        "dropped_empty": 0,
    }

    paths = sorted(in_dir.glob(args.glob))
    if not paths:
        print(f"No files matching {args.glob!r} in {in_dir}", file=sys.stderr)
        sys.exit(2)

    # One JSON object per line: dropped_angus_header or split_multi_sgp (auditable QA trail).
    with log_path.open("w", encoding="utf-8") as log_fh:
        for in_path in paths:
            rel = in_path.name
            if args.in_place:
                st = process_csv(in_path, in_path, log_fh, in_place=True)
            else:
                st = process_csv(in_path, out_dir / rel, log_fh, in_place=False)
            for k in totals:
                totals[k] += st[k]
            print(f"{rel}: {st}")

    print(json.dumps({"totals": totals, "log": str(log_path)}, indent=2))


if __name__ == "__main__":
    main()
