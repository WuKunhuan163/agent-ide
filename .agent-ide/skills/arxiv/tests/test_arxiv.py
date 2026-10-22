"""Offline checks: Atom parsing, id/PDF derivation, query normalisation."""
from __future__ import annotations

import unittest

from src.arxiv_api import _parse_atom_entries, normalize_query_terms

ATOM = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.01234v2</id>
    <published>2024-01-02T10:00:00Z</published>
    <title>Health claims and consumer inference</title>
    <summary>We study how consumers read health claims.</summary>
    <author><name>Ada Lovelace</name></author>
    <author><name>Alan Turing</name></author>
  </entry>
</feed>
"""


class AtomTests(unittest.TestCase):
    def test_entry_fields(self):
        papers = _parse_atom_entries(ATOM)
        self.assertEqual(len(papers), 1)
        paper = papers[0]
        self.assertEqual(paper["id"], "2401.01234")
        self.assertEqual(paper["title"], "Health claims and consumer inference")
        self.assertEqual(paper["authors"], ["Ada Lovelace", "Alan Turing"])
        self.assertEqual(paper["link"], "http://arxiv.org/pdf/2401.01234v2.pdf")

    def test_empty_feed(self):
        feed = b'<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'
        self.assertEqual(_parse_atom_entries(feed), [])


class QueryTests(unittest.TestCase):
    def test_boolean_words_dropped(self):
        self.assertEqual(normalize_query_terms("health AND claim"), ["health", "claim"])
        self.assertEqual(normalize_query_terms("  "), [])


class DownloadTests(unittest.TestCase):
    def test_pdf_magic(self):
        from src.download import is_pdf

        self.assertTrue(is_pdf(b"%PDF-1.7\n"))
        self.assertFalse(is_pdf(b"<!DOCTYPE html>"))
        self.assertFalse(is_pdf(b""))

    def test_filename_is_stable_and_unique(self):
        from src.download import filename_for

        a = filename_for("https://arxiv.org/pdf/2308.04079", "3D Gaussian Splatting")
        b = filename_for("https://arxiv.org/pdf/2308.04079", "3D Gaussian Splatting")
        c = filename_for("https://ojs.aaai.org/x/32193", "3D Gaussian Splatting")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertTrue(a.endswith(".pdf"))
        self.assertNotIn(" ", a)

    def test_records_from_openalex_and_arxiv(self):
        import json
        import os
        import tempfile

        from src.download import records_from_json

        openalex = {"results": [
            {"title": "A", "pdf_url": "https://arxiv.org/pdf/1"},
            {"title": "B", "pdf_url": None},
        ]}
        arxiv = [{"title": "C", "pdf_link": "https://arxiv.org/pdf/3"},
                 {"title": "D"}]
        with tempfile.TemporaryDirectory() as d:
            p1 = os.path.join(d, "oa.json")
            p2 = os.path.join(d, "ax.json")
            with open(p1, "w", encoding="utf-8") as f:
                json.dump(openalex, f)
            with open(p2, "w", encoding="utf-8") as f:
                json.dump(arxiv, f)
            self.assertEqual([r["url"] for r in records_from_json(p1)], ["https://arxiv.org/pdf/1"])
            self.assertEqual([r["url"] for r in records_from_json(p2)], ["https://arxiv.org/pdf/3"])


if __name__ == "__main__":
    unittest.main()
