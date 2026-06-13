"""Corrected dictionary, regression, independent-validation, and CV analyses."""

from __future__ import annotations

import argparse
import copy
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, RidgeCV
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from analysis.common import (
    DATA,
    FIGURES,
    SCOPE_LABELS,
    TEXT_SCOPES,
    build_features,
    build_tokenized,
    category_map,
    category_shorts,
    ensure_dirs,
    independent_groups,
    load_dictionary,
    merge_analysis_frame,
)


def ols_formula(scope: str, categories: list[str], include_eval: bool = True) -> str:
    cats = categories if include_eval else [c for c in categories if c != "eval"]
    terms = [f"{cat}_{scope}_per1k" for cat in cats]
    terms += [f"wordcount_{scope}", "C(review_year)"]
    return "score ~ " + " + ".join(terms)


def fit_ols(df: pd.DataFrame, categories: list[str], scope: str = "review_text", include_eval: bool = True):
    return smf.ols(ols_formula(scope, categories, include_eval), data=df).fit(cov_type="HC1")


def bootstrap_r2_ci(
    y: np.ndarray,
    predicted: np.ndarray,
    n_bootstrap: int = 2000,
    seed: int = 42,
) -> tuple[float, float]:
    """Percentile bootstrap 95% CI for R-squared on paired (y, predicted)."""
    rng = np.random.default_rng(seed)
    n = len(y)
    boot_r2 = np.empty(n_bootstrap)
    for i in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        boot_r2[i] = r2_score(y[idx], predicted[idx])
    return float(np.percentile(boot_r2, 2.5)), float(np.percentile(boot_r2, 97.5))


def bootstrap_adj_r2_ci(
    df: pd.DataFrame,
    categories: list[str],
    scope: str,
    n_bootstrap: int = 1000,
    seed: int = 42,
) -> tuple[float, float]:
    """Percentile bootstrap 95% CI for adjusted R-squared from row resampling."""
    rng = np.random.default_rng(seed)
    n = len(df)
    boot_adj = np.empty(n_bootstrap)
    for i in range(n_bootstrap):
        sample = df.iloc[rng.integers(0, n, size=n)]
        boot_adj[i] = fit_ols(sample, categories, scope).rsquared_adj
    return float(np.percentile(boot_adj, 2.5)), float(np.percentile(boot_adj, 97.5))


def coefficient_rows(model, sample: str) -> pd.DataFrame:
    conf = model.conf_int()
    rows = []
    for name in model.params.index:
        if "_per1k" not in name and "wordcount_" not in name:
            continue
        rows.append({
            "sample": sample,
            "variable": name,
            "b_unstandardized": model.params[name],
            "robust_se_hc1": model.bse[name],
            "ci_low": conf.loc[name, 0],
            "ci_high": conf.loc[name, 1],
            "t_hc1": model.tvalues[name],
            "p_hc1": model.pvalues[name],
            "n": int(model.nobs),
            "adj_r2_descriptive": model.rsquared_adj,
        })
    return pd.DataFrame(rows)


def scope_comparison(df: pd.DataFrame, categories: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    common = df.copy()
    for scope in TEXT_SCOPES:
        common = common[common[f"wordcount_{scope}"].gt(0)]
    primary = []
    supplementary = []
    for scope in TEXT_SCOPES:
        for sample_df, target in [(common, primary), (df[df[f"wordcount_{scope}"].gt(0)], supplementary)]:
            model = fit_ols(sample_df, categories, scope)
            ci_low, ci_high = bootstrap_adj_r2_ci(sample_df, categories, scope)
            target.append({
                "scope": SCOPE_LABELS[scope],
                "n": int(model.nobs),
                "adj_r2_descriptive": model.rsquared_adj,
                "adj_r2_ci_low": ci_low,
                "adj_r2_ci_high": ci_high,
                "r2_descriptive": model.rsquared,
            })
    return pd.DataFrame(primary), pd.DataFrame(supplementary)


def cohen_d(a: pd.Series, b: pd.Series) -> float:
    a, b = a.dropna(), b.dropna()
    pooled = np.sqrt(((len(a) - 1) * a.var() + (len(b) - 1) * b.var()) / (len(a) + len(b) - 2))
    return float((a.mean() - b.mean()) / pooled) if pooled else np.nan


def validate_groups(df: pd.DataFrame, categories: list[str]) -> pd.DataFrame:
    rows = []
    for group, mask in independent_groups(df).items():
        kind = "criterion association" if "score" in group.lower() else "independent metadata validation"
        for category in categories:
            value = f"{category}_review_text_per1k"
            in_group = df.loc[mask, value]
            other = df.loc[~mask, value]
            test = stats.ttest_ind(in_group, other, equal_var=False, nan_policy="omit")
            rows.append({
                "group": group,
                "validation_type": kind,
                "n_group": int(mask.sum()),
                "n_other": int((~mask).sum()),
                "category": category,
                "group_mean_per1k": in_group.mean(),
                "other_mean_per1k": other.mean(),
                "cohen_d": cohen_d(in_group, other),
                "welch_p": test.pvalue,
            })
    return pd.DataFrame(rows)


def _controls(columns: list[str]) -> ColumnTransformer:
    return ColumnTransformer([
        ("num", Pipeline([("impute", SimpleImputer()), ("scale", StandardScaler())]), columns),
        ("year", OneHotEncoder(handle_unknown="ignore"), ["review_year"]),
    ])


def predictive_estimators(
    categories: list[str], without_evaluation: list[str] | None = None
) -> dict[str, Pipeline]:
    dictionary_cols = [f"{cat}_review_text_per1k" for cat in categories]
    non_eval = without_evaluation or [cat for cat in categories if cat != "eval"]
    no_eval_cols = [f"{cat}_review_text_per1k" for cat in non_eval]
    return {
        "M0: Baseline (length + year FE)": Pipeline([
            ("features", _controls(["review_length"])), ("model", LinearRegression())
        ]),
        "M1: VADER sentiment": Pipeline([
            ("features", _controls(["review_length", "vader_compound"])), ("model", LinearRegression())
        ]),
        f"M2: Full dictionary ({len(categories)} categories)": Pipeline([
            ("features", _controls(["review_length"] + dictionary_cols)), ("model", LinearRegression())
        ]),
        f"M3: Dictionary minus explicit evaluation ({len(no_eval_cols)} categories)": Pipeline([
            ("features", _controls(["review_length"] + no_eval_cols)), ("model", LinearRegression())
        ]),
        "M4: TF-IDF / Ridge (5,000 features)": Pipeline([
            ("features", ColumnTransformer([
                ("text", TfidfVectorizer(max_features=5000, ngram_range=(1, 2), min_df=5), "review_text_original"),
                ("num", StandardScaler(), ["review_length"]),
                ("year", OneHotEncoder(handle_unknown="ignore"), ["review_year"]),
            ])),
            ("model", RidgeCV(alphas=[0.1, 1.0, 10.0, 100.0, 1000.0], cv=5)),
        ]),
    }


def outer_splitter() -> KFold:
    return KFold(n_splits=5, shuffle=True, random_state=42)


def predictive_models(
    df: pd.DataFrame, categories: list[str], without_evaluation: list[str] | None = None
) -> pd.DataFrame:
    models = predictive_estimators(categories, without_evaluation)
    splitter = outer_splitter()
    rows = []
    y = df["score"].to_numpy()
    for model_idx, (name, estimator) in enumerate(models.items()):
        predicted = cross_val_predict(estimator, df, y, cv=splitter, n_jobs=1)
        fold_r2 = []
        for train_idx, test_idx in splitter.split(df):
            fold_r2.append(r2_score(y[test_idx], predicted[test_idx]))
        ci_low, ci_high = bootstrap_r2_ci(y, predicted, seed=42 + model_idx)
        rows.append({
            "model": name,
            "evaluation": "out-of-fold 5-fold CV; random_state=42",
            "n": len(df),
            "r2_oof": r2_score(y, predicted),
            "r2_oof_ci_low": ci_low,
            "r2_oof_ci_high": ci_high,
            "r2_fold_mean": float(np.mean(fold_r2)),
            "r2_fold_sd": float(np.std(fold_r2, ddof=1)),
            "mae_oof": mean_absolute_error(y, predicted),
            "rmse_oof": np.sqrt(mean_squared_error(y, predicted)),
        })
    return pd.DataFrame(rows)


def descriptive_table(df: pd.DataFrame, categories: list[str]) -> pd.DataFrame:
    variables = {"score": "Score", "review_length": "Review Length (words)"}
    variables.update({f"{cat}_review_text_per1k": f"{cat.title()} (per 1k)" for cat in categories})
    rows = []
    for column, label in variables.items():
        values = df[column].dropna()
        rows.append({
            "variable": label, "mean": values.mean(), "median": values.median(),
            "sd": values.std(), "min": values.min(), "max": values.max(), "n": len(values),
        })
    return pd.DataFrame(rows)


def _short_context(text: str, terms: list[str], max_words: int = 7) -> str:
    words = str(text).split()
    lowered = [word.lower().strip(".,;:!?()[]'\"") for word in words]
    needles = {term.replace("_", " ").split()[0] for term in terms}
    hit = next((idx for idx, word in enumerate(lowered) if word in needles), 0)
    start = max(0, hit - 5)
    excerpt = " ".join(words[start:start + max_words])
    return excerpt + (" ..." if start + max_words < len(words) else "")


def close_reading_candidates(df: pd.DataFrame, dictionary: dict) -> pd.DataFrame:
    terms = {
        category_map(dictionary)[key]: value["terms"]
        for key, value in dictionary["categories"].items()
    }
    groups = independent_groups(df)
    selections = [
        ("Criterion-association flaw case", "flaw", df["score"].le(75)),
        ("Islay peated-style proxy case", "peat", groups["Islay assigned distillery"]),
        ("Sherry-title maturation case", "sherry", groups["Sherry title cue"]),
    ]
    rows = []
    for label, category, mask in selections:
        rate = f"{category}_review_text_per1k"
        selected = df.loc[mask].sort_values([rate, "score"], ascending=[False, True]).iloc[0]
        rows.append({
            "vignette": label,
            "category": category,
            "whisky_name_raw": selected["whisky_name_raw"],
            "distillery": selected["distillery"],
            "score": selected["score"],
            "category_rate_per1k": selected[rate],
            "source_url": selected["source_url"],
            "short_attributed_excerpt": _short_context(selected["review_text_original"], terms[category]),
        })
    return pd.DataFrame(rows)


def plot_cv(results: pd.DataFrame, figure_dir: Path) -> None:
    figure_dir.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(10, 5))
    labels = [name.split(":")[0] for name in results["model"]]
    yerr = None
    if {"r2_oof_ci_low", "r2_oof_ci_high"}.issubset(results.columns):
        yerr = np.vstack([
            results["r2_oof"] - results["r2_oof_ci_low"],
            results["r2_oof_ci_high"] - results["r2_oof"],
        ])
    bars = plt.bar(labels, results["r2_oof"], color="#315a76", yerr=yerr, capsize=4)
    plt.ylabel("Out-of-fold R2")
    plt.title("Corrected predictive comparison (5-fold cross-validation)")
    for bar, value in zip(bars, results["r2_oof"]):
        plt.text(bar.get_x() + bar.get_width() / 2, value + 0.01, f"{value:.3f}", ha="center")
    plt.tight_layout()
    plt.savefig(figure_dir / "fig_corrected_model_comparison.png", dpi=180)
    plt.savefig(figure_dir / "fig_corrected_model_comparison.pdf")
    plt.close()


def plot_scope_r2(scopes: pd.DataFrame, figure_dir: Path) -> None:
    figure_dir.mkdir(parents=True, exist_ok=True)
    order = [
        "Nose", "Mouth", "Finish", "Comments",
        "Nose + Mouth + Finish", "Full Text",
    ]
    plot_df = scopes.set_index("scope").loc[order].reset_index()
    plt.figure(figsize=(10, 5))
    yerr = None
    if {"adj_r2_ci_low", "adj_r2_ci_high"}.issubset(plot_df.columns):
        yerr = np.vstack([
            plot_df["adj_r2_descriptive"] - plot_df["adj_r2_ci_low"],
            plot_df["adj_r2_ci_high"] - plot_df["adj_r2_descriptive"],
        ])
    bars = plt.bar(plot_df["scope"], plot_df["adj_r2_descriptive"], color="#315a76", yerr=yerr, capsize=4)
    plt.ylabel("Adjusted R2")
    plt.title("Adjusted R2 by review section")
    plt.xticks(rotation=25, ha="right")
    for bar, value in zip(bars, plot_df["adj_r2_descriptive"]):
        plt.text(bar.get_x() + bar.get_width() / 2, value + 0.01, f"{value:.3f}", ha="center", fontsize=8)
    plt.tight_layout()
    plt.savefig(figure_dir / "fig_corrected_r2_by_scope.png", dpi=180)
    plt.savefig(figure_dir / "fig_corrected_r2_by_scope.pdf")
    plt.close()


def export_paper_figures(
    predictions: pd.DataFrame,
    scopes: pd.DataFrame,
    paper_figure_dir: Path,
) -> None:
    """Export publication figures for paper/tex_paper/figure/."""
    paper_figure_dir.mkdir(parents=True, exist_ok=True)
    model_labels = ["M0", "M1", "M2", "M3", "M4"]
    plt.figure(figsize=(10, 4.5))
    yerr = np.vstack([
        predictions["r2_oof"] - predictions["r2_oof_ci_low"],
        predictions["r2_oof_ci_high"] - predictions["r2_oof"],
    ])
    bars = plt.bar(model_labels, predictions["r2_oof"], color="#375a7f", yerr=yerr, capsize=4)
    plt.ylabel("Out-of-fold $R^2$")
    plt.ylim(0, max(predictions["r2_oof_ci_high"]) * 1.15)
    for bar, value in zip(bars, predictions["r2_oof"]):
        plt.text(bar.get_x() + bar.get_width() / 2, value + 0.015, f"{value:.3f}", ha="center", fontsize=9)
    plt.tight_layout()
    plt.savefig(paper_figure_dir / "fig1_model_comparison.pdf")
    plt.savefig(paper_figure_dir / "fig1_model_comparison.png", dpi=180)
    plt.close()

    order = ["Nose", "Mouth", "Finish", "Comments", "Nose + Mouth + Finish", "Full Text"]
    plot_df = scopes.set_index("scope").loc[order].reset_index()
    plt.figure(figsize=(10, 4.5))
    yerr = np.vstack([
        plot_df["adj_r2_descriptive"] - plot_df["adj_r2_ci_low"],
        plot_df["adj_r2_ci_high"] - plot_df["adj_r2_descriptive"],
    ])
    bars = plt.bar(plot_df["scope"], plot_df["adj_r2_descriptive"], color="#375a7f", yerr=yerr, capsize=4)
    plt.ylabel("Adjusted $R^2$")
    plt.xticks(rotation=25, ha="right")
    plt.ylim(0, max(plot_df["adj_r2_ci_high"]) * 1.15)
    for bar, value in zip(bars, plot_df["adj_r2_descriptive"]):
        plt.text(bar.get_x() + bar.get_width() / 2, value + 0.008, f"{value:.3f}", ha="center", fontsize=8)
    plt.tight_layout()
    plt.savefig(paper_figure_dir / "fig2_r2_by_scope.pdf")
    plt.savefig(paper_figure_dir / "fig2_r2_by_scope.png", dpi=180)
    plt.close()


def ambiguous_model_sensitivity(
    tokenized: pd.DataFrame, dictionary: dict, df: pd.DataFrame, categories: list[str], ambiguous_path: Path
) -> pd.DataFrame:
    if not ambiguous_path.exists():
        return pd.DataFrame()
    register = pd.read_csv(ambiguous_path, keep_default_na=False)
    mapping = category_map(dictionary)
    baseline = fit_ols(df, categories)
    rows = []
    for _, item in register[register["decision"].eq("exclude_ambiguous")].iterrows():
        term = item["term"]
        for category in str(item["alternate_categories"]).split(";"):
            if category not in mapping:
                continue
            scenario = copy.deepcopy(dictionary)
            scenario["categories"][category]["terms"] = sorted(
                set(scenario["categories"][category]["terms"] + [term])
            )
            features = build_features(tokenized, scenario)
            model = fit_ols(merge_analysis_frame(tokenized, features), categories)
            variable = f"{mapping[category]}_review_text_per1k"
            rows.append(
                {
                    "term": term,
                    "assigned_category": mapping[category],
                    "variable": variable,
                    "base_b": baseline.params[variable],
                    "sensitivity_b": model.params[variable],
                    "delta_b": model.params[variable] - baseline.params[variable],
                    "sign_changed": np.sign(model.params[variable]) != np.sign(baseline.params[variable]),
                    "analysis_role": "ambiguous-term sensitivity; not primary measurement",
                }
            )
    return pd.DataFrame(rows)


def ambiguous_validation_sensitivity(
    tokenized: pd.DataFrame, dictionary: dict, df: pd.DataFrame, categories: list[str], ambiguous_path: Path
) -> pd.DataFrame:
    if not ambiguous_path.exists():
        return pd.DataFrame()
    register = pd.read_csv(ambiguous_path, keep_default_na=False)
    mapping = category_map(dictionary)
    base = validate_groups(df, categories)
    groups = ["Islay assigned distillery", "Sherry title cue", "Bourbon title cue"]
    rows = []
    for _, item in register[register["decision"].eq("exclude_ambiguous")].iterrows():
        term = item["term"]
        for category in str(item["alternate_categories"]).split(";"):
            if category not in mapping:
                continue
            short = mapping[category]
            scenario = copy.deepcopy(dictionary)
            scenario["categories"][category]["terms"] = sorted(
                set(scenario["categories"][category]["terms"] + [term])
            )
            features = build_features(tokenized, scenario)
            revised = validate_groups(merge_analysis_frame(tokenized, features), categories)
            for group in groups:
                primary = base[base["group"].eq(group) & base["category"].eq(short)].iloc[0]
                sensitivity = revised[
                    revised["group"].eq(group) & revised["category"].eq(short)
                ].iloc[0]
                rows.append(
                    {
                        "term": term,
                        "assigned_category": short,
                        "group": group,
                        "primary_cohen_d": primary["cohen_d"],
                        "sensitivity_cohen_d": sensitivity["cohen_d"],
                        "delta_d": sensitivity["cohen_d"] - primary["cohen_d"],
                        "sign_changed": np.sign(sensitivity["cohen_d"]) != np.sign(primary["cohen_d"]),
                        "analysis_role": "ambiguous-term validation sensitivity; not primary measurement",
                    }
                )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DATA / "whiskyfun_analytical_dataset.csv")
    parser.add_argument("--dictionary", type=Path, default=DATA / "whiskyfun_dictionary_v2.json")
    parser.add_argument("--output-dir", type=Path, default=DATA / "v2")
    parser.add_argument("--figure-dir", type=Path, default=FIGURES / "v2")
    parser.add_argument(
        "--paper-figure-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "paper" / "tex_paper" / "figure",
    )
    parser.add_argument("--ambiguous-register", type=Path, default=DATA / "dictionary_v2_ambiguous_terms.csv")
    args = parser.parse_args()
    dictionary = load_dictionary(args.dictionary)
    ensure_dirs()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    categories = category_shorts(dictionary)
    mapping = category_map(dictionary)
    without_evaluation = [
        mapping[key]
        for key, details in dictionary["categories"].items()
        if details.get("include_without_evaluation", True)
    ]
    tokenized = build_tokenized(args.dataset, args.output_dir / "whiskyfun_tokenized.parquet")
    features = build_features(tokenized, dictionary, args.output_dir / "whiskyfun_dict_features.parquet")
    df = merge_analysis_frame(tokenized, features)

    full = fit_ols(df, categories)
    tier1 = fit_ols(df[df["match_source"].eq("index")], categories)
    coefficients = pd.concat([
        coefficient_rows(full, "All reviews"),
        coefficient_rows(tier1, "Tier 1 index-matched only"),
    ], ignore_index=True)
    coefficients.to_csv(args.output_dir / "corrected_ols_coefficients.csv", index=False)
    coefficients[coefficients["sample"].eq("All reviews")].to_csv(
        args.output_dir / "w4_table3_regression_coefficients.csv", index=False
    )

    sensitivity = pd.DataFrame([
        {"sample": "All reviews", "n": int(full.nobs), "adj_r2_descriptive": full.rsquared_adj},
        {"sample": "Tier 1 index-matched only", "n": int(tier1.nobs), "adj_r2_descriptive": tier1.rsquared_adj},
    ])
    sensitivity.to_csv(args.output_dir / "corrected_tier1_sensitivity.csv", index=False)
    primary_scopes, supplement_scopes = scope_comparison(df, categories)
    primary_scopes.to_csv(args.output_dir / "w4_table4_r2_by_scope.csv", index=False)
    supplement_scopes.to_csv(args.output_dir / "corrected_scope_supplementary_variable_n.csv", index=False)

    validation = validate_groups(df, categories)
    validation.to_csv(args.output_dir / "corrected_independent_group_validation.csv", index=False)
    validation.to_csv(args.output_dir / "w4_table5_known_groups.csv", index=False)
    predictions = predictive_models(df, categories, without_evaluation)
    predictions.to_csv(args.output_dir / "corrected_predictive_comparison.csv", index=False)
    predictions.to_csv(args.output_dir / "w4_table2_model_comparison.csv", index=False)
    descriptive_table(df, categories).to_csv(args.output_dir / "w4_table1_descriptive_stats.csv", index=False)
    close_reading_candidates(df, dictionary).to_csv(args.output_dir / "corrected_close_reading_vignettes.csv", index=False)
    ambiguous_model_sensitivity(tokenized, dictionary, df, categories, args.ambiguous_register).to_csv(
        args.output_dir / "corrected_ambiguous_term_model_sensitivity.csv", index=False
    )
    ambiguous_validation_sensitivity(tokenized, dictionary, df, categories, args.ambiguous_register).to_csv(
        args.output_dir / "corrected_ambiguous_term_validation_sensitivity.csv", index=False
    )
    plot_cv(predictions, args.figure_dir)
    plot_scope_r2(primary_scopes, args.figure_dir)
    export_paper_figures(predictions, primary_scopes, args.paper_figure_dir)
    print(predictions.to_string(index=False))
    print(f"Wrote corrected model outputs to {args.output_dir}")
    print(f"Exported paper figures to {args.paper_figure_dir}")


if __name__ == "__main__":
    main()
