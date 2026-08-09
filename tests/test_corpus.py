import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agentic_research_lab.corpus import corpus_stats, search_corpus


class CorpusTests(unittest.TestCase):
    def test_search_external_manifest(self) -> None:
        fields = [
            "conference",
            "year",
            "paper_id",
            "title",
            "abstract",
            "track",
            "official_page",
            "selected_by",
            "status",
        ]
        rows = [
            {
                "conference": "TEST",
                "year": "2026",
                "paper_id": "1",
                "title": "Private Mobile Agent Memory",
                "abstract": "An Android agent with privacy-preserving memory.",
                "track": "Agents",
                "official_page": "https://example.org/paper/1",
                "selected_by": "title-agent-term",
                "status": "selected",
            },
            {
                "conference": "TEST",
                "year": "2026",
                "paper_id": "2",
                "title": "Graph Clustering",
                "abstract": "A clustering method.",
                "track": "Machine Learning",
                "official_page": "https://example.org/paper/2",
                "selected_by": "other",
                "status": "selected",
            },
        ]
        with TemporaryDirectory() as directory:
            manifest = Path(directory) / "papers.csv"
            with manifest.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            results = search_corpus(manifest, "mobile privacy memory", limit=5)
            self.assertEqual(
                [resource.title for resource in results], ["Private Mobile Agent Memory"]
            )
            self.assertEqual(corpus_stats(manifest)["papers"], 2)


if __name__ == "__main__":
    unittest.main()
