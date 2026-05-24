"""
Unit tests for whiskyfun_parse_utils.

Strings mirror real whiskyfun rows (user reports / plan): blurb-after-title, PREVIEW,
lead paragraph before bottle name, Angus header detection, two-bottle Angus cell split.
"""

from __future__ import annotations

import csv
import unittest
from pathlib import Path

from whiskyfun_parse_utils import (
    extract_clean_bottle_title,
    head_before_colour,
    is_angus_corner_header_row,
    rebuild_review_text,
    split_review_text_multi_sgp,
)


class TestExtractCleanBottleTitle(unittest.TestCase):
    def test_uitvlugt_2018(self) -> None:
        head = (
            "Uitvlugt 26 yo 1990/2017 (51%, Silver Seal, Demerara, cask #27, 219 bottles) "
            "We’ve known rather tense Uitvlugts, as well as easier, softer ones. Let’s see…"
        )
        t, low = extract_clean_bottle_title(head)
        self.assertFalse(low)
        self.assertEqual(
            t,
            "Uitvlugt 26 yo 1990/2017 (51%, Silver Seal, Demerara, cask #27, 219 bottles)",
        )

    def test_preview_highland_park(self) -> None:
        head = (
            "PREVIEW Highland Park 1991/2023 (53.4%, Signatory Vintage, 35th Anniversary, "
            "1st fill sherry butt, cask #15088) All right, this baby's not out yet"
        )
        t, low = extract_clean_bottle_title(head)
        self.assertFalse(low)
        self.assertEqual(
            t,
            "Highland Park 1991/2023 (53.4%, Signatory Vintage, 35th Anniversary, "
            "1st fill sherry butt, cask #15088)",
        )

    def test_linkwood_no_blurb(self) -> None:
        head = "Linkwood 21 yo 1995/2016 (51.5%, Douglas Laing, Old Particular, refill hogshead, cask # 11357, 283 bottles)"
        t, low = extract_clean_bottle_title(head)
        self.assertFalse(low)
        self.assertTrue(t.startswith("Linkwood 21 yo"))

    def test_blurb_before_name_cutty(self) -> None:
        head = (
            "Because what’s really cool with blends, is that they’re made by masters. "
            "Cutty Black (40%, OB, blend, +/-2016) This is Cutty’s version"
        )
        t, low = extract_clean_bottle_title(head)
        self.assertFalse(low)
        self.assertEqual(t, "Cutty Black (40%, OB, blend, +/-2016)")


class TestRebuildReviewText(unittest.TestCase):
    def test_rebuild_strips_preview_intro(self) -> None:
        text = (
            "PREVIEW Highland Park 1991/2023 (53.4%, OB) All right intro here. "
            "Colour: deep gold. Nose: smoke. Mouth: big. Finish: long. Comments: ok. "
            "SGP:462 - 91 points."
        )
        h = head_before_colour(text)
        title, _ = extract_clean_bottle_title(h)
        out = rebuild_review_text(text, title)
        self.assertIn("Colour: deep gold", out)
        self.assertTrue(out.startswith("Highland Park 1991/2023 (53.4%, OB)"))


class TestAngusCorner(unittest.TestCase):
    def test_header_detection(self) -> None:
        self.assertTrue(
            is_angus_corner_header_row(
                "Angus's Corner From our correspondent and skilled taster Angus MacRaild"
            )
        )
        self.assertFalse(is_angus_corner_header_row("Glen Grant 12 yo (40%, OB) Angus already tasted"))
        self.assertFalse(is_angus_corner_header_row("Balblair 23 yo 1993/2017 (53.2%, OB)"))


class TestSplitMultiSgp(unittest.TestCase):
    def test_balblair_two_bottles_from_csv(self) -> None:
        path = Path(__file__).resolve().parent / "whiskyfun_archive_2012_2025" / "reviews_2017_04.csv"
        if not path.is_file():
            self.skipTest("archive CSV not present")
        with path.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("whisky_name_raw", "").startswith("Balblair 23 yo 1993/2017"):
                    parts = split_review_text_multi_sgp(row["review_text"])
                    self.assertEqual(len(parts), 2)
                    self.assertIn("SGP: 634", parts[0])
                    self.assertIn("Balblair 21 yo 1964/1985 (57.80%, Intertrade)", parts[1])
                    self.assertIn("SGP: 755", parts[1])
                    return
        self.fail("Balblair fixture row not found")


if __name__ == "__main__":
    unittest.main()
