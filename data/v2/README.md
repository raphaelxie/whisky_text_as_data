# `data/v2/`: Primary Result Tables

Every file here is written by `python -m analysis.models` or
`python -m analysis.embeddings` (see the repository root `README.md` for the
full command sequence). If you delete this directory, running those two
commands regenerates it in full. Nothing in here should be hand-edited.

## Canonical files

| File | Written by | Role |
| --- | --- | --- |
| `corrected_ols_coefficients.csv` | `analysis.models` | Descriptive OLS coefficients, HC1 robust SEs, for both "All reviews" and "Tier 1 index-matched only" samples |
| `corrected_tier1_sensitivity.csv` | `analysis.models` | Sample size and adjusted R² for the full sample vs. the Tier 1 subsample |
| `corrected_scope_supplementary_variable_n.csv` | `analysis.models` | Supplementary per-scope variable counts backing the R²-by-scope comparison |
| `corrected_independent_group_validation.csv` | `analysis.models` | Known-groups validation (Islay/peat, sherry, bourbon/oak, high/low score) |
| `corrected_predictive_comparison.csv` | `analysis.models` | Out-of-fold five-model comparison (dictionary, VADER, TF-IDF/Ridge, etc.) |
| `corrected_close_reading_vignettes.csv` | `analysis.models` | Candidate reviews for qualitative close reading |
| `corrected_ambiguous_term_model_sensitivity.csv` | `analysis.models` | Sensitivity of the predictive comparison to ambiguous-term allocation |
| `corrected_ambiguous_term_validation_sensitivity.csv` | `analysis.models` | Sensitivity of known-groups validation to ambiguous-term allocation |
| `corrected_ambiguous_term_embedding_sensitivity.csv` | `analysis.embeddings` | Sensitivity of embedding projections to ambiguous-term allocation |
| `corrected_embedding_pole_exclusions.csv` | `analysis.embeddings` | Pole terms excluded from each category's own dimension projection |
| `corrected_embedding_frequency_weighted_means.csv` | `analysis.embeddings` | Frequency-weighted category projections (sensitivity variant of `w3_category_dimension_means.csv`) |
| `corrected_embedding_stability.csv` / `.json` | `analysis.embeddings` | The prespecified 30-run embedding stability analysis and its summary |
| `w3_dimension_projections.csv` | `analysis.embeddings` | Term-level cosine projections onto the four cultural dimensions |
| `w3_category_dimension_means.csv` | `analysis.embeddings` | Category-level mean projections (pole terms excluded) |
| `w3_neighbor_audit.csv` | `analysis.embeddings` | Nearest-neighbor audit of the trained Word2Vec space |
| `w3_weat_results.csv` | `analysis.embeddings` | WEAT effect sizes with Holm-corrected p-values |
| `w4_table1_descriptive_stats.csv` | `analysis.models` | Publication Table 1: corpus descriptive statistics |
| `whiskyfun_dict_features.parquet` | `analysis.models` | Per-review dictionary feature matrix (input cache) |
| `whiskyfun_tokenized.parquet` | `analysis.models` | Tokenized corpus (input cache) |

Three files above are intentionally empty (1 byte, header-only with no rows):
`corrected_ambiguous_term_embedding_sensitivity.csv`,
`corrected_ambiguous_term_model_sensitivity.csv`, and
`corrected_ambiguous_term_validation_sensitivity.csv`. This means no
ambiguous term met that check's inclusion criteria this run, not that the
file is broken or truncated.

## Publication-table aliases

The `w4_table*` files are the exact publication numbering used in the
manuscript. Most are byte-for-byte copies of a `corrected_*`/`w3_*` file
above, written a second time under the paper's table numbers so the
manuscript can cite stable table names:

| Publication table | Identical to |
| --- | --- |
| `w4_table2_model_comparison.csv` | `corrected_predictive_comparison.csv` |
| `w4_table5_known_groups.csv` | `corrected_independent_group_validation.csv` |
| `w4_table6_dimension_projections.csv` | `w3_category_dimension_means.csv` |
| `w4_table7_weat_results.csv` | `w3_weat_results.csv` |

Two publication tables are **not** identical copies:

- `w4_table3_regression_coefficients.csv` is the "All reviews" rows only
  (12 rows) filtered out of `corrected_ols_coefficients.csv` (24 rows, which
  also includes the Tier 1 subsample).
- `w4_table4_r2_by_scope.csv` has no `corrected_*` twin; it is the primary
  half of the scope comparison, and its supplementary half is
  `corrected_scope_supplementary_variable_n.csv`.

## Removed

Ten `w2_*.csv` files and `w3_weat_term_scores.csv` used to sit in this
directory. They were stranded outputs of the superseded week notebooks, which
nothing in `analysis/` regenerates, and were deleted in the November 2026
cleanup. They remain in git history before that cleanup; do not cite their
numbers.
