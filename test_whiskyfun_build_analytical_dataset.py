"""Tests for whiskyfun_build_analytical_dataset helpers."""

from __future__ import annotations

import unittest

from whiskyfun_build_analytical_dataset import (
    apply_alias_normalization,
    extract_sections,
    match_distillery_by_name,
    strip_hyphen_glenlivet_suffix,
    strip_score_leakage,
    strip_title_prefix,
)


class TestStripHyphenGlenlivet(unittest.TestCase):
    def test_glenfarclas(self) -> None:
        self.assertIn(
            "Glenfarclas",
            strip_hyphen_glenlivet_suffix("Glenfarclas-Glenlivet 25 yo"),
        )
        self.assertNotIn("-Glenlivet", strip_hyphen_glenlivet_suffix("Glenfarclas-Glenlivet"))

    def test_braes_unchanged(self) -> None:
        s = "Braes of Glenlivet 16 yo"
        self.assertEqual(strip_hyphen_glenlivet_suffix(s), s)


class TestAliases(unittest.TestCase):
    def test_glengarioch(self) -> None:
        self.assertIn("Glen Garioch", apply_alias_normalization("Glengarioch 1990"))

    def test_pulteney(self) -> None:
        self.assertIn("Old Pulteney", apply_alias_normalization("Pulteney 26 yo"))

    def test_an_cnoc_no_double(self) -> None:
        s = apply_alias_normalization("An Cnoc/Knockdhu 16 yo")
        self.assertEqual(s.count("Knockdhu"), 1)


class TestMatchDistillery(unittest.TestCase):
    def test_longest_wins(self) -> None:
        dists = ["Glen Grant", "Grant"]
        self.assertEqual(
            match_distillery_by_name("Glen Grant 12 yo (40%, OB)", dists),
            "Glen Grant",
        )


class TestStripLeakageAndPrefix(unittest.TestCase):
    def test_sgp_removed(self) -> None:
        t = "Nose: smoke. SGP:462 - 91 points."
        out = strip_score_leakage(t)
        self.assertNotIn("SGP", out)
        self.assertNotIn("points", out.lower())

    def test_narrative_numeric_points_removed(self) -> None:
        out = strip_score_leakage("Comments: easily 90 point material, perhaps 92 points.")
        self.assertNotRegex(out.lower(), r"\b(?:90|92)\s*points?\b")

    def test_numeric_score_phrasing_removed(self) -> None:
        out = strip_score_leakage("Comments: Angus gave a score of 94 out of 100.")
        self.assertNotIn("94", out)

    def test_loose_personal_score_constructions_removed(self) -> None:
        out = strip_score_leakage(
            "Comments: this hits a 90. I had it at around 90-91, then 88. "
            "It fetched north of 92 in my book and was worth 88%."
        )
        self.assertNotRegex(out, r"\b(?:90|91|92)\b")
        self.assertNotIn("88", out)

    def test_percentage_score_after_score_label_removed(self) -> None:
        out = strip_score_leakage("Comments: many tasters would score this old baby 88 or 89%.")
        self.assertNotRegex(out, r"\b(?:88|89)\b")

    def test_score_context_does_not_strip_abv_or_age(self) -> None:
        out = strip_score_leakage(
            "Nose: hitting 60% ABV is hard at 20 years of age. "
            "Serge scored an earlier bottle back in 2008."
        )
        self.assertIn("60% ABV", out)
        self.assertIn("20 years", out)
        self.assertIn("2008", out)

    def test_nonnumeric_score_discussion_retained(self) -> None:
        out = strip_score_leakage("Comments: the score seems fair and SGP is useful.")
        self.assertIn("score seems fair", out)
        self.assertIn("SGP is useful", out)

    def test_prefix(self) -> None:
        title = "Caol Ila 12yo (43%, OB)"
        body = f"{title} Colour: gold. Nose: peat."
        out = strip_title_prefix(body, title)
        self.assertTrue(out.startswith("Colour:"))


class TestExtractSections(unittest.TestCase):
    def test_standard(self) -> None:
        text = (
            "Colour: gold. Nose: smoke and salt. Mouth: big and dry. "
            "Finish: long. Comments: good. Extra tail."
        )
        n, m, f, c, ok = extract_sections(text)
        self.assertTrue(ok)
        self.assertIn("smoke", n.lower())
        self.assertIn("big", m.lower())
        self.assertIn("long", f.lower())
        self.assertIn("good", c.lower())

    def test_mouth_neat(self) -> None:
        text = "Nose: a. Mouth (neat): b. Finish: c. Comments: d."
        n, m, f, c, ok = extract_sections(text)
        self.assertTrue(ok)
        self.assertEqual(m.strip(), "b.")


if __name__ == "__main__":
    unittest.main()
