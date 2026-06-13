"""Construct and approve the Version 2 tasting-language instrument."""

from __future__ import annotations

import argparse
import copy
import json
import re
from collections import OrderedDict
from pathlib import Path

import pandas as pd

from .common import DATA, ROOT, canonical_dictionary_term

V1_DICTIONARY = ROOT / "_local" / "archive" / "v1" / "data" / "whiskyfun_dictionary_v1.json"

MIN_REVIEW_FREQUENCY = 10
DECISIONS = {
    "approve_primary",
    "exclude_ambiguous",
    "exclude_irrelevant",
    "exclude_infrequent",
}

V2_CATEGORIES = OrderedDict(
    [
        ("fruit", {"short_name": "fruit", "display_label": "Fruit", "construct": "Fresh, citrus, tropical, and orchard fruit descriptors.", "include_without_evaluation": True}),
        ("floral", {"short_name": "floral", "display_label": "Floral", "construct": "Flower and blossom descriptors.", "include_without_evaluation": True}),
        ("spice", {"short_name": "spice", "display_label": "Spice", "construct": "Culinary spice descriptors.", "include_without_evaluation": True}),
        ("peat_smoke_coastal", {"short_name": "peat", "display_label": "Peat, smoke, and coastal", "construct": "Peat, smoke, ash, maritime, and coastal descriptors.", "include_without_evaluation": True}),
        ("sherry_influence", {"short_name": "sherry", "display_label": "Sherry influence", "construct": "Direct sherry-cask references and reviewed berry or dried-fruit sensory markers of sherry influence.", "include_without_evaluation": True}),
        ("oak_cask_wood", {"short_name": "oak", "display_label": "Oak and cask", "construct": "Wood and cask influence.", "include_without_evaluation": True}),
        ("texture_body", {"short_name": "texture", "display_label": "Texture and body", "construct": "Mouthfeel and bodily texture.", "include_without_evaluation": True}),
        ("mineral_earth_farmy", {"short_name": "mineral", "display_label": "Mineral, earth, and farmy", "construct": "Mineral, earth, grain, and agricultural descriptors.", "include_without_evaluation": True}),
        ("flaws_off_notes", {"short_name": "flaw", "display_label": "Flaws and off-notes", "construct": "Defect and contamination descriptors.", "include_without_evaluation": True}),
        ("complexity_balance", {"short_name": "structure", "display_label": "Complexity and balance", "construct": "Structural judgment language.", "include_without_evaluation": True}),
        ("explicit_evaluation", {"short_name": "eval", "display_label": "Explicit evaluation", "construct": "Direct praise and blame language.", "include_without_evaluation": False}),
    ]
)

FRUIT_SPLITS = {
    "floral": {"floral", "rose", "violet", "lavender", "heather"},
    "spice": {"ginger", "cinnamon", "nutmeg", "clove", "aniseed"},
}
SHERRY_INFLUENCE_FRUIT_CANDIDATES = {
    "berry",
    "blackberry",
    "blueberry",
    "cranberry",
    "gooseberry",
    "blackcurrant",
    "redcurrant",
    "red_berry",
    "dark_berry",
    "raspberry",
    "strawberry",
    "date",
    "dried_apricot",
    "dried_citrus",
    "dried_fig",
    "dried_fruit",
    "fig",
    "prune",
    "raisin",
    "sultana",
    "currant",
}
USER_PROPOSED = {
    "violet": "floral",
    "ashy": "peat_smoke_coastal",
    "bbq": "peat_smoke_coastal",
    "barbecue": "peat_smoke_coastal",
    "sea_breeze": "peat_smoke_coastal",
    "manzanilla": "sherry_influence",
    "palo_cortado": "sherry_influence",
    "cream_sherry": "sherry_influence",
    "pedro_ximenez": "sherry_influence",
    "bodega": "sherry_influence",
    "ex_bodega": "sherry_influence",
    "jerez": "sherry_influence",
    "solera": "sherry_influence",
    **{term: "sherry_influence" for term in SHERRY_INFLUENCE_FRUIT_CANDIDATES},
}
CORPUS_EXPANSION = {
    "flower": "floral",
    "blossom": "floral",
    "orange_blossom": "floral",
    "honeysuckle": "floral",
    "jasmine": "floral",
    "pepper": "spice",
    "peppery": "spice",
    "black_pepper": "spice",
    "white_pepper": "spice",
    "cardamom": "spice",
    "caraway": "spice",
    "coriander": "spice",
    "star_anise": "spice",
    "anise": "spice",
    "allspice": "spice",
}
RECLASSIFICATIONS = {
    "peppery": "spice",
    "date": "sherry_influence",
    "dried_fruit": "sherry_influence",
    "prune": "sherry_influence",
}
DESIGN_EXCLUSIONS = {
    "mint": ("exclude_irrelevant", "Herbal/tea is not retained as a primary construct in the simplified Version 2 instrument."),
    "herbal": ("exclude_irrelevant", "Herbal/tea is not retained as a primary construct in the simplified Version 2 instrument."),
    "black_tea": ("exclude_irrelevant", "Herbal/tea is not retained as a primary construct in the simplified Version 2 instrument."),
    "green_tea": ("exclude_irrelevant", "Herbal/tea is not retained as a primary construct in the simplified Version 2 instrument."),
    "earl_grey": ("exclude_irrelevant", "Herbal/tea is not retained as a primary construct in the simplified Version 2 instrument."),
}
AMBIGUOUS = {
    "tcp": ("peat_smoke_coastal;flaws_off_notes", "Peat character versus defect."),
    "sulphur": ("flaws_off_notes;off_primary", "Defect cue versus contextual note."),
    "polish": ("sherry_influence;flaws_off_notes", "Possible cask association versus solvent defect."),
    "farmyard": ("mineral_earth_farmy;flaws_off_notes", "Agricultural cue versus defect."),
    "barnyard": ("mineral_earth_farmy;flaws_off_notes", "Agricultural cue versus defect."),
    "manure": ("mineral_earth_farmy;flaws_off_notes", "Agricultural cue versus defect."),
    "medicinal": ("peat_smoke_coastal;flaws_off_notes", "Peat style versus medicinal defect."),
    "antiseptic": ("peat_smoke_coastal;flaws_off_notes", "Peat style versus medicinal defect."),
    "bandage": ("peat_smoke_coastal;flaws_off_notes", "Peat style versus medicinal defect."),
    "phenolic": ("peat_smoke_coastal;flaws_off_notes", "Peat style versus off-note."),
    "creosote": ("peat_smoke_coastal;flaws_off_notes", "Peat style versus contamination."),
    "diesel": ("peat_smoke_coastal;flaws_off_notes", "Peat style versus contamination."),
    "engine_oil": ("peat_smoke_coastal;flaws_off_notes", "Peat style versus contamination."),
    "date": ("fruit;sherry_influence;exclude_primary", "Dried-fruit descriptor strongly associated with sherry style but not a direct cask reference."),
    "dried_fruit": ("fruit;sherry_influence;exclude_primary", "Dried-fruit descriptor strongly associated with sherry style but not a direct cask reference."),
    "prune": ("fruit;sherry_influence;exclude_primary", "Dried-fruit descriptor strongly associated with sherry style but not a direct cask reference."),
    "raisin": ("fruit;sherry_influence;exclude_primary", "Dried-fruit descriptor strongly associated with sherry style but not a direct cask reference."),
    "fig": ("fruit;sherry_influence;exclude_primary", "Dried-fruit descriptor strongly associated with sherry style but not a direct cask reference."),
    "solera": ("sherry_influence;exclude_primary", "A maturation-system term that is not uniquely a direct sherry-cask cue in whisky prose."),
    "jam": ("fruit;exclude_primary", "Prepared-fruit descriptor outside the narrowed fresh-fruit definition."),
    "marmalade": ("fruit;exclude_primary", "Prepared-fruit descriptor outside the narrowed fresh-fruit definition."),
    "rancio": ("rancio_aged_oxidative;exclude_primary", "Aged oxidative character rather than a direct sherry-cask cue."),
    "balsamic": ("rancio_aged_oxidative;exclude_primary", "Possible aged oxidative character rather than a direct sherry-cask cue."),
    "old_book": ("rancio_aged_oxidative;exclude_primary", "Aged-character analogy rather than a direct sherry-cask cue."),
    "antique": ("rancio_aged_oxidative;exclude_primary", "Aged-character analogy rather than a direct sherry-cask cue."),
}
for _term in SHERRY_INFLUENCE_FRUIT_CANDIDATES:
    AMBIGUOUS.setdefault(
        _term,
        (
            "fruit;sherry_influence;exclude_primary",
            "Berry or dried-fruit descriptor proposed as sherry influence but requiring explicit boundary review.",
        ),
    )
SHERRY_ASSOCIATED_NOT_DIRECT = {
    "tobacco", "walnut", "leather", "coffee", "almond", "marzipan",
    "pipe_tobacco", "fudge", "toffee", "cigar", "chestnut", "cocoa",
    "nougat", "dark_chocolate", "cedar", "molasses", "fruitcake", "mocha",
    "treacle", "espresso", "hazelnut", "incense", "church",
}
ADJUDICATION_COLUMNS = [
    "term",
    "prior_v1_category",
    "proposed_v2_category",
    "candidate_source",
    "review_frequency",
    "construct_definition",
    "ambiguity_flag",
    "alternate_categories",
    "concordance_1",
    "concordance_2",
    "concordance_3",
    "decision",
    "reviewer_rationale",
    "reviewer_status",
]


def term_regex(term: str) -> re.Pattern[str]:
    surface = re.escape(term).replace("_", r"[\s_-]+")
    return re.compile(rf"(?<![a-z]){surface}(?![a-z])", flags=re.IGNORECASE)


def review_frequency(text: pd.Series, term: str) -> int:
    return int(text.fillna("").str.contains(term_regex(term), regex=True).sum())


def concordances(text: pd.Series, term: str, limit: int = 3) -> list[str]:
    pattern = term_regex(term)
    snippets: list[str] = []
    for value in text.fillna(""):
        match = pattern.search(value)
        if not match:
            continue
        start = max(0, match.start() - 85)
        end = min(len(value), match.end() + 85)
        snippets.append(re.sub(r"\s+", " ", value[start:end]).strip())
        if len(snippets) == limit:
            break
    return snippets + [""] * (limit - len(snippets))


def proposed_category(prior: str, term: str) -> str:
    if term in RECLASSIFICATIONS:
        return RECLASSIFICATIONS[term]
    if term in USER_PROPOSED:
        return USER_PROPOSED[term]
    if prior == "fruit_aromatics":
        for category, terms in FRUIT_SPLITS.items():
            if term in terms:
                return category
        return "fruit"
    if prior == "sherry_rancio_oxidative":
        return "sherry_influence"
    if prior == "finish_complexity_balance":
        return "complexity_balance"
    return prior


def candidate_frame(tokenized: pd.DataFrame, v1: dict) -> pd.DataFrame:
    candidates: dict[str, dict] = {}
    for prior, category in v1["categories"].items():
        for term in category["terms"]:
            if term in DESIGN_EXCLUSIONS:
                continue
            candidates[term] = {
                "term": term,
                "prior_v1_category": prior,
                "proposed_v2_category": proposed_category(prior, term),
                "candidate_source": "v1",
            }
    for term, category in USER_PROPOSED.items():
        candidates.setdefault(term, {"term": term, "prior_v1_category": "", "proposed_v2_category": category, "candidate_source": "user_proposed"})
    for term, category in CORPUS_EXPANSION.items():
        candidates.setdefault(term, {"term": term, "prior_v1_category": "", "proposed_v2_category": category, "candidate_source": "corpus_expansion"})

    for term in list(candidates):
        canonical = canonical_dictionary_term(term)
        if canonical == term:
            continue
        if canonical in candidates:
            del candidates[term]

    rows = []
    text = tokenized["review_text"]
    for term, row in candidates.items():
        category = row["proposed_v2_category"]
        ambiguity = False
        alternate = ""
        decision = ""
        rationale = ""
        status = ""
        if term in AMBIGUOUS:
            ambiguity = True
            alternate, _ = AMBIGUOUS[term]
        elif category == "sherry_influence" and term in SHERRY_ASSOCIATED_NOT_DIRECT:
            ambiguity = True
            alternate = "sherry_influence;exclude_primary"
        elif term == "honey":
            ambiguity = True
            alternate = "fruit;exclude_primary"
        snippets = concordances(text, term)
        rows.append(
            {
                **row,
                "review_frequency": review_frequency(text, term),
                "construct_definition": V2_CATEGORIES[category]["construct"],
                "ambiguity_flag": ambiguity,
                "alternate_categories": alternate,
                "concordance_1": snippets[0],
                "concordance_2": snippets[1],
                "concordance_3": snippets[2],
                "decision": decision,
                "reviewer_rationale": rationale,
                "reviewer_status": status,
            }
        )
    order = {key: index for index, key in enumerate(V2_CATEGORIES)}
    return (
        pd.DataFrame(rows, columns=ADJUDICATION_COLUMNS)
        .assign(_order=lambda frame: frame["proposed_v2_category"].map(order))
        .sort_values(["_order", "term"])
        .drop(columns="_order")
        .reset_index(drop=True)
    )


def write_candidates(tokenized_path: Path, v1_path: Path, output_dir: Path, overwrite: bool = False) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    adjudication_path = output_dir / "dictionary_v2_adjudication.csv"
    if adjudication_path.exists() and not overwrite:
        raise FileExistsError(f"{adjudication_path} already exists; refusing to overwrite reviewer work. Use --overwrite only to restart adjudication.")
    tokenized = pd.read_parquet(tokenized_path)
    with v1_path.open(encoding="utf-8") as handle:
        v1 = json.load(handle)
    adjudication = candidate_frame(tokenized, v1)
    adjudication.to_csv(adjudication_path, index=False)
    adjudication[adjudication["ambiguity_flag"]].to_csv(output_dir / "dictionary_v2_ambiguous_terms.csv", index=False)
    excluded_rows = []
    for term, (decision, rationale) in DESIGN_EXCLUSIONS.items():
        excluded_rows.append(
            {
                "term": term,
                "proposed_v2_category": "excluded_by_construct_design",
                "review_frequency": review_frequency(tokenized["review_text"], term),
                "decision": decision,
                "reviewer_rationale": rationale,
                "reviewer_status": "design_decision",
            }
        )
    pd.DataFrame(excluded_rows).to_csv(output_dir / "dictionary_v2_exclusions.csv", index=False)
    print(f"Wrote blinded adjudication packet with {len(adjudication)} candidates to {output_dir}.")


def validate_approval(adjudication: pd.DataFrame) -> list[str]:
    missing = [column for column in ADJUDICATION_COLUMNS if column not in adjudication.columns]
    if missing:
        return [f"Adjudication file lacks required columns: {', '.join(missing)}"]
    errors: list[str] = []
    for _, row in adjudication.iterrows():
        term = str(row["term"])
        decision = str(row["decision"]).strip()
        rationale = str(row["reviewer_rationale"]).strip()
        status = str(row["reviewer_status"]).strip()
        category = str(row["proposed_v2_category"]).strip()
        if decision not in DECISIONS:
            errors.append(f"{term}: missing or invalid decision.")
        if not rationale:
            errors.append(f"{term}: missing reviewer rationale.")
        if status != "approved":
            errors.append(f"{term}: reviewer_status must be approved.")
        if category not in V2_CATEGORIES:
            errors.append(f"{term}: unknown proposed category {category}.")
        if decision == "approve_primary":
            if int(row["review_frequency"]) < MIN_REVIEW_FREQUENCY:
                errors.append(f"{term}: approved term has fewer than {MIN_REVIEW_FREQUENCY} reviews.")
    approved = adjudication[adjudication["decision"] == "approve_primary"]
    for term in approved[approved["term"].duplicated(keep=False)]["term"].unique():
        errors.append(f"{term}: primary term appears more than once.")
    missing_categories = set(V2_CATEGORIES) - set(approved["proposed_v2_category"])
    if missing_categories:
        errors.append("No approved primary terms for categories: " + ", ".join(sorted(missing_categories)) + ".")
    return errors


def freeze(adjudication_path: Path, output_dir: Path) -> None:
    adjudication = pd.read_csv(adjudication_path, keep_default_na=False)
    errors = validate_approval(adjudication)
    if errors:
        preview = "\n".join(f"- {error}" for error in errors[:25])
        suffix = "" if len(errors) <= 25 else f"\n- ... and {len(errors) - 25} more errors."
        raise ValueError(f"Version 2 freeze blocked:\n{preview}{suffix}")
    approved = adjudication[adjudication["decision"] == "approve_primary"]
    dictionary = {
        "version": "v2",
        "status": "approved_primary_instrument",
        "approval_basis": "Blind term-level adjudication with recorded rationale and concordances.",
        "minimum_review_frequency": MIN_REVIEW_FREQUENCY,
        "total_terms": int(len(approved)),
        "categories": OrderedDict(),
    }
    for key, metadata in V2_CATEGORIES.items():
        terms = sorted(approved.loc[approved["proposed_v2_category"] == key, "term"].tolist())
        dictionary["categories"][key] = {**copy.deepcopy(metadata), "term_count": len(terms), "terms": terms}
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "whiskyfun_dictionary_v2.json").open("w", encoding="utf-8") as handle:
        json.dump(dictionary, handle, indent=2)
        handle.write("\n")
    adjudication.to_csv(output_dir / "dictionary_v2_provenance.csv", index=False)
    lines = [
        "# Version 2 Dictionary Approval Report",
        "",
        "Version 2 is frozen as the primary instrument only after blinded term-level review.",
        "",
        f"- Approved primary terms: {len(approved)}",
        f"- Excluded ambiguous terms: {(adjudication['decision'] == 'exclude_ambiguous').sum()}",
        f"- Other excluded terms: {adjudication['decision'].isin({'exclude_irrelevant', 'exclude_infrequent'}).sum()}",
        f"- Frequency threshold: {MIN_REVIEW_FREQUENCY} reviews",
        "",
        "## Approved Categories",
        "",
        "| Category | Short name | Approved terms |",
        "| --- | --- | ---: |",
    ]
    for key, metadata in dictionary["categories"].items():
        lines.append(f"| {key} | {metadata['short_name']} | {metadata['term_count']} |")
    lines.extend(
        [
            "",
            "## Measurement Status",
            "",
            "Version 1 is retained only as historical and sensitivity evidence because its construct boundaries and approval traceability were inadequate for primary interpretation.",
            "",
            "Context-dependent terms recorded as ambiguous are omitted from primary rates and may be introduced only in explicitly labeled sensitivity scenarios.",
        ]
    )
    (output_dir / "dictionary_v2_approval_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Frozen Version 2 instrument with {len(approved)} primary terms.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    candidate_parser = subparsers.add_parser("candidate")
    candidate_parser.add_argument("--tokenized", type=Path, default=DATA / "whiskyfun_tokenized.parquet")
    candidate_parser.add_argument("--v1", type=Path, default=V1_DICTIONARY)
    candidate_parser.add_argument("--output-dir", type=Path, default=DATA)
    candidate_parser.add_argument("--overwrite", action="store_true")
    freeze_parser = subparsers.add_parser("freeze")
    freeze_parser.add_argument("--adjudication", type=Path, default=DATA / "dictionary_v2_adjudication.csv")
    freeze_parser.add_argument("--output-dir", type=Path, default=DATA)
    args = parser.parse_args()
    if args.command == "candidate":
        write_candidates(args.tokenized, args.v1, args.output_dir, overwrite=args.overwrite)
    else:
        freeze(args.adjudication, args.output_dir)


if __name__ == "__main__":
    main()
