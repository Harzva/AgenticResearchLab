import csv
import importlib.util
import json
import re
import tempfile
import unittest
from collections import Counter
from pathlib import Path


BUILD_SCRIPT = Path(__file__).resolve().parents[1] / "knowledge-base" / "build.py"
SPEC = importlib.util.spec_from_file_location("knowledge_base_build", BUILD_SCRIPT)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class KnowledgeBaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = builder.load_catalog()

    def test_sources_keep_public_venue_and_paper_coverage(self):
        counts = Counter(paper["venue"] for paper in self.catalog["papers"])
        self.assertEqual(counts, {
            "aaai": 298, "cvpr": 153, "eccv": 6, "iclr": 316,
            "icml": 460, "ijcai": 162, "tpami": 3,
        })
        self.assertEqual({venue["id"]: venue["count"] for venue in self.catalog["venues"]}, counts)
        self.assertEqual({venue["id"]: venue["kind"] for venue in self.catalog["venues"]}["tpami"], "journal")
        self.assertEqual(sum(source["count"] for source in self.catalog["sources"]), len(self.catalog["papers"]))
        self.assertTrue(all("path" not in source for source in self.catalog["sources"]))

    def test_journal_year_is_the_volume_year_and_pdf_is_explicit(self):
        papers = {paper["id"]: paper for paper in self.catalog["papers"] if paper["venue"] == "tpami"}
        self.assertEqual(papers["tpami-2025-etpnav"]["year"], 2025)
        self.assertEqual(papers["tpami-2025-jarvis-1"]["year"], 2025)
        self.assertEqual(papers["tpami-2023-k-eqa"]["pdf_url"], "https://arxiv.org/pdf/2109.07872")
        self.assertIsNone(papers["tpami-2023-k-eqa"]["code_url"])
        self.assertTrue(all(paper["summary_zh"] is None for paper in papers.values()))
        self.assertIn("number = {7}", papers["tpami-2025-etpnav"]["bibtex"])

    def test_route_is_based_on_literal_evidence(self):
        self.assertEqual(builder.extract_routes("Storage planningness", None), [])
        route, = builder.extract_routes("Temporal reasoner", "An agent uses multi-agent coordination.")
        self.assertEqual(route["id"], "multi-agent")
        self.assertEqual(route["term"], "multi-agent")
        self.assertIn(route["term"], route["evidence"])
        self.assertTrue(route["evidence"].startswith("摘要："))
        for paper in self.catalog["papers"]:
            for route in paper["routes"]:
                self.assertIn(route["term"], route["evidence"])

    def test_public_urls_reject_private_hosts_and_credentials(self):
        for url in ("https://127.0.0.1/paper", "https://nas.local/paper", "https://x@example.org/paper", "file:///data/paper"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                builder.public_url(url)

    def test_generated_json_markdown_and_agent_index_point_to_the_same_paper(self):
        with tempfile.TemporaryDirectory() as scratch:
            output = Path(scratch) / "papers-site"
            output.mkdir()
            result = builder.build(output)
            self.assertEqual(result, self.catalog)
            self.assertEqual(json.loads((output / "catalog.json").read_text(encoding="utf-8")), result)
            records = result["papers"]
            self.assertEqual(len(list((output / "papers").glob("*.json"))), len(records))
            self.assertEqual(len(list((output / "papers").glob("*.md"))), len(records))
            paper = next(paper for paper in records if paper["id"] == "cvpr-2026-001")
            paper_json = output / "papers" / f"{paper['id']}.json"
            paper_markdown = output / "papers" / f"{paper['id']}.md"
            self.assertEqual(json.loads(paper_json.read_text(encoding="utf-8")), paper)
            self.assertIn(paper["pdf_url"], paper_markdown.read_text(encoding="utf-8"))
            llms = (output / "llms.txt").read_text(encoding="utf-8")
            links = re.findall(r"\]\(([^()]+)\)", llms)
            self.assertEqual(len(links), len(records) + 2)
            self.assertTrue(all(not link.startswith(("/", "http")) and (output / link).is_file() for link in links))
            with (output / "catalog.csv").open(encoding="utf-8", newline="") as file:
                self.assertEqual([r["id"] for r in csv.DictReader(file)], [p["id"] for p in records])
            with self.assertRaisesRegex(ValueError, "new or empty"):
                builder.build(output)


if __name__ == "__main__":
    unittest.main()
