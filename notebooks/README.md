# `notebooks/`

Notebooks preserve provenance and present results; they are not
authoritative. Every number in the manuscript comes from the scripted
commands in `analysis/` (see the repository root `README.md`).

| Notebook | Role |
| --- | --- |
| `w0_preproc_phrases.ipynb` | Builds `data/whiskyfun_phrases.json` and the initial tokenized parquet |
| `w0_preproc_bigrams.ipynb` | Builds `data/whiskyfun_bigrams.json`; updates the tokenized parquet |
| `w1_eda.ipynb` | Exploratory analysis on the shared corpus and V2 features; writes the `fig_eda_*` figures |
| `v2_dictionary_review.ipynb` | Adjudication worksheet presentation and checks for the V2 dictionary |
| `corrected_results.ipynb` | Presentation notebook that reads and displays the current `analysis/` outputs |

The course-era week notebooks (`w1_dict_build`, `w1_dict_features`,
`w2_analysis`, `w3_analysis`, `w4_analysis`) were removed in the November 2026
cleanup; they were superseded by `analysis.dictionary`, `analysis.models`, and
`analysis.embeddings`. They remain recoverable from git history (for example
`git show 731db76:notebooks/w3_analysis.ipynb`).
