"""Generate corpus construction and score-leakage quality assurance outputs."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

from analysis.common import DATA, ROOT, TEXT_SCOPES, ensure_dirs
from whiskyfun_build_analytical_dataset import CONTEXTUAL_SCORE_PATTERNS

MARKERS = {
    "numeric_points": re.compile(r"\b\d{1,3}(?:\s*[-–]\s*\d{1,3})?\s*points?\b", re.IGNORECASE),
    "numeric_score_phrase": re.compile(
        r"\b(?:score|rating)\s*(?:is|was|of|:|at|around)?\s*\d{1,3}\b", re.IGNORECASE
    ),
    "sgp_score_field": re.compile(r"\bSGP\s*:?\s*\d*\s*[-–]\s*\d{0,3}\s*points?\b", re.IGNORECASE),
    "wf_score_field": re.compile(r"\bWF\s*\d+\b", re.IGNORECASE),
    **CONTEXTUAL_SCORE_PATTERNS,
}


def count_markers(series: pd.Series, stage: str, scope: str) -> list[dict[str, object]]:
    text = series.fillna("").astype(str)
    rows = []
    for marker, pattern in MARKERS.items():
        rows.append({
            "stage": stage,
            "scope": scope,
            "marker": marker,
            "count": int(text.str.contains(pattern).sum()),
        })
    return rows


def corpus_summary(df: pd.DataFrame) -> dict[str, object]:
    match = df["match_source"].value_counts()
    identity = df["identity_status"].value_counts()
    sections = {scope: int(df[scope].fillna("").str.strip().ne("").sum()) for scope in TEXT_SCOPES}
    return {
        "rows": int(len(df)),
        "distilleries": int(df["distillery"].nunique()),
        "score": {
            "mean": round(float(df["score"].mean()), 3),
            "median": round(float(df["score"].median()), 3),
            "sd": round(float(df["score"].std()), 3),
            "min": int(df["score"].min()),
            "max": int(df["score"].max()),
        },
        "match_source": {
            key: {"n": int(value), "pct": round(float(value / len(df) * 100), 1)}
            for key, value in match.items()
        },
        "identity_status": {
            key: {"n": int(value), "pct": round(float(value / len(df) * 100), 1)}
            for key, value in identity.items()
        },
        "section_nonempty": sections,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DATA / "whiskyfun_analytical_dataset.csv")
    parser.add_argument("--matched", type=Path, default=ROOT / "pipeline" / "whiskyfun_scottish_malts_matched_reviews.csv")
    parser.add_argument("--output-dir", type=Path, default=DATA)
    args = parser.parse_args()
    ensure_dirs()
    df = pd.read_csv(args.dataset)
    raw = pd.read_csv(args.matched)
    included_raw = raw[raw["dedupe_hash"].isin(set(df["dedupe_hash"]))].copy()

    marker_rows = count_markers(included_raw["text"], "source_text_before_cleaning", "text")
    for scope in TEXT_SCOPES:
        marker_rows.extend(count_markers(df[scope], "analytical_text_after_cleaning", scope))
    markers = pd.DataFrame(marker_rows)
    summary = corpus_summary(df)
    summary["score_markers"] = marker_rows

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "qa_corpus_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    markers.to_csv(args.output_dir / "qa_score_markers.csv", index=False)
    post_primary = markers[
        (markers["stage"] == "analytical_text_after_cleaning")
        & (markers["scope"] == "review_text")
    ]["count"].sum()
    if post_primary:
        raise SystemExit(f"Primary review text retains {post_primary} numeric score-marker matches.")
    print(json.dumps(summary, indent=2))
    print(f"Wrote {args.output_dir / 'qa_corpus_summary.json'} and qa_score_markers.csv")


if __name__ == "__main__":
    main()
