#!/usr/bin/env python3
"""
Whiskyfun Scottish Malts index scraper, archive enrichment, corpus matching, and reports.

Subcommands: scrape-index, enrich-archive, match, report, smoke, all

Does not modify the original monthly corpus CSVs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import random
import re
import sys
import time
from collections import defaultdict
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

from whiskyfun_archive_crawl import row_dedupe_hash
from whiskyfun_parse_utils import extract_clean_bottle_title, extract_score_from_text, head_before_colour
from whiskyfun_pilot_scraper import (
    USER_AGENT,
    extract_reviews_from_day_fragment,
    split_html_by_day,
)
from whiskyfun_scottish_malts_normalize import (
    normalize_source_url,
    normalize_source_url_loose,
    normalize_text_snippet_for_match,
    normalize_whisky_name_for_match,
    parse_ddmmyy_anchor,
    score_string_to_int,
)

BASE = "https://www.whiskyfun.com/"
log = logging.getLogger("whiskyfun_scottish_malts")

# On-disk cache so full index + enrich reruns do not re-hit the network for every archive page.
PAGE_CACHE_DIR = Path(".whiskyfun_page_cache")


def fetch_html_cached(url: str, pause: float = 0.65, timeout: float = 35.0) -> str | None:
    PAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    path = PAGE_CACHE_DIR / f"{key}.html"
    if path.is_file():
        return path.read_text(encoding="utf-8", errors="replace")
    raw = fetch_html(url, pause=pause, timeout=timeout)
    if raw:
        path.write_text(raw, encoding="utf-8", errors="replace")
    return raw


# --- page types (plan) ---
PT_NAMED_DISTILLERY = "named_scottish_malt_distillery"
PT_NAMED_SECTION = "named_scottish_malt_section"
PT_AUX_UNDISCLOSED = "auxiliary_undisclosed_vatted"
PT_AUX_GRAIN = "auxiliary_grain"
PT_AUX_BLEND = "auxiliary_blend"
PT_AUX_OTHER_WHISKY = "auxiliary_other_whisky"

ARCHIVE_LINK_RE = re.compile(
    r"(?i)https?://(?:www\.)?whiskyfun\.com/([^\"'#]+\.html)#(\d{6})",
)
REL_ARCHIVE_RE = re.compile(r"(?i)(archive[^\"'#]+\.html)#(\d{6})")


def fetch_html(url: str, pause: float = 0.55, timeout: float = 35.0) -> str | None:
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
        if not r.encoding or r.encoding.lower() == "iso-8859-1":
            r.encoding = r.apparent_encoding or "iso-8859-1"
        time.sleep(pause + random.uniform(0, 0.2))
        return r.text
    except requests.RequestException as e:
        log.warning("fetch failed %s: %s", url, e)
        return None


def find_scottish_malts_nav_table(soup: BeautifulSoup) -> Tag | None:
    for text in soup.find_all(string=re.compile(r"Scottish\s+Malts", re.I)):
        t = text.parent
        while t and t.name != "table":
            t = t.parent
        if t and t.name == "table":
            return t
    return None


def basename_lower(path: str) -> str:
    p = (path or "").rsplit("/", 1)[-1].lower()
    return p


def classify_auxiliary(bn: str) -> str | None:
    if bn == "vatted-or-undisclosed.html":
        return PT_AUX_UNDISCLOSED
    if bn == "grain-whisky.html":
        return PT_AUX_GRAIN
    if bn == "blended-whisky.html":
        return PT_AUX_BLEND
    if bn in (
        "japanese-whisky.html",
        "irish-whisky.html",
        "american-whisky.html",
        "world-whisky.html",
    ):
        return PT_AUX_OTHER_WHISKY
    return None


def parse_nav_links(html: str) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Split homepage Scottish Malts nav into named-malt vs auxiliary links."""
    soup = BeautifulSoup(html, "html.parser")
    table = find_scottish_malts_nav_table(soup)
    if not table:
        log.error("Scottish Malts nav table not found")
        return [], []

    raw = str(table)
    idx_other = raw.find("Other Whiskies")
    named: list[dict[str, str]] = []
    auxiliary: list[dict[str, str]] = []

    for a in table.find_all("a", href=True):
        label = " ".join(a.get_text(" ", strip=True).split())
        href = urljoin(BASE, a["href"].strip())
        bn = basename_lower(urlparse(href).path)

        pos = raw.find(str(a))
        if pos == -1:
            pos = raw.find(f'href="{a.get("href")}"')

        after_other = idx_other != -1 and pos != -1 and pos > idx_other
        aux_type = classify_auxiliary(bn)

        if aux_type or after_other:
            auxiliary.append({"label": label, "href": href, "aux_type": aux_type or PT_AUX_OTHER_WHISKY})
        else:
            named.append({"label": label, "href": href})

    def dedupe_links(lst: list[dict], key: str) -> list[dict]:
        seen: set[str] = set()
        out: list[dict] = []
        for d in lst:
            k = d[key]
            if k not in seen:
                seen.add(k)
                out.append(d)
        return out

    named = dedupe_links(named, "href")
    auxiliary = dedupe_links(auxiliary, "href")
    return named, auxiliary


def extract_whisky_line_from_container(container: Tag, anchor_a: Tag) -> str:
    """Strip trailing six-digit anchor link text from container prose."""
    frag = anchor_a.get_text(strip=True)
    line = container.get_text(" ", strip=True)
    line = re.sub(r"\s*-\s*" + re.escape(frag) + r"\s*$", "", line)
    line = re.sub(r"\s*" + re.escape(frag) + r"\s*$", "", line)
    line = " ".join(line.split())
    return line.strip()


def anchor_in_latest_tasted_sidebar(a: Tag) -> bool:
    """Sidebar 'Latest Tasted' widget duplicates the same reviews as the main list."""
    for par in a.parents:
        if par.name != "table":
            continue
        if str(par.get("width") or "") != "190":
            continue
        if par.find(string=re.compile(r"Latest\s+Tasted", re.I)):
            return True
    return False


def extract_archive_entry_rows_from_soup(
    soup: BeautifulSoup,
    *,
    index_distillery: str,
    index_page_url: str,
    page_type: str,
    scope_note: str = "",
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_pair: set[tuple[str, str]] = set()

    for a in soup.find_all("a", href=True):
        href = urljoin(BASE, a["href"].strip())
        m = ARCHIVE_LINK_RE.search(href)
        if not m:
            m2 = REL_ARCHIVE_RE.search(a["href"])
            if m2:
                href = urljoin(BASE, m2.group(1)) + "#" + m2.group(2)
                m = ARCHIVE_LINK_RE.search(href)
        if not m:
            continue
        frag = href.split("#")[-1] if "#" in href else ""
        if not re.fullmatch(r"\d{6}", frag):
            continue
        link_txt = a.get_text(strip=True)
        if link_txt != frag:
            continue

        if anchor_in_latest_tasted_sidebar(a):
            continue

        parent = a.find_parent(["li", "p", "td", "div"])
        if parent is None:
            continue

        whisky_line = extract_whisky_line_from_container(parent, a)
        if not whisky_line:
            whisky_line = parent.get_text(" ", strip=True)
            whisky_line = re.sub(r"\s*" + re.escape(frag) + r"\s*$", "", whisky_line).strip()

        raw_entry = parent.get_text(" ", strip=True)
        key = (normalize_source_url_loose(href.split("#")[0]), frag)
        if key in seen_pair:
            continue
        seen_pair.add(key)

        rd = parse_ddmmyy_anchor(frag)
        rows.append(
            {
                "index_distillery": index_distillery,
                "index_page_url": index_page_url,
                "page_type": page_type,
                "whisky_name_raw_index": whisky_line,
                "source_url_index": href,
                "review_date_index": rd.isoformat() if rd else "",
                "score_index": "",
                "review_text_snippet": "",
                "raw_entry_text": raw_entry,
                "scrape_notes": scope_note,
            }
        )
    return rows


def scrape_distillery_page(url: str, label: str) -> list[dict[str, Any]]:
    html = fetch_html_cached(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    index_distillery = label.strip()
    return extract_archive_entry_rows_from_soup(
        soup,
        index_distillery=index_distillery,
        index_page_url=url,
        page_type=PT_NAMED_DISTILLERY,
    )


def section_title_from_header_row(tr: Tag) -> str:
    for font in tr.find_all("font", color=re.compile(r"#990000", re.I)):
        t = font.get_text(" ", strip=True)
        if t:
            return t
    return ""


def scrape_various_new_distilleries(url: str = urljoin(BASE, "various-new-distilleries.html")) -> list[dict[str, Any]]:
    html = fetch_html_cached(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    out: list[dict[str, Any]] = []

    for tr in soup.find_all("tr", bgcolor=re.compile(r"#DFDFFF", re.I)):
        a_anchor = tr.find("a", attrs={"name": True})
        if not a_anchor:
            continue
        section_name = section_title_from_header_row(tr)
        if not section_name:
            nm = a_anchor.get("name", "")
            section_name = nm.replace("-", " ").replace("_", " ").title()

        frag = (a_anchor.get("name") or "").strip()
        index_page = f"{url}#{frag}" if frag else url

        tr_next = tr.find_next_sibling("tr")
        if not tr_next:
            continue
        ul = tr_next.find("ul")
        if not ul:
            continue

        mini_soup = BeautifulSoup(str(ul), "html.parser")
        chunk = extract_archive_entry_rows_from_soup(
            mini_soup,
            index_distillery=section_name,
            index_page_url=index_page,
            page_type=PT_NAMED_SECTION,
            scope_note="various-new-distilleries section",
        )
        out.extend(chunk)

    return out


def scrape_auxiliary_page(url: str, page_type: str, category_label: str) -> list[dict[str, Any]]:
    html = fetch_html_cached(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    rows = extract_archive_entry_rows_from_soup(
        soup,
        index_distillery=category_label,
        index_page_url=url,
        page_type=page_type,
        scope_note=f"auxiliary:{page_type}",
    )
    return rows


def build_page_jobs(named_nav: list[dict], smoke: bool = False, smoke_urls: list[str] | None = None) -> dict[str, Any]:
    """Resolve which distillery pages to fetch and various-new fragments."""
    jobs: dict[str, dict] = {}
    various_needed = False

    smoke_set = {urljoin(BASE, u.strip()) for u in (smoke_urls or [])}

    for item in named_nav:
        href = item["href"]
        label = item["label"]
        full = urljoin(BASE, href)
        parsed = urlparse(full)
        bn = basename_lower(parsed.path)

        if smoke and smoke_set:
            if full not in smoke_set and not any(full.startswith(s.rstrip("*")) for s in smoke_set):
                if "various-new" not in bn:
                    continue

        if bn == "various-new-distilleries.html" and "#" not in full:
            various_needed = True
            continue
        if "various-new-distilleries.html" in bn and "#" in full:
            various_needed = True
            continue
        if classify_auxiliary(bn):
            continue

        if bn == "various-new-distilleries.html":
            various_needed = True
            continue

        jobs[full] = {"label": label, "kind": "distillery"}

    return {"distillery_urls": jobs, "fetch_various_new": various_needed or not smoke}


def run_scrape_index(
    *,
    out_pages: Path,
    out_metadata_partial: Path | None,
    smoke: bool,
    smoke_allowlist: list[str],
    log_path: Path,
) -> list[dict[str, Any]]:
    home = fetch_html_cached(urljoin(BASE, "/"))
    if not home:
        log.error("homepage fetch failed")
        return []

    named_nav, aux_nav = parse_nav_links(home)

    # Page inventory CSV
    page_rows: list[dict[str, str]] = []
    for item in named_nav:
        href = urljoin(BASE, item["href"])
        bn = basename_lower(urlparse(href).path)
        if classify_auxiliary(bn):
            continue
        if bn == "various-new-distilleries.html" and "#" not in href:
            pt = "catalog_root"
        elif "various-new-distilleries.html" in bn and "#" in href:
            pt = PT_NAMED_SECTION
        else:
            pt = PT_NAMED_DISTILLERY
        page_rows.append({"index_distillery": item["label"], "index_page_url": href, "page_type": pt})

    for item in aux_nav:
        page_rows.append(
            {
                "index_distillery": item["label"],
                "index_page_url": item["href"],
                "page_type": item.get("aux_type") or PT_AUX_OTHER_WHISKY,
            }
        )

    out_pages.parent.mkdir(parents=True, exist_ok=True)
    with out_pages.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["index_distillery", "index_page_url", "page_type"])
        w.writeheader()
        for r in page_rows:
            w.writerow(r)

    all_rows: list[dict[str, Any]] = []

    allow = [urljoin(BASE, x) for x in smoke_allowlist] if smoke and smoke_allowlist else None

    if smoke and allow:
        for url in allow:
            if "various-new-distilleries" in url and "#" not in url:
                all_rows.extend(scrape_various_new_distilleries(url))
            elif "various-new-distilleries" in url:
                base_u, frag = urldefrag(url)
                all_rows.extend(scrape_various_new_distilleries(base_u))
            else:
                label = urlparse(url).path.rsplit("/", 1)[-1].replace(".html", "").replace("-", " ")
                all_rows.extend(scrape_distillery_page(url, label))
    else:
        for item in named_nav:
            href = urljoin(BASE, item["href"])
            bn = basename_lower(urlparse(href).path)
            if classify_auxiliary(bn):
                continue
            if bn == "various-new-distilleries.html" and "#" not in href:
                continue
            if "various-new-distilleries.html" in bn:
                continue
            all_rows.extend(scrape_distillery_page(href, item["label"]))

        all_rows.extend(scrape_various_new_distilleries())

        if not smoke:
            for item in aux_nav:
                href = urljoin(BASE, item["href"])
                at = item.get("aux_type") or PT_AUX_OTHER_WHISKY
                all_rows.extend(scrape_auxiliary_page(href, at, item["label"]))

    with log_path.open("a", encoding="utf-8") as lf:
        lf.write(json.dumps({"event": "scrape_index_done", "n_rows": len(all_rows)}) + "\n")

    if out_metadata_partial:
        write_metadata_csv(all_rows, out_metadata_partial)

    return all_rows


def write_metadata_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "page_type",
        "index_distillery",
        "index_page_url",
        "whisky_name_raw_index",
        "score_index",
        "review_date_index",
        "source_url_index",
        "review_text_snippet",
        "raw_entry_text",
        "scrape_notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def enrich_archive_for_rows(
    rows: list[dict[str, Any]],
    blocks_out: Path,
    *,
    max_archive_pages: int | None = None,
) -> None:
    """Fetch archive pages once; fill score_index and review_text_snippet."""
    by_base: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        su = r.get("source_url_index") or ""
        if "#" not in su:
            continue
        base, _frag = urldefrag(urljoin(BASE, su))
        by_base[base].append(r)

    block_rows: list[dict[str, str]] = []

    base_urls = list(by_base.keys())
    if max_archive_pages is not None:
        base_urls = base_urls[:max_archive_pages]

    for base_url in base_urls:
        group = by_base[base_url]
        raw = fetch_html_cached(base_url)
        if not raw:
            for r in group:
                r["scrape_notes"] = (r.get("scrape_notes") or "") + "; enrich_fetch_failed"
            continue

        segments = split_html_by_day(raw)
        date_to_reviews: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for seg_date, frag in segments:
            for c in extract_reviews_from_day_fragment(frag):
                date_to_reviews[seg_date.isoformat()].append(c)

        for r in group:
            frag = r.get("source_url_index", "").split("#")[-1]
            rd = r.get("review_date_index") or ""
            idx_name = r.get("whisky_name_raw_index") or ""
            idx_norm = normalize_whisky_name_for_match(idx_name)

            candidates = date_to_reviews.get(rd, [])
            best = None
            best_ratio = 0.0
            for c in candidates:
                cn = normalize_whisky_name_for_match(c.get("whisky_name_raw") or "")
                if idx_norm and cn == idx_norm:
                    best = c
                    best_ratio = 1.0
                    break
                ratio = SequenceMatcher(None, idx_norm, cn).ratio() if idx_norm and cn else 0.0
                if ratio > best_ratio:
                    best_ratio = ratio
                    best = c

            min_ratio = 0.52
            if best is not None and best_ratio >= min_ratio:
                text = best.get("review_text") or ""
                score = best.get("score")
                r["score_index"] = str(score) if score is not None else ""
                r["review_text_snippet"] = text[:400].replace("\n", " ") if text else ""
                r["scrape_notes"] = (r.get("scrape_notes") or "") + f"; enrich_ratio={best_ratio:.3f}"
                block_rows.append(
                    {
                        "archive_url": base_url,
                        "review_date": rd,
                        "anchor_frag": frag,
                        "whisky_name_raw": best.get("whisky_name_raw", ""),
                        "score": str(best.get("score", "")),
                        "review_text_snippet": r["review_text_snippet"],
                    }
                )
            elif best is not None:
                r["scrape_notes"] = (r.get("scrape_notes") or "") + f"; enrich_low_ratio={best_ratio:.3f}_skipped"
            else:
                r["scrape_notes"] = (r.get("scrape_notes") or "") + "; enrich_no_review_block"

    blocks_out.parent.mkdir(parents=True, exist_ok=True)
    with blocks_out.open("w", newline="", encoding="utf-8") as f:
        bf = [
            "archive_url",
            "review_date",
            "anchor_frag",
            "whisky_name_raw",
            "score",
            "review_text_snippet",
        ]
        w = csv.DictWriter(f, fieldnames=bf)
        w.writeheader()
        for b in block_rows:
            w.writerow(b)


# ------------- matching (continued in second part of file to avoid huge single write) -------------

MATCH_STRICT = frozenset({"exact_url", "exact_normalized_name_score", "exact_normalized_name_score_snippet"})


def load_corpus(corpus_dir: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for p in sorted(corpus_dir.glob("reviews_*.csv")):
        with p.open(encoding="utf-8", newline="") as f:
            rdr = csv.DictReader(f)
            for row in rdr:
                rows.append(dict(row))
    return rows


def corpus_indexes(corpus: list[dict[str, str]]) -> tuple[dict[str, list[int]], dict[tuple[str, str], list[int]], dict[str, int]]:
    by_loose_url: dict[str, list[int]] = defaultdict(list)
    by_name_score: dict[tuple[str, str], list[int]] = defaultdict(list)
    by_hash: dict[str, int] = {}

    for i, row in enumerate(corpus):
        su = row.get("source_url") or ""
        by_loose_url[normalize_source_url_loose(su)].append(i)
        ns = normalize_whisky_name_for_match(row.get("whisky_name_raw") or "")
        sc = row.get("score") or ""
        by_name_score[(ns, str(sc).strip())].append(i)
        dh = row.get("dedupe_hash") or ""
        if dh:
            by_hash[dh] = i

    return dict(by_loose_url), dict(by_name_score), by_hash


def match_one_index_row(
    ir: dict[str, Any],
    corpus: list[dict[str, str]],
    by_loose_url: dict[str, list[int]],
    by_name_score: dict[tuple[str, str], list[int]],
    by_hash: dict[str, int],
) -> dict[str, Any]:
    """Return match info dict."""
    notes: list[str] = []
    idx_src = ir.get("source_url_index") or ""
    idx_base = normalize_source_url_loose(idx_src.split("#")[0]) if idx_src else ""
    idx_date = ir.get("review_date_index") or ""
    idx_name = normalize_whisky_name_for_match(ir.get("whisky_name_raw_index") or "")
    idx_score = score_string_to_int(ir.get("score_index"))
    idx_snip = normalize_text_snippet_for_match(ir.get("review_text_snippet") or ir.get("raw_entry_text") or "")

    candidates: list[int] = []

    # Tier 1: URL base + date (corpus source_url has no fragment)
    if idx_base:
        pool = by_loose_url.get(idx_base, [])
        for j in pool:
            cr = corpus[j]
            if cr.get("review_date") == idx_date:
                candidates.append(j)
        if len(candidates) == 1:
            return _finalize_match(ir, corpus[candidates[0]], "exact_url", 1.0, True, False, notes)
        if len(candidates) > 1:
            narrowed = [
                j
                for j in candidates
                if normalize_whisky_name_for_match(corpus[j].get("whisky_name_raw") or "") == idx_name
            ]
            if len(narrowed) == 1:
                return _finalize_match(ir, corpus[narrowed[0]], "exact_url", 1.0, True, False, notes)
            notes.append(f"tier1_multi_candidates={len(candidates)}")

    # Tier 2: normalized name + score
    key = (idx_name, str(idx_score if idx_score is not None else ""))
    pool2 = by_name_score.get(key, [])
    if len(pool2) == 1:
        return _finalize_match(ir, corpus[pool2[0]], "exact_normalized_name_score", 1.0, True, True, notes)

    # Tier 3: name + score + snippet prefix
    if pool2:
        narrowed3: list[int] = []
        pref80 = idx_snip[:80] if idx_snip else ""
        pref100 = idx_snip[: min(100, len(idx_snip))] if idx_snip else ""
        for j in pool2:
            ct = corpus[j].get("review_text") or ""
            cn = normalize_text_snippet_for_match(ct)
            ok_snip = False
            if pref100 and cn.startswith(pref100[:80]):
                ok_snip = True
            elif pref80 and pref80 in cn:
                ok_snip = True
            if ok_snip:
                narrowed3.append(j)
        if len(narrowed3) == 1:
            return _finalize_match(
                ir,
                corpus[narrowed3[0]],
                "exact_normalized_name_score_snippet",
                1.0,
                True,
                False,
                notes,
            )

    # Tier 4 fuzzy
    best_j: int | None = None
    best_ratio = 0.0
    pool_f = pool2 if pool2 else list(range(len(corpus)))
    if len(pool_f) > 5000:
        pool_f = pool2 or []

    for j in pool_f:
        cr = corpus[j]
        if idx_score is not None:
            cs = score_string_to_int(cr.get("score"))
            if cs != idx_score:
                continue
        cn = normalize_whisky_name_for_match(cr.get("whisky_name_raw") or "")
        ratio = SequenceMatcher(None, idx_name, cn).ratio() if idx_name else 0.0
        if ratio > best_ratio:
            best_ratio = ratio
            best_j = j

    ambiguous_fuzzy = False
    if best_j is not None and best_ratio >= 0.88:
        second = 0.0
        for j in pool_f:
            if j == best_j:
                continue
            cr = corpus[j]
            if idx_score is not None:
                cs = score_string_to_int(cr.get("score"))
                if cs != idx_score:
                    continue
            cn = normalize_whisky_name_for_match(cr.get("whisky_name_raw") or "")
            r2 = SequenceMatcher(None, idx_name, cn).ratio() if idx_name else 0.0
            if r2 >= 0.88:
                ambiguous_fuzzy = True
            second = max(second, r2)
        date_ok = _date_consistent(ir, corpus[best_j])
        if ambiguous_fuzzy:
            notes.append("fuzzy_ambiguous_multiple_high")
            return _finalize_match(ir, corpus[best_j], "fuzzy_low", best_ratio, False, False, notes)
        if not date_ok:
            notes.append("fuzzy_rejected_date_mismatch")
            return _finalize_match(ir, corpus[best_j], "fuzzy_low", best_ratio, False, False, notes)
        return _finalize_match(ir, corpus[best_j], "fuzzy_high", best_ratio, False, True, notes)

    if best_j is not None and best_ratio >= 0.78:
        return _finalize_match(ir, corpus[best_j], "fuzzy_low", best_ratio, False, False, notes)

    return {
        "match_method": "unmatched",
        "match_confidence": "0",
        "dedupe_hash": "",
        "corpus_row": None,
        "notes": "; ".join(notes),
    }


def _date_consistent(ir: dict[str, Any], cr: dict[str, str]) -> bool:
    a = ir.get("review_date_index") or ""
    b = cr.get("review_date") or ""
    return bool(a and b and a == b)


def _finalize_match(
    ir: dict[str, Any],
    cr: dict[str, str],
    method: str,
    conf: float,
    strict_sample: bool,
    expanded_eligible: bool,
    notes: list[str],
) -> dict[str, Any]:
    dh = cr.get("dedupe_hash") or row_dedupe_hash({"review_text": cr.get("review_text")})
    dc = _date_consistent(ir, cr)
    dd = ""
    if ir.get("review_date_index") and cr.get("review_date"):
        try:
            d1 = date.fromisoformat(ir["review_date_index"])
            d2 = date.fromisoformat(cr["review_date"])
            dd = str(abs((d1 - d2).days))
        except ValueError:
            dd = ""
    if not dc:
        notes.append("date_mismatch")

    joined = "; ".join(notes)
    ambiguous_fuzzy = "fuzzy_ambiguous_multiple_high" in joined
    expanded_ok = method == "fuzzy_high" and dc and not ambiguous_fuzzy

    return {
        "match_method": method,
        "match_confidence": f"{conf:.4f}",
        "dedupe_hash": dh,
        "corpus_row": cr,
        "strict_sample": strict_sample,
        "expanded_eligible": expanded_ok,
        "date_consistent": dc,
        "date_difference_days": dd,
        "notes": joined,
    }


MAIN_SAMPLE_PT = frozenset({PT_NAMED_DISTILLERY, PT_NAMED_SECTION})


def collect_match_packs(
    metadata_rows: list[dict[str, Any]],
    corpus: list[dict[str, str]],
    by_loose_url: dict[str, list[int]],
    by_name_score: dict[tuple[str, str], list[int]],
    by_hash: dict[str, int],
) -> list[dict[str, Any]]:
    return [
        {"ir": ir, "mi": match_one_index_row(ir, corpus, by_loose_url, by_name_score, by_hash)}
        for ir in metadata_rows
    ]


def merge_corpus_with_matches(
    corpus: list[dict[str, str]],
    packs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """One output row per corpus row; index columns reflect winning named match when present."""
    by_dh: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in packs:
        dh = p["mi"].get("dedupe_hash") or ""
        if dh and p["mi"].get("match_method") != "unmatched":
            by_dh[dh].append(p)

    out: list[dict[str, Any]] = []
    for row in corpus:
        dh = row.get("dedupe_hash") or ""
        plist = by_dh.get(dh, [])
        named_ok = [p for p in plist if p["ir"].get("page_type") in MAIN_SAMPLE_PT]
        aux_only = [p for p in plist if p["ir"].get("page_type") not in MAIN_SAMPLE_PT]

        def best_of(sub: list[dict[str, Any]]) -> dict[str, Any] | None:
            if not sub:
                return None
            return max(sub, key=lambda p: float(p["mi"].get("match_confidence") or 0))

        win = best_of(named_ok) or best_of(aux_only)
        also_ud = any(p["ir"].get("page_type") == PT_AUX_UNDISCLOSED for p in plist)
        multi_named = len(named_ok) > 1

        whisky_name = row.get("whisky_name_raw") or ""
        norm_w = normalize_whisky_name_for_match(whisky_name)

        empty_base = {
            "dedupe_hash": dh,
            "whisky_name_raw": whisky_name,
            "text": row.get("review_text", ""),
            "score": row.get("score", ""),
            "review_date": row.get("review_date", ""),
            "source_url": row.get("source_url", ""),
            "index_distillery": "",
            "index_page_url": "",
            "whisky_name_raw_index": "",
            "score_index": "",
            "review_date_index": "",
            "source_url_index": "",
            "match_method": "",
            "match_confidence": "",
            "is_scottish_malt_indexed": "FALSE",
            "is_scottish_malt_indexed_strict": "FALSE",
            "is_scottish_malt_indexed_expanded": "FALSE",
            "name_mentions_index_distillery": "FALSE",
            "identity_status": "unmatched",
            "also_in_undisclosed_index": "FALSE",
            "matching_notes": "",
            "date_consistent": "",
            "date_difference_days": "",
            "page_type": "",
        }

        if not win:
            out.append(empty_base)
            continue

        ir, mi = win["ir"], win["mi"]
        idx_dist = ir.get("index_distillery") or ""
        norm_d = normalize_whisky_name_for_match(idx_dist)
        mentions = bool(norm_d and norm_d in norm_w)

        is_named_indexed = bool(named_ok)
        match_method = mi.get("match_method", "")
        dc = bool(mi.get("date_consistent"))

        strict = is_named_indexed and match_method in MATCH_STRICT and dc
        expanded = strict or (
            is_named_indexed
            and match_method == "fuzzy_high"
            and bool(mi.get("expanded_eligible"))
            and dc
        )

        if is_named_indexed:
            identity = "explicit_distillery" if mentions else "undisclosed_but_indexed_under_distillery"
        elif ir.get("page_type") == PT_AUX_UNDISCLOSED:
            identity = "undisclosed_uncertain"
        elif ir.get("page_type") == PT_AUX_GRAIN:
            identity = "non_scotch"
        elif ir.get("page_type") == PT_AUX_BLEND:
            identity = "blended_or_vatted"
        else:
            identity = "unmatched"

        notes = mi.get("notes", "") or ""
        if multi_named:
            notes += "; multi_named_page_membership"

        also_flag = "FALSE"
        if also_ud and is_named_indexed:
            also_flag = "TRUE"

        out.append(
            {
                "dedupe_hash": dh,
                "whisky_name_raw": whisky_name,
                "text": row.get("review_text", ""),
                "score": row.get("score", ""),
                "review_date": row.get("review_date", ""),
                "source_url": row.get("source_url", ""),
                "index_distillery": idx_dist,
                "index_page_url": ir.get("index_page_url", ""),
                "whisky_name_raw_index": ir.get("whisky_name_raw_index", ""),
                "score_index": ir.get("score_index", ""),
                "review_date_index": ir.get("review_date_index", ""),
                "source_url_index": ir.get("source_url_index", ""),
                "match_method": match_method,
                "match_confidence": mi.get("match_confidence", ""),
                "is_scottish_malt_indexed": "TRUE" if is_named_indexed else "FALSE",
                "is_scottish_malt_indexed_strict": "TRUE" if strict else "FALSE",
                "is_scottish_malt_indexed_expanded": "TRUE" if expanded else "FALSE",
                "name_mentions_index_distillery": "TRUE" if mentions else "FALSE",
                "identity_status": identity,
                "also_in_undisclosed_index": also_flag,
                "matching_notes": notes,
                "date_consistent": "TRUE" if dc else "FALSE",
                "date_difference_days": mi.get("date_difference_days", ""),
                "page_type": ir.get("page_type", ""),
            }
        )

    return out


def build_membership_rows(packs: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for p in packs:
        mi = p["mi"]
        ir = p["ir"]
        dh = mi.get("dedupe_hash") or ""
        if not dh or mi.get("match_method") == "unmatched":
            continue
        rows.append(
            {
                "dedupe_hash": dh,
                "whisky_name_raw_index": ir.get("whisky_name_raw_index", ""),
                "score_index": ir.get("score_index", ""),
                "index_page_url": ir.get("index_page_url", ""),
                "index_distillery_or_category": ir.get("index_distillery", ""),
                "page_type": ir.get("page_type", ""),
                "source_url_index": ir.get("source_url_index", ""),
                "notes": ir.get("scrape_notes", ""),
            }
        )
    return rows


def write_report(
    path: Path,
    *,
    n_pages: int,
    n_index_entries: int,
    n_matched: int,
    method_counts: dict[str, int],
    n_unmatched_index: int,
    n_corpus_scottish_malt: int,
    n_no_mention: int,
    examples_no_mention: list[str],
    dup_examples: list[str],
    scrape_errors: list[str],
) -> None:
    lines = [
        "Whiskyfun Scottish Malts Index Matching Report",
        "=" * 60,
        f"1. Distillery/index pages scraped (inventory): {n_pages}",
        f"2. Index review entries scraped: {n_index_entries}",
        f"3. Index entries matched to corpus: {n_matched}",
        "4. Match counts by match_method:",
    ]
    for k, v in sorted(method_counts.items()):
        lines.append(f"   - {k}: {v}")
    lines.extend(
        [
            f"5. Unmatched index entries: {n_unmatched_index}",
            f"6. Corpus rows with Scottish Malt index match: {n_corpus_scottish_malt}",
            f"7. Matched rows where name_mentions_index_distillery == FALSE: {n_no_mention}",
            "8. Top examples where index_distillery not in whisky_name_raw:",
        ]
    )
    for ex in examples_no_mention[:30]:
        lines.append(f"   - {ex}")
    lines.append("9. Duplicate / multi-page membership examples:")
    for ex in dup_examples[:20]:
        lines.append(f"   - {ex}")
    lines.append("10. Scraping errors / unusual pages:")
    for ex in scrape_errors[:30]:
        lines.append(f"   - {ex}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def manual_audit_rows(packs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-index-entry audit rows (not corpus-merged)."""
    out: list[dict[str, Any]] = []
    for pack in packs:
        ir = pack["ir"]
        mi = pack["mi"]
        method = mi.get("match_method", "")
        conf = float(mi.get("match_confidence") or 0)
        cr = mi.get("corpus_row")
        mentions = False
        if cr:
            mentions = normalize_whisky_name_for_match(ir.get("index_distillery") or "") in normalize_whisky_name_for_match(
                cr.get("whisky_name_raw") or ""
            )
        reasons: list[str] = []
        if method == "fuzzy_low":
            reasons.append("fuzzy_low")
        if method == "unmatched":
            reasons.append("unmatched_index_entry")
        if method and method not in MATCH_STRICT and method != "unmatched" and conf < 0.95:
            reasons.append("low_confidence")
        notes = mi.get("notes", "") or ""
        if "tier1_multi_candidates" in notes or "fuzzy_ambiguous" in notes:
            reasons.append("multiple_candidates")
        if cr and not mi.get("date_consistent"):
            reasons.append("date_mismatch")
        if cr and not mentions and method != "unmatched":
            reasons.append("name_does_not_mention_index_distillery")
        if reasons:
            out.append(
                {
                    "index_distillery": ir.get("index_distillery", ""),
                    "whisky_name_raw_index": ir.get("whisky_name_raw_index", ""),
                    "source_url_index": ir.get("source_url_index", ""),
                    "dedupe_hash": mi.get("dedupe_hash", ""),
                    "match_method": method,
                    "match_confidence": conf,
                    "page_type": ir.get("page_type", ""),
                    "audit_reasons": "; ".join(reasons),
                }
            )
    return out


def cmd_smoke(args: argparse.Namespace) -> None:
    root = Path(args.project_root)
    out_dir = root / "whiskyfun_index_outputs_smoke"
    out_dir.mkdir(parents=True, exist_ok=True)
    allow = [
        "https://www.whiskyfun.com/Ardbeg.html",
        "https://www.whiskyfun.com/Laphroaig.html",
        "https://www.whiskyfun.com/various-new-distilleries.html",
    ]
    rows = run_scrape_index(
        out_pages=out_dir / "whiskyfun_scottish_malts_index_pages.csv",
        out_metadata_partial=out_dir / "whiskyfun_scottish_malts_index_metadata_partial.csv",
        smoke=True,
        smoke_allowlist=allow,
        log_path=out_dir / "whiskyfun_index_scrape_log.jsonl",
    )
    enrich_archive_for_rows(
        rows,
        out_dir / "whiskyfun_index_archive_review_blocks.csv",
        max_archive_pages=25,
    )
    write_metadata_csv(rows, out_dir / "whiskyfun_scottish_malts_index_metadata.csv")
    print(f"Smoke: wrote {len(rows)} index rows to {out_dir}")


def cmd_all(args: argparse.Namespace) -> None:
    root = Path(args.project_root)
    out_dir = root / args.out_dir if args.out_dir.is_absolute() else root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = run_scrape_index(
        out_pages=out_dir / "whiskyfun_scottish_malts_index_pages.csv",
        out_metadata_partial=None,
        smoke=False,
        smoke_allowlist=[],
        log_path=out_dir / "whiskyfun_index_scrape_log.jsonl",
    )
    enrich_archive_for_rows(rows, out_dir / "whiskyfun_index_archive_review_blocks.csv")
    write_metadata_csv(rows, out_dir / "whiskyfun_scottish_malts_index_metadata.csv")

    corpus_dir = root / args.corpus_dir
    corpus = load_corpus(corpus_dir)
    by_loose_url, by_name_score, by_hash = corpus_indexes(corpus)
    packs = collect_match_packs(rows, corpus, by_loose_url, by_name_score, by_hash)
    final_rows = merge_corpus_with_matches(corpus, packs)
    membership = build_membership_rows(packs)

    fieldnames_matched = [
        "dedupe_hash",
        "whisky_name_raw",
        "text",
        "score",
        "review_date",
        "source_url",
        "index_distillery",
        "index_page_url",
        "whisky_name_raw_index",
        "score_index",
        "review_date_index",
        "source_url_index",
        "match_method",
        "match_confidence",
        "is_scottish_malt_indexed",
        "is_scottish_malt_indexed_strict",
        "is_scottish_malt_indexed_expanded",
        "name_mentions_index_distillery",
        "identity_status",
        "also_in_undisclosed_index",
        "matching_notes",
        "date_consistent",
        "date_difference_days",
        "page_type",
    ]

    with (out_dir / "whiskyfun_scottish_malts_matched_reviews.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames_matched, extrasaction="ignore")
        w.writeheader()
        for r in final_rows:
            w.writerow({k: r.get(k, "") for k in fieldnames_matched})

    mf = [
        "dedupe_hash",
        "whisky_name_raw_index",
        "score_index",
        "index_page_url",
        "index_distillery_or_category",
        "page_type",
        "source_url_index",
        "notes",
    ]
    with (out_dir / "whiskyfun_index_multi_page_membership.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=mf)
        w.writeheader()
        for row in membership:
            w.writerow({k: row.get(k, "") for k in mf})

    audit = manual_audit_rows(packs)
    audit_path = out_dir / "whiskyfun_scottish_malts_manual_audit_needed.csv"
    if audit:
        with audit_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(audit[0].keys()))
            w.writeheader()
            for r in audit:
                w.writerow(r)
    else:
        audit_path.write_text("", encoding="utf-8")

    method_counts: dict[str, int] = defaultdict(int)
    for p in packs:
        method_counts[p["mi"].get("match_method", "")] += 1

    n_index_matched = sum(1 for p in packs if p["mi"].get("match_method") != "unmatched")
    n_unmatched_index = sum(1 for p in packs if p["mi"].get("match_method") == "unmatched")

    examples_nm = [
        f"{r.get('index_distillery')} :: {r.get('whisky_name_raw')}"
        for r in final_rows
        if r.get("name_mentions_index_distillery") == "FALSE" and r.get("is_scottish_malt_indexed") == "TRUE"
    ]

    by_dh_named: dict[str, int] = defaultdict(int)
    for p in packs:
        dh = p["mi"].get("dedupe_hash") or ""
        if dh and p["ir"].get("page_type") in MAIN_SAMPLE_PT and p["mi"].get("match_method") != "unmatched":
            by_dh_named[dh] += 1
    dup_examples = [f"{dh} ({n} named hits)" for dh, n in by_dh_named.items() if n > 1][:25]

    n_pages = 0
    pages_csv = out_dir / "whiskyfun_scottish_malts_index_pages.csv"
    if pages_csv.is_file():
        n_pages = sum(1 for _ in pages_csv.open(encoding="utf-8")) - 1

    write_report(
        out_dir / "whiskyfun_scottish_malts_matching_report.txt",
        n_pages=n_pages,
        n_index_entries=len(rows),
        n_matched=n_index_matched,
        method_counts=dict(method_counts),
        n_unmatched_index=n_unmatched_index,
        n_corpus_scottish_malt=len([r for r in final_rows if r.get("is_scottish_malt_indexed") == "TRUE"]),
        n_no_mention=len(examples_nm),
        examples_no_mention=examples_nm,
        dup_examples=dup_examples,
        scrape_errors=[],
    )
    print(f"Done. Outputs in {out_dir}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Whiskyfun Scottish Malts index pipeline")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--project-root", type=Path, default=Path("."))
        sp.add_argument("--corpus-dir", default="whiskyfun_archive_2012_2025_clean")
        sp.add_argument(
            "--out-dir",
            type=Path,
            default=Path("."),
            help="Directory for output CSVs/report (default: project root)",
        )

    sp_smoke = sub.add_parser("smoke")
    add_common(sp_smoke)
    sp_all = sub.add_parser("all")
    add_common(sp_all)

    args = p.parse_args()
    if args.cmd == "smoke":
        cmd_smoke(args)
    elif args.cmd == "all":
        cmd_all(args)
    else:
        p.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
