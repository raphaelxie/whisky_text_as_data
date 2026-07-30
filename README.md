# Making Expert Taste Computable

A reproducible computational-sociology study of expert valuation in Whiskyfun
Scottish malt reviews, 2012–2025. It uses theory-guided text measurement and
distributional semantics to study how specialized tasting discourse makes
sensory qualities comparable and evaluable.

Every number that appears in the manuscript comes from scripted, tested
computations in `analysis/`. Notebooks preserve provenance and present results;
they are not authoritative.

## Project Status

This began as the final project for CSSS 594 (Computational Social Science).
**The course is finished.** The repository is now in submission preparation:
the analysis is frozen, and active work is theoretical development, reframing,
and copy-editing of the manuscript.

That transition is why the repository is large and layered. It holds two kinds
of material that are easy to confuse — a finished, reproducible analysis
pipeline, and an accumulation of course-era drafts, memos, and superseded
artifacts. [Repository Structure](#repository-structure) marks which is which,
and [Canonical Versus Superseded](#canonical-versus-superseded) is the quick
answer for "which version of this file do I trust?"

## Publication Plan

Two stages, one framing target.

1. **Text as Data (TADA) — submit by October 1, 2026.** A feedback checkpoint
   before journal submission. TADA is non-archival, so presenting there does
   not preclude a later journal submission; verify this against the current
   call for papers before submitting.
2. **_Poetics: Journal of Empirical Research on Culture, the Media and the
   Arts_ — submit after incorporating conference feedback.**

*Poetics* is the terminal target, so **all copy-editing, reframing, and
theoretical work is anchored to Poetics conventions**, not to conference
norms. Cultural sociology leads; computational measurement is the enabling
method, not the headline. The TADA submission uses the same framing rather
than a separate one.

The copy-edit pass is driven by `_feedback/`: written comments from the
professor and TA, plus two AI reviewer reports covering theory and
accessibility. `paper/REFRAMING_MEMO_POETICS.md` turns those into a working
checklist under "August–September 2026."

**Working title:** *Making Expert Taste Computable: Symbolic Boundaries and
the Discursive Production of Value in Whisky Reviews*

The planned article is not a score-prediction paper and not a general account
of whisky consumers. It treats expert whisky reviewing as a bounded case in
the sociology of cultural valuation — examining how a specialized evaluative
community constructs comparability and legitimacy through tasting discourse.
It makes three contributions:

1. **Substantive.** Defect vocabulary and a Natural/Artificial semantic axis
   identify a stable symbolic boundary in this expert corpus, consistent with
   cultural-field theories of legitimate versus illegitimate production.
2. **Measurement.** Domain-specific evaluative categories derived from expert
   tasting discourse carry evaluative signal beyond generic sentiment,
   supporting theories of specialized cultural competence and field-specific
   valuation logics.
3. **Methodological.** A reproducible workflow for constructing interpretable,
   theory-grounded measurement instruments from expert cultural discourse.

The full venue strategy, article outline, and revision plan live in
`paper/REFRAMING_MEMO_POETICS.md`. Its framing guidance is current; its
timeline and backup cascade are **stale** — they were written for a direct
August 1, 2026 Poetics submission and predate the TADA checkpoint.

## Where To Start

| If you want to… | Read |
| --- | --- |
| See the current manuscript | `paper/tex_paper/main.pdf` (32 pp.) |
| Understand the intended argument and venue strategy | `paper/REFRAMING_MEMO_POETICS.md` |
| Go deeper on theory | `paper/theoretical_framework_enriched.md` |
| See outstanding reviewer feedback | `_feedback/` |
| Reproduce the reported numbers | [Canonical Workflow](#canonical-workflow) |
| Understand how the corpus was built | `data/DATASET.md` |
| Understand how the instrument was built | `data/DICTIONARY_V2_PROTOCOL.md` and `data/dictionary_v2_approval_report.md` |

## Repository Structure

### Four layers

1. **Acquisition** — `pipeline/` and `whiskyfun_build_analytical_dataset.py`.
   Crawl, clean, index-match, and assemble the analytical corpus. This has
   already been run; you do not need to re-scrape to reproduce results. Its
   bulky inputs (671 cached HTML pages, 167 monthly archive CSVs) are excluded
   from version control.
2. **Measurement** — `analysis/dictionary.py` and the `data/dictionary_v2_*`
   files. Generates candidate terms, records human adjudication, and freezes
   the instrument.
3. **Analysis** — `analysis/qa.py`, `models.py`, `embeddings.py`, and
   `assemble.py`. Writes every reported table and figure into `data/v2/` and
   `figures/v2/`.
4. **Writing** — `paper/` and `_feedback/`. Local only; not published to
   GitHub.

`notebooks/` runs alongside these as provenance and presentation. `_local/` is
a historical archive of course-era material.

### Directory map

| Path | Contents | Version control |
| --- | --- | --- |
| `whiskyfun_build_analytical_dataset.py` | Builds `data/whiskyfun_analytical_dataset.csv` from pipeline match outputs: two-tier inclusion, alias normalization, score-leakage stripping, section parsing | tracked |
| `analysis/` | The authoritative computation layer: `common.py` (shared paths, tokenization, features), `qa.py`, `dictionary.py`, `models.py`, `embeddings.py`, `assemble.py` | tracked |
| `data/` | Analytical corpus, tokenized parquet, frozen instrument, adjudication records, QA output | tracked |
| `data/v2/` | Primary result tables and features (36 tracked files) | tracked |
| `figures/v2/` | Primary figures (3 figures, PNG + PDF) | tracked |
| `figures/` (top level) | Superseded notebook figures: `fig_eda_*` from `w1_eda`, `fig_w2_*`/`fig_w3_*`/`fig_w4_*` from the week notebooks | tracked |
| `notebooks/` | Preprocessing provenance, dictionary review, and step-by-step presentation of results | tracked |
| `pipeline/` | Scraper, cleaner, index matcher, parse utilities, and the one pytest suite | tracked; heavy artifacts ignored |
| `models/` | Trained Word2Vec (`w2v_whisky.model`, `w2v_whisky.kv`), regenerated by `analysis.embeddings` | **ignored** |
| `paper/` | LaTeX manuscript (`tex_paper/`), Poetics reframing memo, enriched theory framework | **ignored — local only** |
| `_feedback/` | Professor and TA feedback, plus two AI reviewer reports in `_AI_reviewer/`; drives the copy-edit pass | **ignored — local only** |
| `_local/` | Course-era archive: literature PDFs, weekly memos, old prompts, superseded drafts, presentation deck and build scripts, V1 data and figures | **ignored — local only** |

`.claude/`, `.cursor/`, `.pytest_cache/`, `__pycache__/`, `.frontend-slides/`,
and `skills-lock.json` are tooling or cache artifacts with no analytical
content. All are excluded from version control.

### Canonical versus superseded

The repository keeps its own history, which is the main source of confusion.
For anything that goes into the manuscript, use the left column.

| Use this | Not this |
| --- | --- |
| `data/whiskyfun_dictionary_v2.json` (247 terms, 11 categories) | The V1 dictionary, kept only in `_local/archive/v1/` |
| `analysis/` modules | `notebooks/w2_analysis.ipynb`, `w3_analysis.ipynb`, `w4_analysis.ipynb` |
| `data/v2/corrected_*.csv` and `w4_table*.csv` | `data/v2/w2_*.csv` and `w3_weat_term_scores.csv`, which are stranded notebook outputs no current module writes |
| `figures/v2/` | Top-level `figures/` |
| `notebooks/w1_eda.ipynb` | `notebooks/w1_dict_build.ipynb`, `w1_dict_features.ipynb` (V1-era) |
| `paper/tex_paper/main.tex` | `_local/paper_draft/` |
| `paper/REFRAMING_MEMO_POETICS.md` | `_local/presentation/REFRAMING_MEMO_JCSS.md` |

### Repository size

`.git` was 449 MB and is now 248 MB after a repack; 258 MB of that was loose,
unpacked objects. What remains splits two ways:

- **111 MB of real git history**, three quarters of which is tokenized parquet.
  Parquet is already compressed, so git cannot pack it further. Two of those
  parquets are no longer tracked — `data/whiskyfun_tokenized_phrases_only.parquet`
  (a backup nothing reads) and `data/v2/whiskyfun_tokenized.parquet` (regenerated
  by `analysis.models`) — but their blobs stay in history until it is rewritten.
- **136 MB in `.git/cursor/`**, which is Cursor's local checkpoint store, not
  git history. It is never pushed and can be deleted at the cost of losing
  Cursor's restore points.

Genuinely large files that stay tracked because replication needs them:
`data/whiskyfun_analytical_dataset.csv` (31 MB, the corpus),
`pipeline/whiskyfun_scottish_malts_matched_reviews.csv` (29 MB, the build
input), and `data/whiskyfun_tokenized.parquet` (24 MB, the input to
`analysis.dictionary candidate`, produced only by the `w0` notebooks).

## Corpus

The analytical dataset contains 11,149 reviews from 146 assigned distilleries.
Name matching supplies 8,492 reviews (76.2%), while direct index matching
supplies 2,657 reviews (23.8%). The score mean is 86.226 and the median is 87.
The generated corpus audit and score-leakage checks are in
`data/qa_corpus_summary.json` and `data/qa_score_markers.csv`; all eleven
score-marker patterns return zero counts in the cleaned analytical text.

Processed review text remains included for replication with attribution to
[Whiskyfun](https://www.whiskyfun.com/). This repository does not assert that
redistribution permission has been obtained; see
`DATA_USE_AND_ATTRIBUTION.md`. Resolving that permission question is a
prerequisite for journal submission.

## Version 2 Measurement Instrument

Version 1 is retained as historical evidence, but it is superseded for primary
interpretation because it mixed fruit, floral, herbal/tea, and spice terms and
did not preserve a complete approval trail. Version 2 uses eleven primary
constructs: it separates fruit, floral, and spice, omits herbal/tea as too
minor for this study's theory, replaces the former sherry/rancio construct with
`sherry_influence`, whose berry and dried-fruit candidates require explicit
adjudication, excludes or documents context-dependent terms, and is frozen as
the primary instrument (`data/whiskyfun_dictionary_v2.json`). The freeze
approved 247 primary terms and excluded 61 ambiguous and 13 other terms, at a
frequency threshold of 10 reviews.

## Setup

Python 3.11 with the pinned dependencies:

```bash
pip install -r requirements.txt
python -c "import nltk; nltk.download('vader_lexicon')"
```

The VADER lexicon is required by `analysis/common.py` for the sentiment
baseline and is not downloaded automatically.

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
  pipeline/test_whiskyfun_parse_utils.py
```

The corpus and the frozen instrument are already committed, so reproducing
published results only requires the last four commands.

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
--skip-stability`; to redraw the category-dimension figure from saved tables
without retraining, use `--plot-only`.

Two commands write outside version control, into `paper/`. `analysis.models`
exports `fig1_model_comparison` and `fig2_r2_by_scope` directly into
`paper/tex_paper/figure/`; the manuscript's `fig3`, `fig4`, and `fig5` are
**not** auto-regenerated and must be refreshed by hand from `figures/v2/`.
`analysis.assemble` writes `paper/final_paper.md`, a generated markdown summary
that is separate from the LaTeX manuscript.

## Outputs

- `data/whiskyfun_analytical_dataset.csv`, `data/whiskyfun_tokenized.parquet`: shared corpus inputs.
- `data/DATASET.md`: generated corpus-construction memo.
- `data/dictionary_v2_adjudication.csv`: term-level review worksheet with concordances and decisions.
- `data/dictionary_v2_ambiguous_terms.csv`: excluded-primary ambiguity register.
- `data/dictionary_v2_exclusions.csv`: construct-design exclusions from candidate generation.
- `data/whiskyfun_dictionary_v2.json`: authoritative frozen instrument.
- `data/dictionary_v2_provenance.csv`: frozen approval and frequency audit.
- `data/v2/` and `figures/v2/`: primary analysis tables, features, and figures.

## Analysis Design

The approved primary instrument is `data/whiskyfun_dictionary_v2.json`.
Descriptive OLS models report HC1 robust standard errors. Predictive model
comparisons use the same shuffled outer five-fold cross-validation splits, with
text vectorization and Ridge tuning confined to training folds. Validation
groups use title or assigned-distillery metadata rather than dictionary feature
outcomes.

Embedding projections are cosine similarities, and category averages exclude
terms used to construct the corresponding pole. WEAT results report corrected
permutation p-values and Holm adjustment across the two primary tests.
Frequency-weighted category projections and ambiguous-term allocations are
labeled sensitivity analyses. The `Natural_Artificial` result is interpreted
as a robust boundary within this corpus, not as a universal structure of taste
or an observed effect on consumers.

## Notebooks

Active notebooks in `notebooks/`:

- `w0_preproc_phrases.ipynb`, `w0_preproc_bigrams.ipynb`: preprocessing
  provenance; they build `data/whiskyfun_phrases.json`,
  `data/whiskyfun_bigrams.json`, and the tokenized parquet.
- `w1_eda.ipynb`: exploratory analysis on the shared corpus and V2 features.
- `v2_dictionary_review.ipynb`: adjudication worksheet presentation and checks.
- `corrected_results.ipynb`: presentation of the current `analysis/` outputs.

Retained for reproduction history, superseded for publication:

- `w2_analysis.ipynb`, `w3_analysis.ipynb`, `w4_analysis.ipynb`: step-by-step
  regression, embedding, and publication-table results, now recomputed by the
  `analysis/` modules.
- `w1_dict_build.ipynb`, `w1_dict_features.ipynb`: V1-era dictionary
  construction.

> **Note for notebook users.** The week notebooks `w1_eda` through `w4` read
> from and write to **V2 paths** (`data/whiskyfun_dictionary_v2.json`,
> `data/v2/whiskyfun_dict_features.parquet`, `data/v2/`), and run in that
> order. Do **not** run `w1_dict_build.ipynb` or `w1_dict_features.ipynb`
> alongside them: they build the superseded V1 feature matrix at the old
> `data/whiskyfun_dict_features.parquet` path, and they expect a V1 dictionary
> that now exists only under `_local/archive/v1/`.
