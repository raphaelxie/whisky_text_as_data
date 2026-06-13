"""Shared data, text, dictionary, and statistical helpers."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from nltk.stem import WordNetLemmatizer

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
FIGURES = ROOT / "figures"
PAPER = ROOT / "paper"
TEXT_SCOPES = ["review_text", "nose", "mouth", "finish", "comments", "nmf"]
SCOPE_LABELS = {
    "review_text": "Full Text",
    "nose": "Nose",
    "mouth": "Mouth",
    "finish": "Finish",
    "comments": "Comments",
    "nmf": "Nose + Mouth + Finish",
}
LEGACY_CAT_SHORT = {
    "fruit_aromatics": "fruit",
    "peat_smoke_coastal": "peat",
    "sherry_rancio_oxidative": "sherry",
    "oak_cask_wood": "oak",
    "texture_body": "texture",
    "mineral_earth_farmy": "mineral",
    "flaws_off_notes": "flaw",
    "complexity_balance": "structure",
    "finish_complexity_balance": "structure",
    "explicit_evaluation": "eval",
}
PRIMARY_DICTIONARY = DATA / "whiskyfun_dictionary_v2.json"
ISLAY_DISTILLERIES = {
    "Ardbeg", "Bowmore", "Bruichladdich", "Bunnahabhain", "Caol Ila",
    "Kilchoman", "Lagavulin", "Laphroaig", "Octomore", "Port Charlotte",
    "Port Ellen",
}
SHERRY_CUE = re.compile(
    r"\b(?:sherry|oloroso|px|pedro\s+xim[eé]nez|amontillado|fino|manzanilla)\b",
    re.IGNORECASE,
)
BOURBON_CUE = re.compile(r"\b(?:bourbon|barrel|hogshead)\b", re.IGNORECASE)
PUNCTUATED_WORD = re.compile(r"^([^A-Za-z]*)([A-Za-z]+)([^A-Za-z]*)$")


def lemma_noun_token(word: str, lemmatizer: WordNetLemmatizer | None = None) -> str:
    """Singularize a single-word noun token; fallback when WordNet leaves plurals unchanged."""
    lowered = word.lower()
    if not lowered.isalpha() or len(lowered) <= 2:
        return lowered
    stemmer = lemmatizer or WordNetLemmatizer()
    lemma = stemmer.lemmatize(lowered, pos="n")
    if lemma != lowered:
        return lemma
    if len(lowered) > 3 and lowered.endswith("s"):
        if lowered.endswith("ies") and len(lowered) > 4:
            y_form = stemmer.lemmatize(lowered[:-3] + "y", pos="n")
            if y_form != lowered:
                return y_form
        if lowered.endswith("es"):
            es_form = stemmer.lemmatize(lowered[:-2], pos="n")
            if es_form != lowered[:-2]:
                return es_form
        s_form = stemmer.lemmatize(lowered[:-1], pos="n")
        if s_form != lowered[:-1]:
            return s_form
    return lowered


def canonical_dictionary_term(term: str) -> str:
    """Map dictionary term surfaces to a canonical singular lemma (single-word terms only)."""
    if "_" in term:
        return term.lower()
    return lemma_noun_token(term)


def load_dictionary(path: Path | None = None) -> dict:
    selected = path or PRIMARY_DICTIONARY
    if not selected.exists():
        raise FileNotFoundError(
            f"Primary Version 2 dictionary has not been frozen: {selected}. "
            "Complete data/dictionary_v2_adjudication.csv and run "
            "`python -m analysis.dictionary freeze` first. For historical V1 "
            "reproduction, explicitly pass _local/archive/v1/data/whiskyfun_dictionary_v1.json."
        )
    with selected.open(encoding="utf-8") as f:
        return json.load(f)


def category_map(dictionary: dict) -> dict[str, str]:
    result = {}
    for category, details in dictionary["categories"].items():
        short = details.get("short_name") or LEGACY_CAT_SHORT.get(category)
        if not short:
            raise ValueError(f"Dictionary category has no short name: {category}")
        if short in result.values():
            raise ValueError(f"Dictionary contains duplicate short name: {short}")
        result[category] = short
    return result


def category_shorts(dictionary: dict) -> list[str]:
    return list(category_map(dictionary).values())


def _phrase_patterns() -> list[tuple[str, re.Pattern[str]]]:
    phrases = json.loads((DATA / "whiskyfun_phrases.json").read_text(encoding="utf-8"))
    phrases += json.loads((DATA / "whiskyfun_bigrams.json").read_text(encoding="utf-8"))
    result = []
    for phrase in sorted(set(phrases), key=lambda item: (len(item), item), reverse=True):
        words = re.escape(phrase.replace("_", " ")).replace(r"\ ", r"[\s_-]+")
        result.append((phrase, re.compile(r"\b" + words + r"(?:e?s)?\b", re.IGNORECASE)))
    return result


def preprocess_text(text: object, patterns: list[tuple[str, re.Pattern[str]]] | None = None) -> str:
    if pd.isna(text) or not str(text).strip():
        return ""
    value = str(text).translate(str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": " "}))
    value = re.sub(r"\bpu[\s_-]?(?:ehr|her)\b", "pu erh", value, flags=re.IGNORECASE)
    value = re.sub(r"(?<=[A-Za-z])-(?=[A-Za-z])", "_", value)
    for phrase, pattern in patterns or _phrase_patterns():
        value = pattern.sub(phrase, value)
    lemmatizer = WordNetLemmatizer()
    tokens = []
    for token in value.split():
        lowered = token.lower()
        if "_" in token:
            tokens.append(lowered)
            continue
        if token.isalpha():
            tokens.append(lemma_noun_token(lowered, lemmatizer))
            continue
        punctuated_word = PUNCTUATED_WORD.fullmatch(token)
        if punctuated_word and len(punctuated_word.group(2)) > 2:
            prefix, word, suffix = punctuated_word.groups()
            tokens.append(prefix + lemma_noun_token(word, lemmatizer) + suffix)
        else:
            tokens.append(lowered)
    return " ".join(tokens)


def build_tokenized(
    dataset_path: Path | None = None, output_path: Path | None = None
) -> pd.DataFrame:
    df = pd.read_csv(dataset_path or DATA / "whiskyfun_analytical_dataset.csv")
    patterns = _phrase_patterns()
    df["review_text_original"] = df["review_text"].fillna("")
    for scope in TEXT_SCOPES:
        df[scope] = df[scope].apply(lambda value: preprocess_text(value, patterns))
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(output_path, index=False)
    return df


def dictionary_patterns(dictionary: dict) -> dict[str, re.Pattern[str]]:
    result = {}
    for category, short in category_map(dictionary).items():
        terms = sorted(dictionary["categories"][category]["terms"], key=len, reverse=True)
        surfaces = [re.escape(term).replace("_", r"[\s_-]+") for term in terms]
        result[short] = re.compile(
            r"\b(?:" + "|".join(surfaces) + r")\b",
            re.IGNORECASE,
        )
    return result


def build_features(
    tokenized: pd.DataFrame, dictionary: dict, output_path: Path | None = None
) -> pd.DataFrame:
    patterns = dictionary_patterns(dictionary)
    metadata = ["dedupe_hash", "score", "review_year", "distillery", "review_length", "identity_status", "match_source"]
    columns: dict[str, pd.Series] = {column: tokenized[column] for column in metadata}
    for scope in TEXT_SCOPES:
        text = tokenized[scope].fillna("")
        wc = text.str.split().str.len()
        columns[f"wordcount_{scope}"] = wc
        for short, pattern in patterns.items():
            counts = text.str.count(pattern)
            columns[f"{short}_{scope}_count"] = counts
            columns[f"{short}_{scope}_per1k"] = pd.Series(
                np.where(wc > 0, counts / wc * 1000, np.nan), index=tokenized.index
            )
            columns[f"{short}_{scope}_binary"] = counts.gt(0).astype(int)
    vader = SentimentIntensityAnalyzer()
    scores = tokenized["review_text_original"].fillna("").apply(vader.polarity_scores)
    for key in ["compound", "pos", "neg", "neu"]:
        columns[f"vader_{key}"] = scores.apply(lambda values: values[key])
    features = pd.DataFrame(columns)
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        features.to_parquet(output_path, index=False)
    return features


def merge_analysis_frame(tokenized: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    overlap = [column for column in features.columns if column in tokenized.columns and column != "dedupe_hash"]
    return tokenized.merge(features.drop(columns=overlap), on="dedupe_hash", how="left")


def independent_groups(df: pd.DataFrame) -> dict[str, pd.Series]:
    title = df["whisky_name_raw"].fillna("")
    sherry = title.str.contains(SHERRY_CUE)
    return {
        "Islay assigned distillery": df["distillery"].isin(ISLAY_DISTILLERIES),
        "Sherry title cue": sherry,
        "Bourbon title cue": title.str.contains(BOURBON_CUE) & ~sherry,
        "High score (criterion)": df["score"].ge(90),
        "Low score (criterion)": df["score"].le(75),
    }


def token_sentences(tokenized: pd.DataFrame) -> list[list[str]]:
    return [re.findall(r"[a-z_]+", text.lower()) for text in tokenized["review_text"].fillna("")]


def ensure_dirs() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    PAPER.mkdir(parents=True, exist_ok=True)


def holm_adjust(pvalues: Iterable[float]) -> list[float]:
    values = list(pvalues)
    order = sorted(range(len(values)), key=values.__getitem__)
    adjusted = [0.0] * len(values)
    running = 0.0
    total = len(values)
    for rank, index in enumerate(order):
        running = max(running, (total - rank) * values[index])
        adjusted[index] = min(1.0, running)
    return adjusted
