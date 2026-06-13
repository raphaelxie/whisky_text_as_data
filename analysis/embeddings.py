"""Corrected embedding dimensions, WEAT tests, and stability analysis."""

from __future__ import annotations

import argparse
import itertools
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from gensim.models import Word2Vec

from analysis.common import (
    DATA,
    FIGURES,
    build_tokenized,
    category_map,
    ensure_dirs,
    holm_adjust,
    load_dictionary,
    token_sentences,
)

DIMS = {
    "Quality_Defect": {
        "positive": ["excellent", "superb", "brilliant", "marvellous", "great", "perfect", "beautiful", "impressive"],
        "negative": ["poor", "flawed", "weak", "dull", "disappointing", "mediocre", "failed", "unpleasant"],
    },
    "Complexity_Simplicity": {
        "positive": ["complex", "layered", "deep", "evolving", "sophisticated", "multidimensional", "intricate"],
        "negative": ["simple", "plain", "basic", "narrow", "monolithic", "straightforward", "monotone"],
    },
    "Balance_Imbalance": {
        "positive": ["balanced", "integrated", "harmonious", "coherent", "precise", "elegant"],
        "negative": ["unbalanced", "disjointed", "rough", "messy", "clumsy", "excessive", "awkward"],
    },
    "Natural_Artificial": {
        "positive": ["natural", "honest", "earthy", "waxy", "old_school", "traditional",
                     "old_style", "classic", "genuine"],
        "negative": ["artificial", "chemical", "plastic", "rubber", "metallic", "solvent",
                     "industrial", "doctored", "bland", "hollow"],
    },
}
WEAT_PRIMARY = [
    {
        "test": "High vs low descriptors x quality/defect",
        "X": ["complex", "waxy", "tropical_fruit", "balanced", "long_finish", "elegant", "rancio", "mineral"],
        "Y": ["thin", "bitter", "rubbery", "cardboard", "short_finish", "weak", "dull", "simple"],
        "A": ["excellent", "superb", "brilliant", "marvellous", "perfect", "impressive"],
        "B": ["poor", "flawed", "disappointing", "mediocre", "failed", "unpleasant"],
    },
    {
        "test": "Flaws vs neutral descriptors x defect/quality",
        "X": ["rubber", "cardboard", "soap", "metallic", "feinty", "solvent"],
        "Y": ["barley", "malt", "cereal", "apple", "vanilla", "honey"],
        "A": ["poor", "flawed", "dull", "weak", "disappointing"],
        "B": ["excellent", "great", "superb", "brilliant", "marvellous"],
    },
]
WEAT_SUPPLEMENTARY = [
    {
        "test": "Old_School vs Modern/Industrial descriptors x Quality/Defect",
        "X": ["old_school", "old_style", "classic", "traditional", "genuine", "waxy", "honest"],
        "Y": ["doctored", "industrial", "bland", "hollow", "botoxed", "wood_driven", "cask_driven"],
        "A": ["excellent", "superb", "brilliant", "marvellous", "perfect", "impressive"],
        "B": ["poor", "flawed", "disappointing", "mediocre", "failed", "unpleasant"],
    },
]


def unit(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    if norm == 0:
        raise ValueError("Cannot normalize a zero vector.")
    return vector / norm


def cosine_projection(vector: np.ndarray, axis: np.ndarray) -> float:
    return float(np.dot(unit(vector), unit(axis)))


def train(sentences: list[list[str]], vector_size: int, window: int, seed: int) -> Word2Vec:
    return Word2Vec(
        sentences=sentences,
        sg=1,
        vector_size=vector_size,
        window=window,
        min_count=10,
        negative=5,
        epochs=10,
        workers=1,
        seed=seed,
    )


def dimension_axes(wv) -> tuple[dict[str, np.ndarray], dict[str, set[str]]]:
    axes: dict[str, np.ndarray] = {}
    poles: dict[str, set[str]] = {}
    for name, config in DIMS.items():
        positive = [term for term in config["positive"] if term in wv]
        negative = [term for term in config["negative"] if term in wv]
        if len(positive) < 2 or len(negative) < 2:
            raise ValueError(f"Insufficient vocabulary support for {name}")
        axes[name] = unit(
            np.mean([unit(wv[term]) for term in positive], axis=0)
            - np.mean([unit(wv[term]) for term in negative], axis=0)
        )
        poles[name] = set(positive + negative)
    return axes, poles


def dictionary_projections(
    wv,
    dictionary: dict,
    axes: dict[str, np.ndarray] | None = None,
    poles: dict[str, set[str]] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if axes is None or poles is None:
        axes, poles = dimension_axes(wv)
    mapping = category_map(dictionary)
    term_rows: list[dict[str, object]] = []
    exclusions: list[dict[str, object]] = []
    for category, data in dictionary["categories"].items():
        short = mapping[category]
        terms = [term for term in data["terms"] if term in wv]
        for term in terms:
            row = {"category": short, "term": term}
            for dimension, axis in axes.items():
                row[f"{dimension}_proj"] = cosine_projection(wv[term], axis)
            term_rows.append(row)
        for dimension, pole_terms in poles.items():
            omitted = sorted(set(terms).intersection(pole_terms))
            exclusions.append({
                "category": short, "dimension": dimension,
                "excluded_pole_terms": "; ".join(omitted), "n_excluded": len(omitted),
                "n_retained": len(terms) - len(omitted),
            })
    term_df = pd.DataFrame(term_rows)
    mean_rows = []
    for category in term_df["category"].unique():
        source = term_df[term_df["category"].eq(category)]
        row: dict[str, object] = {"category": category}
        for dimension, pole_terms in poles.items():
            eligible = source[~source["term"].isin(pole_terms)]
            row[f"{dimension}_proj"] = eligible[f"{dimension}_proj"].mean()
            row[f"{dimension}_n"] = len(eligible)
        mean_rows.append(row)
    return term_df, pd.DataFrame(mean_rows), pd.DataFrame(exclusions)


def association(wv, word: str, a: list[str], b: list[str]) -> float:
    return float(np.mean([cosine_projection(wv[word], wv[x]) for x in a])
                 - np.mean([cosine_projection(wv[word], wv[x]) for x in b]))


def weat_test(wv, definition: dict, max_permutations: int = 10000, seed: int = 42) -> dict[str, object]:
    sets = {key: [term for term in definition[key] if term in wv] for key in ["X", "Y", "A", "B"]}
    used = [term for terms in sets.values() for term in terms]
    if len(used) != len(set(used)):
        raise ValueError(f"WEAT sets overlap after vocabulary filtering: {definition['test']}")
    if any(len(sets[key]) < 2 for key in sets):
        raise ValueError(f"WEAT set has fewer than two in-vocabulary words: {definition['test']}")
    x_scores = [association(wv, term, sets["A"], sets["B"]) for term in sets["X"]]
    y_scores = [association(wv, term, sets["A"], sets["B"]) for term in sets["Y"]]
    observed = sum(x_scores) - sum(y_scores)
    pooled = np.asarray(x_scores + y_scores)
    effect = (np.mean(x_scores) - np.mean(y_scores)) / np.std(pooled, ddof=1)
    combined = sets["X"] + sets["Y"]
    n_x = len(sets["X"])
    total_partitions = math.comb(len(combined), n_x)
    rng = np.random.default_rng(seed)
    if total_partitions <= max_permutations:
        selections = itertools.combinations(range(len(combined)), n_x)
        permutations = [tuple(item) for item in selections]
    else:
        permutations = [tuple(sorted(rng.choice(len(combined), n_x, replace=False))) for _ in range(max_permutations)]
    values = {term: association(wv, term, sets["A"], sets["B"]) for term in combined}
    extreme = 0
    for indices in permutations:
        selected = {combined[index] for index in indices}
        statistic = sum(values[term] for term in selected) - sum(values[term] for term in combined if term not in selected)
        extreme += statistic >= observed
    pvalue = (extreme + 1) / (len(permutations) + 1)
    return {
        "test": definition["test"],
        "effect_size_d": effect,
        "p_value_one_sided": pvalue,
        "n_permutations": len(permutations),
        "X_terms": "; ".join(sets["X"]), "Y_terms": "; ".join(sets["Y"]),
        "A_terms": "; ".join(sets["A"]), "B_terms": "; ".join(sets["B"]),
    }


def weat_results(wv) -> pd.DataFrame:
    rows = [weat_test(wv, definition) for definition in WEAT_PRIMARY]
    adjusted = holm_adjust([row["p_value_one_sided"] for row in rows])
    for row, corrected in zip(rows, adjusted):
        row["p_value_holm_primary"] = corrected
        row["analysis_role"] = "primary"
    sensitivity = dict(WEAT_PRIMARY[1])
    sensitivity["test"] = "Flaws vs neutral descriptors x defect/quality (including ambiguous sulphur)"
    sensitivity["X"] = sensitivity["X"] + ["sulphur"]
    row = weat_test(wv, sensitivity)
    row["p_value_holm_primary"] = np.nan
    row["analysis_role"] = "sensitivity"
    rows.append(row)
    for definition in WEAT_SUPPLEMENTARY:
        row = weat_test(wv, definition)
        row["p_value_holm_primary"] = np.nan
        row["analysis_role"] = "supplementary_weat"
        rows.append(row)
    return pd.DataFrame(rows)


def stability_run(sentences: list[list[str]], dictionary: dict) -> pd.DataFrame:
    rows = []
    for vector_size, window in [(100, 5), (150, 6), (200, 10)]:
        for seed in range(1, 11):
            model = train(sentences, vector_size, window, seed)
            _, means, _ = dictionary_projections(model.wv, dictionary)
            spreads = {}
            for dimension in DIMS:
                values = means[f"{dimension}_proj"]
                spreads[dimension] = values.max() - values.min()
            flaw_value = means.loc[means["category"].eq("flaw"), "Natural_Artificial_proj"].iloc[0]
            rows.append({
                "vector_size": vector_size, "window": window, "seed": seed,
                **{f"{dimension}_spread": spread for dimension, spread in spreads.items()},
                "largest_spread_dimension": max(spreads, key=spreads.get),
                "flaw_natural_artificial_projection": flaw_value,
                "natural_artificial_dominant": max(spreads, key=spreads.get) == "Natural_Artificial",
                "flaw_artificial_direction": flaw_value < 0,
            })
    return pd.DataFrame(rows)


def neighbor_audit(wv, dictionary: dict) -> pd.DataFrame:
    mapping = category_map(dictionary)
    category = {
        term: mapping[key] for key, values in dictionary["categories"].items()
        for term in values["terms"]
    }
    anchors = ["waxy", "rancio", "tropical_fruit", "peat", "sulphur", "rubber", "sherry", "balanced", "complex"]
    rows = []
    for anchor in anchors:
        if anchor not in wv:
            continue
        for rank, (neighbor, similarity) in enumerate(wv.most_similar(anchor, topn=10), start=1):
            rows.append({"anchor": anchor, "rank": rank, "neighbor": neighbor, "similarity": similarity, "neighbor_category": category.get(neighbor, "")})
    return pd.DataFrame(rows)


def frequency_weighted_means(
    terms: pd.DataFrame, exclusions: pd.DataFrame, provenance_path: Path
) -> pd.DataFrame:
    provenance = pd.read_csv(provenance_path, keep_default_na=False)
    frequency = provenance.loc[
        provenance["decision"].eq("approve_primary"), ["term", "review_frequency"]
    ].drop_duplicates()
    source = terms.merge(frequency, on="term", how="left")
    rows = []
    for category in source["category"].unique():
        for dimension in DIMS:
            omitted = exclusions.loc[
                exclusions["category"].eq(category) & exclusions["dimension"].eq(dimension),
                "excluded_pole_terms",
            ].iloc[0]
            excluded_terms = {term.strip() for term in str(omitted).split(";") if term.strip()}
            eligible = source[source["category"].eq(category) & ~source["term"].isin(excluded_terms)]
            weights = eligible["review_frequency"].astype(float)
            value = np.average(eligible[f"{dimension}_proj"], weights=weights) if weights.sum() else np.nan
            rows.append(
                {
                    "category": category,
                    "dimension": dimension,
                    "frequency_weighted_mean_projection": value,
                    "n_terms": len(eligible),
                    "analysis_role": "frequency-weighted sensitivity",
                }
            )
    return pd.DataFrame(rows)


def ambiguous_projection_sensitivity(
    wv, dictionary: dict, axes: dict[str, np.ndarray], poles: dict[str, set[str]], means: pd.DataFrame, register_path: Path
) -> pd.DataFrame:
    if not register_path.exists():
        return pd.DataFrame()
    register = pd.read_csv(register_path, keep_default_na=False)
    mapping = category_map(dictionary)
    rows = []
    for _, item in register[register["decision"].eq("exclude_ambiguous")].iterrows():
        term = item["term"]
        if term not in wv:
            continue
        for category in str(item["alternate_categories"]).split(";"):
            if category not in mapping:
                continue
            short = mapping[category]
            category_terms = [item for item in dictionary["categories"][category]["terms"] if item in wv]
            for dimension, axis in axes.items():
                retained = [value for value in category_terms + [term] if value not in poles[dimension]]
                primary = means.loc[means["category"].eq(short), f"{dimension}_proj"].iloc[0]
                scenario = np.mean([cosine_projection(wv[value], axis) for value in retained])
                rows.append(
                    {
                        "term": term,
                        "assigned_category": short,
                        "dimension": dimension,
                        "primary_mean_projection": primary,
                        "sensitivity_mean_projection": scenario,
                        "delta": scenario - primary,
                        "sign_changed": np.sign(scenario) != np.sign(primary),
                        "analysis_role": "ambiguous-term sensitivity; not primary measurement",
                    }
                )
    return pd.DataFrame(rows)


def plot_dimensions(means: pd.DataFrame, figure_dir: Path) -> None:
    figure_dir.mkdir(parents=True, exist_ok=True)
    display = means.set_index("category")[[f"{name}_proj" for name in DIMS]]
    display.plot(kind="bar", figsize=(12, 6))
    plt.ylabel("Mean cosine projection (pole terms excluded)")
    plt.title("Corrected category projections onto cultural dimensions")
    plt.tight_layout()
    plt.savefig(figure_dir / "fig_corrected_category_dimensions.png", dpi=180)
    plt.savefig(figure_dir / "fig_corrected_category_dimensions.pdf")
    plt.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DATA / "whiskyfun_analytical_dataset.csv")
    parser.add_argument("--dictionary", type=Path, default=DATA / "whiskyfun_dictionary_v2.json")
    parser.add_argument("--output-dir", type=Path, default=DATA / "v2")
    parser.add_argument("--figure-dir", type=Path, default=FIGURES / "v2")
    parser.add_argument("--provenance", type=Path, default=DATA / "dictionary_v2_provenance.csv")
    parser.add_argument("--ambiguous-register", type=Path, default=DATA / "dictionary_v2_ambiguous_terms.csv")
    parser.add_argument("--skip-stability", action="store_true")
    args = parser.parse_args()
    dictionary = load_dictionary(args.dictionary)
    ensure_dirs()
    tokenized_path = args.output_dir / "whiskyfun_tokenized.parquet"
    tokenized = pd.read_parquet(tokenized_path) if tokenized_path.exists() else build_tokenized(args.dataset, tokenized_path)
    sentences = token_sentences(tokenized)
    canonical = train(sentences, vector_size=150, window=6, seed=42)
    axes, poles = dimension_axes(canonical.wv)
    terms, means, exclusions = dictionary_projections(canonical.wv, dictionary, axes, poles)
    terms.to_csv(args.output_dir / "w3_dimension_projections.csv", index=False)
    means.to_csv(args.output_dir / "w3_category_dimension_means.csv", index=False)
    means.to_csv(args.output_dir / "w4_table6_dimension_projections.csv", index=False)
    exclusions.to_csv(args.output_dir / "corrected_embedding_pole_exclusions.csv", index=False)
    frequency_weighted_means(terms, exclusions, args.provenance).to_csv(
        args.output_dir / "corrected_embedding_frequency_weighted_means.csv", index=False
    )
    ambiguous_projection_sensitivity(
        canonical.wv, dictionary, axes, poles, means, args.ambiguous_register
    ).to_csv(args.output_dir / "corrected_ambiguous_term_embedding_sensitivity.csv", index=False)
    neighbor_audit(canonical.wv, dictionary).to_csv(args.output_dir / "w3_neighbor_audit.csv", index=False)
    weat = weat_results(canonical.wv)
    weat.to_csv(args.output_dir / "w3_weat_results.csv", index=False)
    weat.to_csv(args.output_dir / "w4_table7_weat_results.csv", index=False)
    if not args.skip_stability:
        stability = stability_run(sentences, dictionary)
        stability.to_csv(args.output_dir / "corrected_embedding_stability.csv", index=False)
        summary = {
            "runs": int(len(stability)),
            "natural_artificial_dominant_runs": int(stability["natural_artificial_dominant"].sum()),
            "flaw_artificial_direction_runs": int(stability["flaw_artificial_direction"].sum()),
        }
        (args.output_dir / "corrected_embedding_stability_summary.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(summary, indent=2))
    plot_dimensions(means, args.figure_dir)
    print(means.to_string(index=False))
    print(weat[["test", "effect_size_d", "p_value_one_sided", "p_value_holm_primary"]].to_string(index=False))


if __name__ == "__main__":
    main()
