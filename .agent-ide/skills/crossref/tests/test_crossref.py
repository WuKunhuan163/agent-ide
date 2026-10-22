"""Offline checks: Crossref item parsing and licence decoding, no network."""
from __future__ import annotations

import unittest

from src.main import _authors, _license_status, parse_works


ITEM = {
    "title": ["Consumer response to health claims"],
    "issued": {"date-parts": [[2020, 5]]},
    "container-title": ["Food Quality and Preference"],
    "volume": "31",
    "issue": "3",
    "page": "1-10",
    "DOI": "10.1016/j.foodqual.2020.103999",
    "author": [{"given": "Ana", "family": "Silva"}, {"family": "NoGiven"}],
    "is-referenced-by-count": 77,
    "license": [{"URL": "https://creativecommons.org/licenses/by-nc/4.0/"}],
    "type": "journal-article",
}


class ParseTests(unittest.TestCase):
    def test_item_fields(self):
        rows = parse_works({"message": {"items": [ITEM]}})
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["title"], "Consumer response to health claims")
        self.assertEqual(row["year"], 2020)
        self.assertEqual(row["journal"], "Food Quality and Preference")
        self.assertEqual(row["volume"], "31")
        self.assertEqual(row["pages"], "1-10")
        self.assertEqual(row["doi"], "10.1016/j.foodqual.2020.103999")
        self.assertEqual(row["cited_by_count"], 77)
        self.assertEqual(row["license"], "CC-BY-NC")

    def test_missing_fields_do_not_raise(self):
        rows = parse_works({"message": {"items": [{"DOI": "10.1/x"}]}})
        self.assertEqual(rows[0]["doi"], "10.1/x")
        self.assertIsNone(rows[0]["year"])
        self.assertEqual(rows[0]["authors"], [])

    def test_empty_payload(self):
        self.assertEqual(parse_works(None), [])
        self.assertEqual(parse_works({"message": {}}), [])

    def test_license_detection(self):
        self.assertEqual(_license_status({"license": [
            {"URL": "https://creativecommons.org/licenses/by/4.0/"}][:1]})[0], "CC-BY")
        self.assertIsNone(_license_status({})[0])

    def test_authors_skip_missing_family(self):
        self.assertEqual(_authors(ITEM), ["Ana Silva", " NoGiven"])


if __name__ == "__main__":
    unittest.main()
