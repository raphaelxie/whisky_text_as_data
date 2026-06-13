"""Assemble provenance artifacts and a result-driven Markdown manuscript."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from analysis.common import DATA, PAPER, ensure_dirs, load_dictionary


def _value(frame: pd.DataFrame, column: str, condition) -> float:
    return float(frame.loc[condition, column].iloc[0])


def manuscript(results_dir: Path, dictionary: dict) -> str:
    qa = json.loads((DATA / "qa_corpus_summary.json").read_text(encoding="utf-8"))
    cv = pd.read_csv(results_dir / "corrected_predictive_comparison.csv")
    coef = pd.read_csv(results_dir / "corrected_ols_coefficients.csv")
    scopes = pd.read_csv(results_dir / "w4_table4_r2_by_scope.csv")
    sensitivity = pd.read_csv(results_dir / "corrected_tier1_sensitivity.csv")
    validation = pd.read_csv(results_dir / "corrected_independent_group_validation.csv")
    vignettes = pd.read_csv(results_dir / "corrected_close_reading_vignettes.csv")
    weat = pd.read_csv(results_dir / "w4_table7_weat_results.csv")
    stability = json.loads((results_dir / "corrected_embedding_stability_summary.json").read_text(encoding="utf-8"))
    n_terms = dictionary["total_terms"]
    n_categories = len(dictionary["categories"])

    dict_r2 = _value(cv, "r2_oof", cv["model"].str.startswith("M2"))
    vader_r2 = _value(cv, "r2_oof", cv["model"].str.startswith("M1"))
    tfidf_r2 = _value(cv, "r2_oof", cv["model"].str.startswith("M4"))
    flaw = coef[(coef["sample"] == "All reviews") & coef["variable"].str.startswith("flaw_")].iloc[0]
    tier_full = sensitivity.iloc[0]
    tier_index = sensitivity.iloc[1]
    nmf = scopes[scopes["scope"] == "Nose + Mouth + Finish"].iloc[0]
    comments = scopes[scopes["scope"] == "Comments"].iloc[0]
    peat_islay = validation[(validation["group"] == "Islay assigned distillery") & (validation["category"] == "peat")].iloc[0]
    sherry = validation[(validation["group"] == "Sherry title cue") & (validation["category"] == "sherry")].iloc[0]
    bourbon = validation[(validation["group"] == "Bourbon title cue") & (validation["category"] == "oak")].iloc[0]
    weat1, weat2 = weat.iloc[0], weat.iloc[1]
    vignette_lines = "\n".join(
        f"| {row.vignette} | {row.whisky_name_raw} | {row.category} = {row.category_rate_per1k:.2f} | "
        f"\"{row.short_attributed_excerpt}\" ([source]({row.source_url})) |"
        for row in vignettes.itertuples()
    )
    natural_dominance = stability["natural_artificial_dominant_runs"]
    flaw_direction = stability["flaw_artificial_direction_runs"]
    natural_language = (
        f"Under Version 2, the Natural/Artificial dimension was widest in {natural_dominance} of "
        f"{stability['runs']} prespecified runs and flaw language was artificial-facing in "
        f"{flaw_direction} of {stability['runs']}. This stability provides robustness evidence "
        "for a corpus-specific boundary interpretation, rather than a universal account of taste."
    )
    bourbon_language = (
        f"bourbon-style title cues excluding sherry (`n` = {int(bourbon['n_group']):,}) "
        f"show only negligible oak-language difference (`d` = {bourbon['cohen_d']:.3f})"
    )
    return f"""# Making Expert Taste Computable

## Theory-Guided Measurement of Valuation and Symbolic Boundaries in Whisky Reviews

### Abstract
Specialized evaluative communities organize judgment through vocabularies that generic sentiment measures may not adequately represent. This article develops an interpretable computational measurement strategy for expert valuation using {qa['rows']:,} structured Scottish malt whisky reviews from Whiskyfun, 2012-2025. We construct a human-adjudicated Version 2 {n_terms}-term, {n_categories}-category domain instrument and assess it through leakage auditing, metadata-defined validation groups, robust descriptive models, held-out model comparisons, semantic-space analysis, and sensitivity tests. The instrument captures more out-of-fold score-related information than VADER sentiment (`R2` = {dict_r2:.3f} versus {vader_r2:.3f}), while a TF-IDF/Ridge benchmark performs better (`R2` = {tfidf_r2:.3f}), clarifying the distinction between interpretable cultural measurement and unrestricted prediction. Sensory-section language contains substantially more evaluative information than concluding comments, and flaw vocabulary has the strongest negative dictionary association with score. {natural_language} The study provides a transparent design for computational analysis of specialized valuation while limiting substantive claims to this review discourse.

### Research Questions
1. Can a theory-guided, human-adjudicated domain instrument capture held-out evaluative information beyond generic sentiment while remaining distinct from unrestricted lexical prediction?
2. Do its categories track independently specified style cues and the structured locations where expert evaluation occurs?
3. Can corpus-trained semantic space recover a robust boundary between legitimate character and artificial defect?

### Computational Sociology Contribution
This study treats expert valuation as a measurement problem in computational cultural sociology. Bourdieu (1984), Hennion (2004, 2007), and Karpik (2010) motivate treating expert review language as a classificatory and practical device for making singular sensory goods comparable. Lamont and Molnar (2002) and Douglas (1966) motivate the theoretically specified boundary between valued character and contaminating defect. These concepts define the categories and semantic relation to be measured; predictive models are validation benchmarks rather than substitutes for sociological interpretation.

The article contributes (1) a documented, human-adjudicated instrument for specialized evaluative discourse, (2) a validation design combining leakage auditing, independent metadata checks, held-out benchmark comparison, and semantic sensitivity testing, and (3) a bounded empirical finding about the organization of character and defect within one expert review practice.

### Data And Ethics
The unit of analysis is a Whiskyfun review with an integer score in the 2012-2025 collection. The corrected corpus contains {qa['rows']:,} reviews from {qa['distilleries']} assigned distilleries; mean score is {qa['score']['mean']:.3f} and median score is {qa['score']['median']:.0f}. Contrary to earlier drafts, name matching supplies {qa['match_source']['name']['n']:,} rows ({qa['match_source']['name']['pct']:.1f}%) and index matching supplies {qa['match_source']['index']['n']:,} ({qa['match_source']['index']['pct']:.1f}%).

The repository includes processed review text to permit replication. The review prose remains copyright of Whiskyfun and its original authors; inclusion here is attributed research use and does not assert permission for redistribution or transfer copyright. Publication beyond coursework should include an institutional or publisher review of this data-release decision. No private-person data or participant intervention is involved.

Numerical score disclosures are removed before text analysis. QA recorded zero retained numeric points, numeric score phrases, SGP score fields, or WF score fields in the primary modeling text after cleaning.

### Methods
The approved Version 2 dictionary contains {n_categories} sensory/evaluative categories. Its reconstruction separates fresh fruit, floral, and spice vocabularies, omits herbal/tea as outside the primary theoretical focus, replaces the former sherry/rancio construct with sherry influence, and documents decisions about direct sherry references and associated berry or dried-fruit markers. Rates per 1,000 tokens are calculated separately for full review text and for Nose, Mouth, Finish, Comments, and combined Nose-Mouth-Finish (NMF). Generic sentiment uses VADER (Hutto and Gilbert 2014). OLS associations use year fixed effects and HC1 robust standard errors; these are descriptive associations because score and prose are co-produced.

Prediction comparisons use identical shuffled five-fold outer splits (`random_state=42`). TF-IDF vectorization and ridge tuning occur inside training folds only. Results are reported as out-of-fold `R2`, MAE, and RMSE, rather than fitted-sample adjusted `R2`.

Validation groups are defined without dictionary outcome rates: assigned Islay distillery, sherry cues in bottle titles, and bourbon/barrel/hogshead title cues excluding sherry cues. High- and low-score comparisons are retained only as criterion associations.

Embedding dimensions use Word2Vec skip-gram models (Mikolov et al. 2013) and cosine projections with both word and dimension vectors normalized, following dimension-based cultural measurement (Kozlowski, Taddy, and Evans 2019). Any dictionary term used as a pole is excluded from that category's mean projection on that dimension. Two primary WEAT tests adapt Caliskan, Bryson, and Narayanan (2017) and report conservative permutation p-values and Holm-adjusted p-values. Stability is evaluated across 30 deterministic models: three dimension/window specifications and ten seeds each, reflecting sensitivity concerns in applied embedding research (Rodriguez and Spirling 2022).

### Results
#### Interpretable Measurement Versus Prediction
In out-of-fold comparison, the full dictionary model achieves `R2` = {dict_r2:.3f}, versus {vader_r2:.3f} for VADER. TF-IDF/Ridge reaches `R2` = {tfidf_r2:.3f}, indicating that transparent domain categories improve on generic sentiment but do not capture all score-related lexical information.

Flaw rate is negatively associated with score in the full corpus (`b` = {flaw['b_unstandardized']:.3f}, HC1 `SE` = {flaw['robust_se_hc1']:.3f}, `p` = {flaw['p_hc1']:.3g}). The full-corpus dictionary model has descriptive adjusted `R2` = {tier_full['adj_r2_descriptive']:.3f}; on the more securely assigned Tier-1 subset it is {tier_index['adj_r2_descriptive']:.3f} (`n` = {int(tier_index['n']):,}). Tier-specific differences constrain broad claims about the full matched sample.

#### Independent Validation
Islay-assigned reviews (`n` = {int(peat_islay['n_group']):,}) show higher peat-language rates than other assigned distilleries (Cohen's `d` = {peat_islay['cohen_d']:.3f}). Reviews with sherry title cues (`n` = {int(sherry['n_group']):,}) show higher sherry vocabulary (`d` = {sherry['cohen_d']:.3f}); {bourbon_language}. These comparisons replace the earlier circular rate-defined groups and disclose the unsupported bourbon/oak check rather than treating it as confirmation.

#### Structured Description
Using one common complete-case sample (`n` = {int(nmf['n']):,}), the NMF scope has descriptive adjusted `R2` = {nmf['adj_r2_descriptive']:.3f}; Comments alone has {comments['adj_r2_descriptive']:.3f}. This pattern is consistent with evaluation being embedded in sensory description, but it is an association within one reviewer's format, not a causal demonstration of legitimation.

#### Close-Reading Anchors
The following cases were selected reproducibly from the corrected outputs: the maximum relevant category rate within each prespecified stratum. Excerpts are brief, attributed context anchors rather than a redistributed substitute for the source review.

| Selection rule | Bottle title | Relevant rate per 1,000 tokens | Brief attributed excerpt |
| --- | --- | ---: | --- |
{vignette_lines}

#### Embedding Evidence
The corrected WEAT high/low-descriptor test gives `d` = {weat1['effect_size_d']:.3f}, Holm-adjusted `p` = {weat1['p_value_holm_primary']:.4f}; the flaw/neutral test gives `d` = {weat2['effect_size_d']:.3f}, adjusted `p` = {weat2['p_value_holm_primary']:.4f}. {natural_language}

### Discussion And Limitations
The corrected analyses support a restrained computational-sociology conclusion: a theory-guided instrument identifies score-relevant structure that generic sentiment underrepresents, even though unrestricted lexical features remain more predictive. Independent style-group checks support the peat and sherry categories but not the proposed bourbon/oak check. The sensory-section result supports reading structured description as an evaluative practice, and the embedding analyses recover a robust character/defect boundary within this corpus.

Limitations are substantial. This is one reviewer's corpus, not expert whisky discourse generally. Most assignments rely on title-name matching rather than direct index placement. The dictionary and embedding poles are theoretically curated. Corrected pole exclusion and multi-seed stability reduce, but do not eliminate, interpretive dependence on design choices. Scores and prose are jointly produced, so the models cannot estimate causal effects of language.

### Conclusion
This project makes expert taste computationally observable without reducing it to score prediction. Whiskyfun tasting notes provide a bounded case in which transparent domain measurement and robust semantic analysis identify how specialized vocabulary renders sensory value publicly comparable. The evidence supports a corpus-specific boundary between legitimate character and artificial defect; it does not establish audience effects, market value, or universal structures of taste.

### Reproducibility
The canonical computational entry points are `python -m analysis.qa`, `python -m analysis.dictionary candidate`, `python -m analysis.dictionary freeze`, `python -m analysis.models`, `python -m analysis.embeddings`, and `python -m analysis.assemble`. Version 2 primary outputs are generated under `data/v2/` and `figures/v2/` only after approval. The bibliography source of truth is `paper/references.bib`; verification notes are in `paper/source_log.md`.

### References
Bourdieu, Pierre. 1984. *Distinction: A Social Critique of the Judgement of Taste*. Cambridge, MA: Harvard University Press.

Caliskan, Aylin, Joanna J. Bryson, and Arvind Narayanan. 2017. "Semantics Derived Automatically from Language Corpora Contain Human-Like Biases." *Science* 356(6334):183-186. https://doi.org/10.1126/science.aal4230.

Douglas, Mary. 1966. *Purity and Danger: An Analysis of Concepts of Pollution and Taboo*. London: Routledge and Kegan Paul.

Hennion, Antoine. 2004. "Pragmatics of Taste." In *The Blackwell Companion to the Sociology of Culture*, edited by Mark D. Jacobs and Nancy Weiss Hanrahan, 131-144. Malden, MA: Blackwell.

Hennion, Antoine. 2007. "Those Things That Hold Us Together: Taste and Sociology." *Cultural Sociology* 1(1):97-114. https://doi.org/10.1177/1749975507073923.

Hutto, C. J., and Eric Gilbert. 2014. "VADER: A Parsimonious Rule-based Model for Sentiment Analysis of Social Media Text." In *Proceedings of the Eighth International AAAI Conference on Weblogs and Social Media*.

Karpik, Lucien. 2010. *Valuing the Unique: The Economics of Singularities*. Princeton, NJ: Princeton University Press.

Kozlowski, Austin C., Matt Taddy, and James A. Evans. 2019. "The Geometry of Culture: Analyzing the Meanings of Class through Word Embeddings." *American Sociological Review* 84(5):905-949. https://doi.org/10.1177/0003122419877135.

Lamont, Michele, and Virag Molnar. 2002. "The Study of Boundaries in the Social Sciences." *Annual Review of Sociology* 28:167-195. https://doi.org/10.1146/annurev.soc.28.110601.141107.

Mikolov, Tomas, Kai Chen, Greg Corrado, and Jeffrey Dean. 2013. "Efficient Estimation of Word Representations in Vector Space." arXiv:1301.3781. https://arxiv.org/abs/1301.3781.

Rodriguez, Pedro L., and Arthur Spirling. 2022. "Word Embeddings: What Works, What Does Not, and How to Tell the Difference for Applied Research." *Journal of Politics* 84(1):101-115. https://doi.org/10.1086/715162.

Swidler, Ann. 1986. "Culture in Action: Symbols and Strategies." *American Sociological Review* 51(2):273-286.
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dictionary", type=Path, default=DATA / "whiskyfun_dictionary_v2.json")
    parser.add_argument("--results-dir", type=Path, default=DATA / "v2")
    parser.add_argument("--paper-dir", type=Path, default=PAPER)
    args = parser.parse_args()
    ensure_dirs()
    args.paper_dir.mkdir(parents=True, exist_ok=True)
    dictionary = load_dictionary(args.dictionary)
    provenance = DATA / "dictionary_v2_provenance.csv"
    if not provenance.exists():
        raise FileNotFoundError("Version 2 approval provenance is missing; run `python -m analysis.dictionary freeze` first.")
    (args.paper_dir / "final_paper.md").write_text(manuscript(args.results_dir, dictionary), encoding="utf-8")
    print(f"Assembled Version 2 manuscript from {args.results_dir} and {provenance}.")


if __name__ == "__main__":
    main()
