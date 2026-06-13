# Whiskyfun analytical dataset

This document describes how **`data/whiskyfun_analytical_dataset.csv`** was built for the project *Making Expert Taste Computable* (Whiskyfun Scottish malt reviews, 2012-2025).

## Data sources

- **Archive corpus**: Monthly HTML archives on whiskyfun.com were crawled and cleaned; rows live in `pipeline/whiskyfun_archive_2012_2025_clean/` and were joined with the Scottish Malts index.
- **Scottish Malts index**: Distillery and section pages under the site’s Scottish Malts index were scraped (`pipeline/whiskyfun_scottish_malts_index.py`), producing `pipeline/whiskyfun_scottish_malts_index_pages.csv` and match metadata.
- **Input to this script**: `pipeline/whiskyfun_scottish_malts_matched_reviews.csv` (full corpus rows plus index-matching diagnostics).

## Inclusion: two-tier strategy

### Tier 1 — `match_source=index`

- `is_scottish_malt_indexed_strict == TRUE`
- `page_type` is `named_scottish_malt_distillery` or `named_scottish_malt_section`
- **Distillery** = `index_distillery` from Whiskyfun’s index (site classification, not legal disclosure).

### Tier 2 — `match_source=name`

- `is_scottish_malt_indexed == FALSE`
- `page_type` is **not** an auxiliary index page (`auxiliary_other_whisky`, `auxiliary_blend`, `auxiliary_grain`, `auxiliary_undisclosed_vatted`)
- **Distillery** = longest matching name from the Scottish Malts index list applied to `whisky_name_raw` after alias normalization and `-Glenlivet` stripping (see below).

### Shared filters

- Numeric **score** required (integer).
- **review_date** year must be in **2012–2025**.
- Rows are deduplicated by `dedupe_hash`.

## Exclusion

- Non–Scottish-malt rows that never match Tier 1 or Tier 2.
- Tier 2 candidates with no distillery match after normalization.
- Auxiliary index pages for Tier 2 (same as above).

## Alias and normalization (Tier 2 matching only)

Applied to a copy of the bottle title **before** word-boundary distillery matching:

- `Glengarioch` → `Glen Garioch`
- `St Magdalene` / `St. Magdalene` → `St-Magdalene`
- `Glen Esk` → `Glenesk`
- `Old Rhosdhu` / `Rhosdhu` → `Loch Lomond`
- `Port Charlotte` → `Octomore` (index page label on whiskyfun.com)
- Hyphenated **-Glenlivet** after a letter is stripped (e.g. `Glenfarclas-Glenlivet` → `Glenfarclas`); this is a historical regional suffix, not the Glenlivet distillery.
- `Pulteney` → `Old Pulteney` when not already prefixed by `Old`
- `Jura` → `Isle of Jura` when not already `Isle of Jura`
- `Lochnagar` → `Royal Lochnagar` when not already `Royal Lochnagar`
- `Glenury` → `Glenury Royal`
- `Knockdhu` / `An Cnoc` → `An Cnoc/Knockdhu`

**Word-boundary rule**: `(?<![a-zA-Z])` + escaped distillery name + `(?![a-zA-Z])`, case-insensitive; longest distillery name wins. This can still fail on unusual spellings; extend the alias table as needed.

## Preprocessing on review text

1. **Score leakage removal**: SGP / points / WF score patterns stripped (see `strip_score_leakage` in `whiskyfun_build_analytical_dataset.py`).
2. **Title prefix removal**: leading `whisky_name_raw` removed from the body when it repeats the opening.
3. **Section parsing**: `Nose:`, `Mouth:` (optional parenthetical) or `Palate:`, `Finish:`, `Comments:` — stored in `nose`, `mouth`, `finish`, `comments`; `nmf` = Nose + Mouth + Finish.

## Output schema

| Column | Description |
|--------|-------------|
| `dedupe_hash` | SHA-256 of normalized review body (corpus id) |
| `whisky_name_raw` | Bottle line as in the matched CSV |
| `distillery` | Assigned distillery (index or name match) |
| `score` | Integer points |
| `review_date` | ISO date |
| `review_year` | Year (for FE) |
| `source_url` | Archive page URL |
| `review_text` | Cleaned full text |
| `identity_status` | `explicit_distillery`, `undisclosed_but_indexed`, or `name_matched` |
| `match_source` | `index` or `name` |
| `review_length` | Word count of `review_text` |
| `nose` / `mouth` / `finish` / `comments` | Parsed sections |
| `nmf` | Sensory-only concatenation |

Rows with empty `nose`/`mouth`/`finish` did not match the standard section structure; use full `review_text` for those analyses.

## Build statistics (this run)

- Input rows scanned: **20704**
- Tier 1 (index) rows in output: **2657**
- Tier 2 (name) rows in output: **8492**
- Output rows (deduped): **11149**
- Distinct distilleries: **146**
- Rows with all three sensory sections non-empty after parse: **11117**
- Dropped (invalid/missing score): **650**
- Dropped (date outside 2012–2025): **0**
- Tier 2 dropped (no distillery match): **7478**

## Limitations

- **Tier 2** assigns distillery by label text; undisclosed codes (e.g. some Elements of Islay) are only included if they appear under Tier 1 in the index.
- **Aliases** are hand-curated; rare spellings may need new rules.
- **Section parsing** misses non-standard formatting; use full `review_text` when `nose`/`mouth`/`finish` are empty.

## Reproducibility

```bash
python whiskyfun_build_analytical_dataset.py \
  --matched pipeline/whiskyfun_scottish_malts_matched_reviews.csv \
  --index-pages pipeline/whiskyfun_scottish_malts_index_pages.csv \
  --out data/whiskyfun_analytical_dataset.csv \
  --readme data/DATASET.md
```
