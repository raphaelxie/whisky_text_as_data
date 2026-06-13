#!/usr/bin/env python3
"""
Build data/whiskyfun_analytical_dataset.csv from pipeline intermediate CSVs.

Implements the two-tier inclusion strategy (index-matched + name-matched), alias
normalization, -Glenlivet stripping, score-leakage removal, title-prefix stripping,
and Nose/Mouth/Finish/Comments section parsing.

Usage (from project root):
  python whiskyfun_build_analytical_dataset.py \\
      --matched pipeline/whiskyfun_scottish_malts_matched_reviews.csv \\
      --index-pages pipeline/whiskyfun_scottish_malts_index_pages.csv \\
      --out data/whiskyfun_analytical_dataset.csv \\
      --readme data/DATASET.md
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

_ROOT = Path(__file__).resolve().parent
_PIPELINE_DIR = _ROOT / "pipeline"
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

from whiskyfun_parse_utils import SGP_POINTS_TAIL, normalize_ws

# --- inclusion constants (must match whiskyfun_scottish_malts_index.py) ---
PT_NAMED_DISTILLERY = "named_scottish_malt_distillery"
PT_NAMED_SECTION = "named_scottish_malt_section"
AUX_TYPES: Final[frozenset[str]] = frozenset(
    {
        "auxiliary_other_whisky",
        "auxiliary_undisclosed_vatted",
        "auxiliary_blend",
        "auxiliary_grain",
    }
)

YEAR_MIN, YEAR_MAX = 2012, 2025
SCORE_VALUE = r"(?:100|[1-9]?\d)(?:\s*(?:[-–/]|or)\s*(?:100|[1-9]?\d))?\+?(?:\s*/\s*100)?"
HIGH_SCORE_VALUE = r"(?:100|[6-9]\d)(?:\s*(?:[-–/]|or)\s*(?:100|[6-9]\d))?\+?(?:\s*/\s*100)?"
SCORE_TOKEN = rf"\b{SCORE_VALUE}\b(?!\s*(?:%|°|yo\b|years?\b|bottles?\b))"
HIGH_SCORE_TOKEN = rf"\b{HIGH_SCORE_VALUE}\b(?!\s*(?:%|°|yo\b|years?\b|bottles?\b|€|£))"
LABELED_SCORE_TOKEN = rf"\b{SCORE_VALUE}\b\s*%?(?!\s*(?:yo\b|years?\b|bottles?\b))"
LABELED_HIGH_SCORE_TOKEN = rf"\b{HIGH_SCORE_VALUE}\b\s*%?(?!\s*(?:yo\b|years?\b|bottles?\b|€|£))"
CONTEXTUAL_SCORE_PATTERNS = {
    "score_label_numeric": re.compile(
        rf"\b(?:scores?|scored?|ratings?|rated?)\b[^.!?\n]{{0,45}}?{LABELED_SCORE_TOKEN}",
        re.IGNORECASE,
    ),
    "numeric_score_label": re.compile(
        rf"{SCORE_TOKEN}[^.!?\n]{{0,45}}?\b(?:scores?|ratings?|points?|pointers?)\b",
        re.IGNORECASE,
    ),
    "personal_score_action": re.compile(
        rf"\b(?:I\s+(?:had|have)\s+it\s+at|worth|fetch(?:ed|es)?|hit(?:s|ting)?|"
        rf"(?:I(?:'ll| will)|we(?:'ll| will))\s+(?:say|go\s+for)|go(?:es|ing)?\s+(?:above|over|to))"
        rf"\s*(?:more\s+than\s+|north\s+of\s+|around\s+|approx(?:imately)?\s+|a\s+|the\s+|"
        rf"measly\s+|solid\s+)*{HIGH_SCORE_TOKEN}",
        re.IGNORECASE,
    ),
    "personal_percent_score": re.compile(
        rf"\b(?:I\s+(?:had|have)\s+it\s+at|worth|fetch(?:ed|es)?|"
        rf"(?:I(?:'ll| will)|we(?:'ll| will))\s+(?:say|go\s+for))"
        rf"\s*(?:more\s+than\s+|north\s+of\s+|around\s+|approx(?:imately)?\s+|a\s+|the\s+|"
        rf"measly\s+|solid\s+)*{LABELED_HIGH_SCORE_TOKEN}",
        re.IGNORECASE,
    ),
    "personal_score_sequence": re.compile(
        rf"\bI\s+(?:had|have)\s+it\s+at\b[^.!?\n]{{0,70}}?{LABELED_HIGH_SCORE_TOKEN}",
        re.IGNORECASE,
    ),
    "numeric_in_tasting_book": re.compile(
        rf"{HIGH_SCORE_TOKEN}[^.!?\n]{{0,30}}?\b(?:in|for)\s+my\s+(?:little\s+|wee\s+|tasting\s+)?"
        r"(?:book|system)\b",
        re.IGNORECASE,
    ),
    "score_threshold": re.compile(
        rf"\b(?:approach(?:ing)?|over|above|under)\s+(?:the\s+)?{HIGH_SCORE_TOKEN}"
        r"(?:\s*[-–]?\s*(?:mark|hurdle)|\+)?",
        re.IGNORECASE,
    ),
}

OUTPUT_FIELDS: Final[list[str]] = [
    "dedupe_hash",
    "whisky_name_raw",
    "distillery",
    "score",
    "review_date",
    "review_year",
    "source_url",
    "review_text",
    "identity_status",
    "match_source",
    "review_length",
    "nose",
    "mouth",
    "finish",
    "comments",
    "nmf",
]


def load_distillery_names(index_pages_path: Path) -> list[str]:
    names: list[str] = []
    with index_pages_path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("page_type") in (PT_NAMED_DISTILLERY, PT_NAMED_SECTION):
                n = (row.get("index_distillery") or "").strip()
                if n:
                    names.append(n)
    # Longest first for greedy matching
    return sorted(set(names), key=len, reverse=True)


def strip_hyphen_glenlivet_suffix(s: str) -> str:
    """
    Remove historical '-Glenlivet' / '- Glenlivet' suffix after a letter
    (e.g. Glenfarclas-Glenlivet -> Glenfarclas). Does not remove 'Braes of Glenlivet'.
    """
    return re.sub(r"(?<=[A-Za-z])[-–]\s*Glenlivet\b", "", s, flags=re.IGNORECASE)


def apply_alias_normalization(s: str) -> str:
    """
    Normalize bottle text for distillery matching only (original whisky_name_raw is kept
    in the output row).
    """
    out = s

    # Literal / phrase replacements (longer / more specific first where needed)
    replacements: list[tuple[str, str]] = [
        ("Glengarioch", "Glen Garioch"),
        ("GLENGARIOCH", "Glen Garioch"),
        ("St. Magdalene", "St-Magdalene"),
        ("St Magdalene", "St-Magdalene"),
        ("St-Magdalene", "St-Magdalene"),
        ("Glen Esk", "Glenesk"),
        ("Old Rhosdhu", "Loch Lomond"),
        ("Rhosdhu", "Loch Lomond"),
        # Index lists Octomore for Port Charlotte page
        ("Port Charlotte", "Octomore"),
    ]
    for old, new in replacements:
        if old in out:
            out = out.replace(old, new)

    out = strip_hyphen_glenlivet_suffix(out)

    # Pulteney -> Old Pulteney when not already "Old Pulteney"
    out = re.sub(r"(?<![Oo]ld )\bPulteney\b", "Old Pulteney", out)

    # Jura -> Isle of Jura when not already part of "Isle of Jura"
    out = re.sub(r"(?<!Isle of )\bJura\b", "Isle of Jura", out)

    # Lochnagar -> Royal Lochnagar when Royal not already present
    out = re.sub(r"(?<![Rr]oyal )\bLochnagar\b", "Royal Lochnagar", out)

    # Glenury (without Royal) -> Glenury Royal
    out = re.sub(r"\bGlenury\b(?!\s+[Rr]oyal)", "Glenury Royal", out)

    # Knockdhu / An Cnoc -> index form (avoid doubling if label already combined)
    if "An Cnoc/Knockdhu" not in out:
        out = re.sub(r"\bKnockdhu\b", "An Cnoc/Knockdhu", out)
        out = re.sub(r"\bAn Cnoc\b", "An Cnoc/Knockdhu", out)

    return out


def match_distillery_by_name(match_text: str, distilleries: list[str]) -> str | None:
    """Longest distillery name match at word boundaries (letters only)."""
    for d in distilleries:
        pat = r"(?<![a-zA-Z])" + re.escape(d) + r"(?![a-zA-Z])"
        if re.search(pat, match_text, re.IGNORECASE):
            return d
    return None


def strip_score_leakage(s: str) -> str:
    """Remove numerical score disclosures while retaining nonnumeric evaluation prose."""
    t = s
    t = SGP_POINTS_TAIL.sub("", t)
    # Full and malformed SGP score fields.
    t = re.sub(r"SGP\s*:?\s*\d*\s*[-–]\s*\d{0,3}\s*points?", "", t, flags=re.IGNORECASE)
    t = re.sub(r"SGP\s*:?\s*\d+", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\bWF\s*\d+\s*points\b", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\bWF\s*\d+\b", "", t, flags=re.IGNORECASE)
    # Narrative disclosures such as "93 point material" or "score of 94 out of 100".
    t = re.sub(
        r"\b(?:score|rating)\s*(?:is|was|of|:|at|around)?\s*"
        r"\d{1,3}(?:\s*(?:/|out\s+of)\s*100)?\b",
        "",
        t,
        flags=re.IGNORECASE,
    )
    t = re.sub(
        r"\b(?:around\s+|about\s+|an?\s+|mid[-\s]?|high[-\s]?|low[-\s]?)?"
        r"\d{1,3}(?:\s*[-–]\s*\d{1,3})?\s*(?:[-–]\s*)?point(?:s|er)?\b",
        "",
        t,
        flags=re.IGNORECASE,
    )
    # Redact values from looser score talk while retaining the surrounding discussion.
    for pattern in CONTEXTUAL_SCORE_PATTERNS.values():
        previous = None
        while previous != t:
            previous = t
            t = pattern.sub(
                lambda match: re.sub(LABELED_SCORE_TOKEN, "", match.group(0), flags=re.IGNORECASE),
                t,
            )
    return normalize_ws(t)


def strip_title_prefix(text: str, title: str) -> str:
    """Remove repeated bottle title from the start of review text when present."""
    t = normalize_ws(text)
    title_n = normalize_ws(title)
    if title_n and t.startswith(title_n):
        rest = t[len(title_n) :].strip()
        return rest if rest else t
    return t


def extract_sections(text: str) -> tuple[str, str, str, str, bool]:
    """
    Extract Nose, Mouth (or Palate), Finish, Comments.
    Returns (nose, mouth, finish, comments, sections_parsed).
    sections_parsed True when Nose, (Mouth or Palate), and Finish are all non-empty.
    """
    nose_m = re.search(r"\bNose\s*:", text, re.IGNORECASE)
    if not nose_m:
        return "", "", "", "", False

    def find_mouth_or_palate(start: int) -> re.Match[str] | None:
        tail = text[start:]
        return re.search(r"\b(?:Mouth\s*(?:\([^)]*\))?\s*:|Palate\s*:)", tail, re.IGNORECASE)

    mp_m = find_mouth_or_palate(nose_m.end())
    if not mp_m:
        return "", "", "", "", False
    mp_abs_start = nose_m.end() + mp_m.start()
    mp_abs_end = nose_m.end() + mp_m.end()

    tail_after_mouth = text[mp_abs_end:]
    finish_m = re.search(r"\bFinish\s*:", tail_after_mouth)
    if not finish_m:
        return "", "", "", "", False
    finish_abs_start = mp_abs_end + finish_m.start()
    finish_abs_end = mp_abs_end + finish_m.end()

    tail_after_finish = text[finish_abs_end:]
    comments_m = re.search(r"\bComments\s*:", tail_after_finish)

    nose_txt = text[nose_m.end() : mp_abs_start].strip()
    mouth_txt = text[mp_abs_end : finish_abs_start].strip()
    if comments_m:
        comments_abs_start = finish_abs_end + comments_m.start()
        comments_abs_end = finish_abs_end + comments_m.end()
        finish_txt = text[finish_abs_end : comments_abs_start].strip()
        comments_txt = text[comments_abs_end :].strip()
    else:
        finish_txt = text[finish_abs_end :].strip()
        comments_txt = ""

    ok = bool(nose_txt and mouth_txt and finish_txt)
    return nose_txt, mouth_txt, finish_txt, comments_txt, ok


def normalize_identity_status(raw: str, match_source: str) -> str:
    if match_source == "name":
        return "name_matched"
    r = (raw or "").strip()
    if r == "undisclosed_but_indexed_under_distillery":
        return "undisclosed_but_indexed"
    if r in ("explicit_distillery", "undisclosed_but_indexed"):
        return r
    if r == "unmatched" or not r:
        return "explicit_distillery"
    return r


def parse_year(review_date: str) -> str:
    d = (review_date or "").strip()
    if len(d) >= 4 and d[:4].isdigit():
        return d[:4]
    return ""


def valid_score(s: str) -> bool:
    return bool(s and s.strip().isdigit())


def year_in_range(review_date: str) -> bool:
    y = parse_year(review_date)
    if not y:
        return False
    yi = int(y)
    return YEAR_MIN <= yi <= YEAR_MAX


def row_is_tier1(row: dict[str, str]) -> bool:
    if (row.get("is_scottish_malt_indexed_strict") or "").upper() != "TRUE":
        return False
    pt = row.get("page_type") or ""
    return pt in (PT_NAMED_DISTILLERY, PT_NAMED_SECTION)


def row_is_tier2_candidate(row: dict[str, str]) -> bool:
    if (row.get("is_scottish_malt_indexed") or "").upper() != "FALSE":
        return False
    pt = row.get("page_type") or ""
    return pt not in AUX_TYPES


@dataclass
class BuildStats:
    corpus_rows: int = 0
    tier1: int = 0
    tier2: int = 0
    dropped_no_score: int = 0
    dropped_year: int = 0
    tier2_no_distillery: int = 0
    sections_parsed_true: int = 0


def build_rows(
    matched_path: Path,
    distilleries: list[str],
    stats: BuildStats,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen_hash: set[str] = set()

    with matched_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            stats.corpus_rows += 1
            if not valid_score(row.get("score") or ""):
                stats.dropped_no_score += 1
                continue
            if not year_in_range(row.get("review_date") or ""):
                stats.dropped_year += 1
                continue

            match_source: str | None = None
            distillery: str | None = None

            if row_is_tier1(row):
                match_source = "index"
                distillery = (row.get("index_distillery") or "").strip() or None
                if not distillery:
                    continue
            elif row_is_tier2_candidate(row):
                match_source = "name"
                norm_title = apply_alias_normalization(row.get("whisky_name_raw") or "")
                distillery = match_distillery_by_name(norm_title, distilleries)
                if not distillery:
                    stats.tier2_no_distillery += 1
                    continue
            else:
                continue

            if not distillery:
                continue

            dh = row.get("dedupe_hash") or ""
            if dh in seen_hash:
                continue
            seen_hash.add(dh)

            raw_text = row.get("text") or ""
            title = row.get("whisky_name_raw") or ""

            cleaned = strip_score_leakage(raw_text)
            cleaned = strip_title_prefix(cleaned, title)
            cleaned = normalize_ws(cleaned)

            nose, mouth, finish, comments, sections_ok = extract_sections(cleaned)
            nmf = normalize_ws(f"{nose} {mouth} {finish}".strip())
            if sections_ok:
                stats.sections_parsed_true += 1

            review_len = len(cleaned.split()) if cleaned else 0
            ident = normalize_identity_status(row.get("identity_status") or "", match_source)

            if match_source == "index":
                stats.tier1 += 1
            else:
                stats.tier2 += 1

            out.append(
                {
                    "dedupe_hash": dh,
                    "whisky_name_raw": title,
                    "distillery": distillery,
                    "score": str(int(row["score"])),
                    "review_date": (row.get("review_date") or "").strip(),
                    "review_year": parse_year(row.get("review_date") or ""),
                    "source_url": (row.get("source_url") or "").strip(),
                    "review_text": cleaned,
                    "identity_status": ident,
                    "match_source": match_source,
                    "review_length": str(review_len),
                    "nose": nose,
                    "mouth": mouth,
                    "finish": finish,
                    "comments": comments,
                    "nmf": nmf,
                }
            )

    return out


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def write_readme(path: Path, stats: BuildStats, n_out: int, n_distilleries: int) -> None:
    lines = [
        "# Whiskyfun analytical dataset",
        "",
        "This document describes how **`data/whiskyfun_analytical_dataset.csv`** was built for the project "
        "*Making Expert Taste Computable* (Whiskyfun Scottish malt reviews, 2012-2025).",
        "",
        "## Data sources",
        "",
        "- **Archive corpus**: Monthly HTML archives on whiskyfun.com were crawled and cleaned; rows live in "
        "`pipeline/whiskyfun_archive_2012_2025_clean/` and were joined with the Scottish Malts index.",
        "- **Scottish Malts index**: Distillery and section pages under the site’s Scottish Malts index were "
        "scraped (`pipeline/whiskyfun_scottish_malts_index.py`), producing "
        "`pipeline/whiskyfun_scottish_malts_index_pages.csv` and match metadata.",
        "- **Input to this script**: `pipeline/whiskyfun_scottish_malts_matched_reviews.csv` (full corpus rows plus "
        "index-matching diagnostics).",
        "",
        "## Inclusion: two-tier strategy",
        "",
        "### Tier 1 — `match_source=index`",
        "",
        "- `is_scottish_malt_indexed_strict == TRUE`",
        "- `page_type` is `named_scottish_malt_distillery` or `named_scottish_malt_section`",
        "- **Distillery** = `index_distillery` from Whiskyfun’s index (site classification, not legal disclosure).",
        "",
        "### Tier 2 — `match_source=name`",
        "",
        "- `is_scottish_malt_indexed == FALSE`",
        "- `page_type` is **not** an auxiliary index page (`auxiliary_other_whisky`, `auxiliary_blend`, "
        "`auxiliary_grain`, `auxiliary_undisclosed_vatted`)",
        "- **Distillery** = longest matching name from the Scottish Malts index list applied to "
        "`whisky_name_raw` after alias normalization and `-Glenlivet` stripping (see below).",
        "",
        "### Shared filters",
        "",
        "- Numeric **score** required (integer).",
        "- **review_date** year must be in **2012–2025**.",
        "- Rows are deduplicated by `dedupe_hash`.",
        "",
        "## Exclusion",
        "",
        "- Non–Scottish-malt rows that never match Tier 1 or Tier 2.",
        "- Tier 2 candidates with no distillery match after normalization.",
        "- Auxiliary index pages for Tier 2 (same as above).",
        "",
        "## Alias and normalization (Tier 2 matching only)",
        "",
        "Applied to a copy of the bottle title **before** word-boundary distillery matching:",
        "",
        "- `Glengarioch` → `Glen Garioch`",
        "- `St Magdalene` / `St. Magdalene` → `St-Magdalene`",
        "- `Glen Esk` → `Glenesk`",
        "- `Old Rhosdhu` / `Rhosdhu` → `Loch Lomond`",
        "- `Port Charlotte` → `Octomore` (index page label on whiskyfun.com)",
        "- Hyphenated **-Glenlivet** after a letter is stripped (e.g. `Glenfarclas-Glenlivet` → `Glenfarclas`); "
        "this is a historical regional suffix, not the Glenlivet distillery.",
        "- `Pulteney` → `Old Pulteney` when not already prefixed by `Old`",
        "- `Jura` → `Isle of Jura` when not already `Isle of Jura`",
        "- `Lochnagar` → `Royal Lochnagar` when not already `Royal Lochnagar`",
        "- `Glenury` → `Glenury Royal`",
        "- `Knockdhu` / `An Cnoc` → `An Cnoc/Knockdhu`",
        "",
        "**Word-boundary rule**: `(?<![a-zA-Z])` + escaped distillery name + `(?![a-zA-Z])`, case-insensitive; "
        "longest distillery name wins. This can still fail on unusual spellings; extend the alias table as needed.",
        "",
        "## Preprocessing on review text",
        "",
        "1. **Score leakage removal**: SGP / points / WF score patterns stripped (see `strip_score_leakage` in "
        "`whiskyfun_build_analytical_dataset.py`).",
        "2. **Title prefix removal**: leading `whisky_name_raw` removed from the body when it repeats the opening.",
        "3. **Section parsing**: `Nose:`, `Mouth:` (optional parenthetical) or `Palate:`, `Finish:`, `Comments:` — "
        "stored in `nose`, `mouth`, `finish`, `comments`; `nmf` = Nose + Mouth + Finish.",
        "",
        "## Output schema",
        "",
        "| Column | Description |",
        "|--------|-------------|",
        "| `dedupe_hash` | SHA-256 of normalized review body (corpus id) |",
        "| `whisky_name_raw` | Bottle line as in the matched CSV |",
        "| `distillery` | Assigned distillery (index or name match) |",
        "| `score` | Integer points |",
        "| `review_date` | ISO date |",
        "| `review_year` | Year (for FE) |",
        "| `source_url` | Archive page URL |",
        "| `review_text` | Cleaned full text |",
        "| `identity_status` | `explicit_distillery`, `undisclosed_but_indexed`, or `name_matched` |",
        "| `match_source` | `index` or `name` |",
        "| `review_length` | Word count of `review_text` |",
        "| `nose` / `mouth` / `finish` / `comments` | Parsed sections |",
        "| `nmf` | Sensory-only concatenation |",
        "",
        "Rows with empty `nose`/`mouth`/`finish` did not match the standard section structure; use full "
        "`review_text` for those analyses.",
        "",
        "## Build statistics (this run)",
        "",
        f"- Input rows scanned: **{stats.corpus_rows}**",
        f"- Tier 1 (index) rows in output: **{stats.tier1}**",
        f"- Tier 2 (name) rows in output: **{stats.tier2}**",
        f"- Output rows (deduped): **{n_out}**",
        f"- Distinct distilleries: **{n_distilleries}**",
        f"- Rows with all three sensory sections non-empty after parse: **{stats.sections_parsed_true}**",
        f"- Dropped (invalid/missing score): **{stats.dropped_no_score}**",
        f"- Dropped (date outside {YEAR_MIN}–{YEAR_MAX}): **{stats.dropped_year}**",
        f"- Tier 2 dropped (no distillery match): **{stats.tier2_no_distillery}**",
        "",
        "## Limitations",
        "",
        "- **Tier 2** assigns distillery by label text; undisclosed codes (e.g. some Elements of Islay) are only "
        "included if they appear under Tier 1 in the index.",
        "- **Aliases** are hand-curated; rare spellings may need new rules.",
        "- **Section parsing** misses non-standard formatting; use full `review_text` when `nose`/`mouth`/`finish` are empty.",
        "",
        "## Reproducibility",
        "",
        "```bash",
        "python whiskyfun_build_analytical_dataset.py \\",
        "  --matched pipeline/whiskyfun_scottish_malts_matched_reviews.csv \\",
        "  --index-pages pipeline/whiskyfun_scottish_malts_index_pages.csv \\",
        "  --out data/whiskyfun_analytical_dataset.csv \\",
        "  --readme data/DATASET.md",
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Build analytical whiskyfun dataset CSV + README.")
    ap.add_argument(
        "--matched",
        type=Path,
        default=_ROOT / "pipeline" / "whiskyfun_scottish_malts_matched_reviews.csv",
    )
    ap.add_argument(
        "--index-pages",
        type=Path,
        default=_ROOT / "pipeline" / "whiskyfun_scottish_malts_index_pages.csv",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=_ROOT / "data" / "whiskyfun_analytical_dataset.csv",
    )
    ap.add_argument("--readme", type=Path, default=_ROOT / "data" / "DATASET.md")
    args = ap.parse_args()

    if not args.matched.is_file():
        print(f"Missing --matched file: {args.matched}", file=sys.stderr)
        return 1
    if not args.index_pages.is_file():
        print(f"Missing --index-pages file: {args.index_pages}", file=sys.stderr)
        return 1

    distilleries = load_distillery_names(args.index_pages)
    stats = BuildStats()
    rows = build_rows(args.matched, distilleries, stats)
    write_csv(args.out, rows)

    n_dist = len({r["distillery"] for r in rows})
    write_readme(args.readme, stats, len(rows), n_dist)

    print(f"Wrote {args.out} ({len(rows)} rows)")
    print(f"Wrote {args.readme}")
    print(f"Tier1={stats.tier1} Tier2={stats.tier2} sections_ok={stats.sections_parsed_true}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
