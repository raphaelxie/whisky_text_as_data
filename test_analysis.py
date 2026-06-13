"""Tests for corrected reproducible analysis helpers."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import RidgeCV

from analysis.common import (
    build_features,
    canonical_dictionary_term,
    category_shorts,
    dictionary_patterns,
    independent_groups,
    lemma_noun_token,
    preprocess_text,
)
from analysis.dictionary import ADJUDICATION_COLUMNS, V2_CATEGORIES, candidate_frame, freeze, validate_approval
from analysis.embeddings import cosine_projection, dictionary_projections
from analysis.models import fit_ols, outer_splitter, predictive_estimators

V2_SHORTS = [metadata["short_name"] for metadata in V2_CATEGORIES.values()]


class TestPreprocessing(unittest.TestCase):
    def test_punctuation_attached_sensory_plurals_normalize_to_singular(self) -> None:
        normalized = preprocess_text(
            "flowers flowers, berries, raisins; dates. figs! prunes? sultanas:"
        )
        self.assertEqual(
            normalized,
            "flower flower, berry, raisin; date. fig! prune? sultana:",
        )

    def test_phrase_tokens_remain_intact_with_punctuation_and_hyphens(self) -> None:
        normalized = preprocess_text(
            "dried_fruit, red_berry; black_pepper. dried-fruit! red-berry? black-pepper:"
        )
        self.assertEqual(
            normalized,
            "dried_fruit, red_berry; black_pepper. dried_fruit! red_berry? black_pepper:",
        )

    def test_overlapping_phrase_ties_prefer_dried_citrus_candidate(self) -> None:
        self.assertEqual(preprocess_text("dried citrus fruit"), "dried_citrus fruit")

    def test_internal_apostrophes_and_numeric_punctuation_are_not_reconstructed(self) -> None:
        normalized = preprocess_text("flowers, Serge's sample at 46%, cask #12.")
        self.assertEqual(normalized, "flower, serge's sample at 46%, cask #12.")

    def test_kippers_plural_normalizes_to_kipper(self) -> None:
        self.assertEqual(lemma_noun_token("kippers"), "kipper")
        self.assertEqual(preprocess_text("brine and kippers"), "brine and kipper")
        self.assertEqual(canonical_dictionary_term("kippers"), "kipper")
        self.assertEqual(canonical_dictionary_term("kipper"), "kipper")


class TestIndependentGroups(unittest.TestCase):
    def test_group_labels_do_not_depend_on_dictionary_rates(self) -> None:
        frame = pd.DataFrame({
            "whisky_name_raw": ["Lagavulin bourbon barrel", "Glenlivet oloroso sherry"],
            "distillery": ["Lagavulin", "Glenlivet"],
            "score": [88, 88],
            "peat_review_text_per1k": [0.0, 999.0],
        })
        original = independent_groups(frame)
        frame["peat_review_text_per1k"] = [999.0, 0.0]
        revised = independent_groups(frame)
        for key in original:
            self.assertTrue(original[key].equals(revised[key]))
        self.assertTrue(original["Islay assigned distillery"].iloc[0])
        self.assertTrue(original["Sherry title cue"].iloc[1])


class TestEmbeddingMath(unittest.TestCase):
    def test_cosine_projection_is_magnitude_invariant(self) -> None:
        axis = np.array([1.0, 0.0])
        self.assertAlmostEqual(cosine_projection(np.array([2.0, 2.0]), axis),
                               cosine_projection(np.array([20.0, 20.0]), axis))

    def test_dimension_pole_terms_are_excluded_from_category_mean(self) -> None:
        vectors = {
            "rubber": np.array([-1.0, 0.0]),
            "soap": np.array([0.0, 1.0]),
        }
        dictionary = {"categories": {
            "flaws_off_notes": {"short_name": "flaw", "terms": ["rubber", "soap"]},
        }}
        _, means, exclusions = dictionary_projections(
            vectors,
            dictionary,
            axes={"Natural_Artificial": np.array([1.0, 0.0])},
            poles={"Natural_Artificial": {"rubber"}},
        )
        self.assertEqual(means.loc[0, "Natural_Artificial_n"], 1)
        self.assertAlmostEqual(means.loc[0, "Natural_Artificial_proj"], 0.0)
        self.assertEqual(exclusions.loc[0, "excluded_pole_terms"], "rubber")


class TestRobustOLS(unittest.TestCase):
    def test_ols_uses_hc1_covariance(self) -> None:
        n = 40
        frame = pd.DataFrame({"score": np.arange(n), "review_year": [2020] * n})
        for category in V2_SHORTS:
            frame[f"{category}_review_text_per1k"] = np.linspace(0, 1, n) + np.random.default_rng(1).normal(0, .01, n)
        frame["wordcount_review_text"] = np.arange(n) + 10
        result = fit_ols(frame, V2_SHORTS)
        self.assertEqual(result.cov_type, "HC1")


class TestPredictionDesign(unittest.TestCase):
    def test_text_vectorizer_and_ridge_tuning_are_inside_outer_cv_pipeline(self) -> None:
        estimators = predictive_estimators(V2_SHORTS)
        self.assertIn("M2: Full dictionary (11 categories)", estimators)
        self.assertIn("M3: Dictionary minus explicit evaluation (10 categories)", estimators)
        tfidf = estimators["M4: TF-IDF / Ridge (5,000 features)"]
        transformer = tfidf.named_steps["features"].transformers[0][1]
        self.assertIsInstance(transformer, TfidfVectorizer)
        self.assertIsInstance(tfidf.named_steps["model"], RidgeCV)
        splitter = outer_splitter()
        self.assertEqual(splitter.n_splits, 5)
        self.assertTrue(splitter.shuffle)
        self.assertEqual(splitter.random_state, 42)


class TestVersion2Dictionary(unittest.TestCase):
    def test_dynamic_metadata_exposes_eleven_separate_categories(self) -> None:
        dictionary = {"categories": {
            key: {**metadata, "terms": [key]}
            for key, metadata in V2_CATEGORIES.items()
        }}
        self.assertEqual(category_shorts(dictionary), V2_SHORTS)
        self.assertEqual(len(V2_SHORTS), 11)
        self.assertEqual(V2_SHORTS[:3], ["fruit", "floral", "spice"])
        self.assertNotIn("herbal", V2_SHORTS)

    def test_split_constructs_generate_separate_primary_features(self) -> None:
        dictionary = {"categories": {
            key: {**metadata, "terms": [key]}
            for key, metadata in V2_CATEGORIES.items()
        }}
        dictionary["categories"]["fruit"]["terms"] = ["apple"]
        dictionary["categories"]["floral"]["terms"] = ["rose"]
        dictionary["categories"]["spice"]["terms"] = ["ginger", "black_pepper"]
        text = "apple rose ginger black pepper"
        tokenized = pd.DataFrame({
            "dedupe_hash": ["a"], "score": [88], "review_year": [2020],
            "distillery": ["X"], "review_length": [4], "identity_status": ["known"],
            "match_source": ["index"], "review_text_original": [text],
            "review_text": [text], "nose": [text], "mouth": [text],
            "finish": [text], "comments": [text], "nmf": [text],
        })
        features = build_features(tokenized, dictionary)
        for short in ["fruit", "floral"]:
            self.assertEqual(features.loc[0, f"{short}_review_text_count"], 1)
        self.assertEqual(features.loc[0, "spice_review_text_count"], 2)

    def test_candidate_packet_reclassifies_terms_and_records_concordances(self) -> None:
        v1 = {"categories": {
            "fruit_aromatics": {"terms": ["apple", "floral", "mint", "ginger", "honey", "date", "dried_fruit", "blackberry", "raspberry", "strawberry"]},
            "texture_body": {"terms": ["peppery"]},
            "peat_smoke_coastal": {"terms": ["tcp"]},
        }}
        tokenized = pd.DataFrame({"review_text": [
            "apple floral mint ginger honey tcp",
            "mint floral ginger honey tcp",
            "apple mint ginger honey tcp",
        ]})
        frame = candidate_frame(tokenized, v1).set_index("term")
        self.assertEqual(frame.loc["apple", "proposed_v2_category"], "fruit")
        self.assertEqual(frame.loc["floral", "proposed_v2_category"], "floral")
        self.assertNotIn("mint", frame.index)
        self.assertEqual(frame.loc["ginger", "proposed_v2_category"], "spice")
        self.assertEqual(frame.loc["peppery", "proposed_v2_category"], "spice")
        self.assertTrue(bool(frame.loc["tcp", "ambiguity_flag"]))
        self.assertEqual(frame.loc["tcp", "decision"], "")
        self.assertTrue(bool(frame.loc["date", "ambiguity_flag"]))
        self.assertEqual(frame.loc["date", "proposed_v2_category"], "sherry_influence")
        self.assertTrue(bool(frame.loc["dried_fruit", "ambiguity_flag"]))
        for term in ["blackberry", "raspberry", "strawberry", "berry", "dried_fig", "sultana"]:
            self.assertEqual(frame.loc[term, "proposed_v2_category"], "sherry_influence")
            self.assertTrue(bool(frame.loc[term, "ambiguity_flag"]))
        self.assertIn("flower", frame.index)
        self.assertNotIn("flowers", frame.index)
        self.assertIn("pepper", frame.index)
        self.assertIn("sea_breeze", frame.index)
        self.assertIn("solera", frame.index)
        self.assertEqual(frame.loc["solera", "proposed_v2_category"], "sherry_influence")
        self.assertTrue(frame.loc["apple", "concordance_1"])

    def test_candidate_packet_drops_plural_when_singular_present(self) -> None:
        v1 = {"categories": {"peat_smoke_coastal": {"terms": ["kipper", "kippers"]}}}
        tokenized = pd.DataFrame(
            {"review_text": [preprocess_text("brine and kippers on the palate")]}
        )
        frame = candidate_frame(tokenized, v1)
        terms = set(frame["term"])
        self.assertIn("kipper", terms)
        self.assertNotIn("kippers", terms)
        self.assertEqual(frame.loc[frame["term"] == "kipper", "review_frequency"].iloc[0], 1)

    def test_canonical_flower_pattern_counts_plural_surface_after_preprocessing(self) -> None:
        normalized = preprocess_text("flower flowers, flowers.")
        dictionary = {"categories": {
            "floral": {"short_name": "floral", "terms": ["flower"]},
        }}
        matches = dictionary_patterns(dictionary)["floral"].findall(normalized)
        self.assertEqual(len(matches), 3)
        frame = candidate_frame(pd.DataFrame({"review_text": [normalized]}), {"categories": {}})
        self.assertIn("flower", set(frame["term"]))
        self.assertNotIn("flowers", set(frame["term"]))

    def test_freeze_blocks_incomplete_and_below_threshold_approvals(self) -> None:
        rows = []
        for key in V2_CATEGORIES:
            rows.append({
                "term": f"{key}_term",
                "prior_v1_category": "",
                "proposed_v2_category": key,
                "candidate_source": "seed",
                "review_frequency": 20,
                "construct_definition": V2_CATEGORIES[key]["construct"],
                "ambiguity_flag": False,
                "alternate_categories": "",
                "concordance_1": "context",
                "concordance_2": "context",
                "concordance_3": "context",
                "decision": "approve_primary",
                "reviewer_rationale": "Literal construct match.",
                "reviewer_status": "approved",
            })
        frame = pd.DataFrame(rows, columns=ADJUDICATION_COLUMNS)
        frame.loc[0, "decision"] = ""
        frame.loc[1, "ambiguity_flag"] = True
        frame.loc[2, "review_frequency"] = 2
        errors = validate_approval(frame)
        self.assertTrue(any("missing or invalid decision" in error for error in errors))
        self.assertTrue(any("fewer than 10" in error for error in errors))
        duplicated = pd.concat([frame, frame.iloc[[3]]], ignore_index=True)
        duplicated.loc[duplicated["term"].eq(frame.loc[3, "term"]), "decision"] = "approve_primary"
        self.assertTrue(any("appears more than once" in error for error in validate_approval(duplicated)))

    def test_ambiguity_flag_can_be_resolved_by_documented_approval(self) -> None:
        rows = []
        for key in V2_CATEGORIES:
            rows.append({
                "term": f"{key}_term",
                "prior_v1_category": "",
                "proposed_v2_category": key,
                "candidate_source": "seed",
                "review_frequency": 20,
                "construct_definition": V2_CATEGORIES[key]["construct"],
                "ambiguity_flag": key == "sherry_influence",
                "alternate_categories": "fruit;sherry_influence" if key == "sherry_influence" else "",
                "concordance_1": "context",
                "concordance_2": "context",
                "concordance_3": "context",
                "decision": "approve_primary",
                "reviewer_rationale": "Reviewed in context and assigned to the selected construct.",
                "reviewer_status": "approved",
            })
        self.assertEqual(validate_approval(pd.DataFrame(rows, columns=ADJUDICATION_COLUMNS)), [])

    def test_freeze_emits_versioned_dictionary_after_complete_approval(self) -> None:
        rows = []
        for key in V2_CATEGORIES:
            rows.append({
                "term": f"{key}_term",
                "prior_v1_category": "",
                "proposed_v2_category": key,
                "candidate_source": "seed",
                "review_frequency": 20,
                "construct_definition": V2_CATEGORIES[key]["construct"],
                "ambiguity_flag": False,
                "alternate_categories": "",
                "concordance_1": "context",
                "concordance_2": "context",
                "concordance_3": "context",
                "decision": "approve_primary",
                "reviewer_rationale": "Literal construct match.",
                "reviewer_status": "approved",
            })
        with TemporaryDirectory() as tmp:
            output = Path(tmp)
            adjudication = output / "adjudication.csv"
            pd.DataFrame(rows, columns=ADJUDICATION_COLUMNS).to_csv(adjudication, index=False)
            freeze(adjudication, output)
            self.assertTrue((output / "whiskyfun_dictionary_v2.json").exists())
            self.assertTrue((output / "dictionary_v2_approval_report.md").exists())


if __name__ == "__main__":
    unittest.main()
