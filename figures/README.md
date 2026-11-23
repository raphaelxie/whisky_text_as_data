# `figures/`

## Canonical: `figures/v2/`

Written by `python -m analysis.models` and `python -m analysis.embeddings`
(each `.png` + `.pdf`):

| Figure | Written by | Manuscript copy |
| --- | --- | --- |
| `fig_corrected_model_comparison` | `analysis.models` | `fig1_model_comparison` (restyled export) |
| `fig_corrected_r2_by_scope` | `analysis.models` | `fig2_r2_by_scope` (restyled export) |
| `fig3_known_groups` | `analysis.models` | `fig3_known_groups` (identical) |
| `fig_corrected_category_dimensions` | `analysis.embeddings` | `fig4_category_dimensions` (identical) |
| `fig5_weat_effect_sizes` | `analysis.embeddings` | `fig5_weat_effect_sizes` (identical) |

All five manuscript figures are exported automatically into
`paper/tex_paper/figure/`. To redraw figures 3–5 from the saved tables
without refitting anything, run:

```bash
python -m analysis.models --plot-only
python -m analysis.embeddings --plot-only
```

## EDA figures: top level of `figures/`

`fig_eda_*` are outputs of `notebooks/w1_eda.ipynb`. They are exploratory and
outside the `analysis/` pipeline; cite `figures/v2/` for results.
