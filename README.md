# Making Expert Taste Computable

This repository contains a reproducible computational-sociology study of
expert valuation in Whiskyfun Scottish malt reviews from 2012-2025. It uses
theory-guided text measurement and distributional semantics to study how
specialized tasting discourse makes sensory qualities comparable and
evaluable. The publication analysis uses scripted, tested computations;
notebooks present or preserve the analytical history.

## Publication Goal

The primary target is *Poetics: Journal of Empirical Research on Culture,
the Media and the Arts* (submit by August 1, 2026). Backup venues in order:
*Big Data & Society*, *Socius*, ICWSM 2027. The planned article is not a
score-prediction paper and not a general account of whisky consumers. It
treats expert whisky reviewing as a bounded case in the sociology of
cultural valuation — examining how a specialized evaluative community
constructs comparability and legitimacy through tasting discourse.

**Working title:** *Making Expert Taste Computable: Symbolic Boundaries and
the Discursive Production of Value in Whisky Reviews*

The Poetics contribution has three parts:

1. A substantive finding in the sociology of cultural valuation: defect
   vocabulary and a Natural/Artificial semantic axis identify a stable
   symbolic boundary in this expert corpus, consistent with cultural-field
   theories of legitimate versus illegitimate production.
2. An empirical demonstration that domain-specific evaluative categories
   derived from expert tasting discourse carry evaluative signal beyond
   generic sentiment, supporting theories of specialized cultural competence
   and field-specific valuation logics.
3. A methodological contribution for empirical cultural sociology: a
   reproducible workflow for constructing interpretable, theory-grounded
   measurement instruments from expert cultural discourse.

See `paper/REFRAMING_MEMO_POETICS.md` for the active Poetics-primary
submission blueprint and summer 2026 revision plan,
`theoretical_framework.md` for the sociology-to-measurement argument, and
`llm-council/runs/venue-selection-2026/final-plan.md` for the full venue
strategy analysis.

## Corrected Corpus

The analytical dataset contains 11,149 reviews from 146 assigned distilleries.
Name matching supplies 8,492 reviews (76.2%), while direct index matching
supplies 2,657 reviews (23.8%). The score mean is 86.226 and the median is 87.
The generated corpus audit and score-leakage checks are in
`data/qa_corpus_summary.json` and `data/qa_score_markers.csv`.

Processed review text remains included for replication with attribution to
[Whiskyfun](https://www.whiskyfun.com/). This repository does not assert that
redistribution permission has been obtained; see
`DATA_USE_AND_ATTRIBUTION.md`.

## Version 2 Measurement Status

Version 1 is retained as historical evidence, but it is superseded for primary
interpretation because it mixed fruit, floral, herbal/tea, and spice terms and
did not preserve a complete approval trail. Version 2 uses eleven primary
constructs: it separates fruit, floral, and spice, omits herbal/tea as too
minor for this study's theory, replaces the former sherry/rancio construct with
`sherry_influence`, whose berry and dried-fruit candidates require explicit
adjudication, excludes or documents context-dependent terms, and
is frozen as the primary instrument (`data/whiskyfun_dictionary_v2.json`).
Superseded Version 1 tables and notebooks live under `_local/archive/v1/`
(local only, not tracked in git).

## Canonical Workflow

Run from the repository root:

```bash
python whiskyfun_build_analytical_dataset.py
python -m analysis.qa
# Produces concordances and frequencies only; review this worksheet manually.
python -m analysis.dictionary candidate
# Run after completing every decision, rationale, and reviewer status cell.
python -m analysis.dictionary freeze
python -m analysis.models
python -m analysis.embeddings
python -m analysis.assemble
python -m pytest -q -p no:cacheprovider \
  test_whiskyfun_build_analytical_dataset.py \
  pipeline/test_whiskyfun_parse_utils.py \
  test_analysis.py
```

The candidate command refuses to overwrite an existing adjudication worksheet;
use the generated `data/dictionary_v2_adjudication.csv` in this repository for
ongoing review. Its `--overwrite` flag is only for deliberately restarting
that review.

To add terms before review, edit candidate definitions in
`analysis/dictionary.py`, regenerate the CSV, and rerun the review notebook.
Do not edit `notebooks/v2_dictionary_review.ipynb` to alter category contents;
it is a presentation artifact that reads the generated worksheet.

The three final analysis commands deliberately fail until a completed approval
worksheet has been frozen to `data/whiskyfun_dictionary_v2.json`. Once frozen,
they write primary artifacts under `data/v2/` and `figures/v2/`. The embedding
command performs the prespecified deterministic 30-run stability analysis. For
a quick development-only run, use `python -m analysis.embeddings
--skip-stability`.

## Outputs

- `paper/final_paper.md`: assembled working manuscript from V2 results (`python -m analysis.assemble`); theory-first restructuring for Poetics in progress.
- `paper/REFRAMING_MEMO_POETICS.md`: active Poetics-primary submission blueprint and summer 2026 revision plan.
- `paper/REFRAMING_MEMO_JCSS.md`: superseded JCSS manuscript blueprint; retained for development provenance.
- `paper/references.bib`: single bibliography source.
- `paper/source_log.md`: citation verification and use log.
- `data/DATASET.md`: generated corpus-construction memo.
- `data/whiskyfun_analytical_dataset.csv`, `data/whiskyfun_tokenized.parquet`: shared corpus inputs.
- `data/dictionary_v2_adjudication.csv`: term-level review worksheet with concordances and decisions.
- `data/dictionary_v2_ambiguous_terms.csv`: excluded-primary ambiguity register.
- `data/dictionary_v2_exclusions.csv`: construct-design exclusions from candidate generation.
- `data/whiskyfun_dictionary_v2.json`: authoritative frozen instrument.
- `data/dictionary_v2_provenance.csv`: frozen approval and frequency audit.
- `data/v2/` and `figures/v2/`: primary analysis tables, features, and figures.
- `_local/archive/v1/`: superseded V1 CSVs, figures, and notebooks (local archive).

## Analysis Design

The approved primary instrument is `data/whiskyfun_dictionary_v2.json`.
Descriptive OLS models report HC1 robust standard errors. Predictive model comparisons use the
same shuffled outer five-fold cross-validation splits, with text vectorization
and Ridge tuning confined to training folds. Validation groups use title or
assigned-distillery metadata rather than dictionary feature outcomes.

Embedding projections are cosine similarities, and category averages exclude
terms used to construct the corresponding pole. WEAT results report corrected
permutation p-values and Holm adjustment across the two primary tests.
Frequency-weighted category projections and ambiguous-term allocations are
labeled sensitivity analyses. The `Natural_Artificial` result is interpreted
as a robust boundary within this corpus, not as a universal structure of taste
or an observed effect on consumers.

## Notebooks

Active notebooks in `notebooks/`:

- `w0_preproc_phrases.ipynb`, `w0_preproc_bigrams.ipynb`: preprocessing provenance.
- `w1_eda.ipynb`: exploratory analysis on the shared corpus and V2 features.
- `v2_dictionary_review.ipynb`: adjudication worksheet presentation and checks.
- `w2_analysis.ipynb`, `w3_analysis.ipynb`, `w4_analysis.ipynb`: step-by-step
  reproduction of regression, embedding, and publication-table results.

Week notebooks remain in `notebooks/` for step-by-step reproduction. Archived
V1 **data and figures** live under `_local/archive/v1/`; publication tables
and figures are regenerated by the `analysis/` modules into `data/v2/` and
`figures/v2/`.

> **Note for notebook users.** All week notebooks (`w1_eda` through `w4`)
> now read from and write to **V2 paths** (`data/whiskyfun_dictionary_v2.json`,
> `data/v2/whiskyfun_dict_features.parquet`, `data/v2/`). Do **not** run
> `w1_dict_build.ipynb` or `w1_dict_features.ipynb` to reproduce V2 results —
> those are V1-era notebooks whose outputs are already superseded. The correct
> starting notebook is `w1_eda.ipynb`, followed by `w2_analysis.ipynb`,
> `w3_analysis.ipynb`, and `w4_analysis.ipynb` in order.
