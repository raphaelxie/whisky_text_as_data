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
