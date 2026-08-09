import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agentic_research_lab.paper_catalog import (
    build_public_catalog,
    get_public_paper,
    load_public_catalog,
    render_conference_page,
    search_public_catalog,
    write_public_catalog,
)


class PaperCatalogTests(unittest.TestCase):
    def _manifest(self, directory: str) -> Path:
        manifest = Path(directory) / "papers.csv"
        fields = [
            "conference",
            "year",
            "paper_id",
            "title",
            "authors",
            "abstract",
            "track",
            "official_page",
            "official_pdf",
            "openreview_id",
            "arxiv_id",
            "arxiv_pdf",
            "selected_by",
            "status",
            "provenance",
            "downloaded_path",
            "download_error",
            "pdf_url",
        ]
        row = {
            "conference": "TEST",
            "year": "2026",
            "paper_id": "42",
            "title": "A Mobile Agent",
            "authors": "Ada Example; Lin Example",
            "abstract": "A privacy-aware Android agent.",
            "track": "Agents",
            "official_page": "https://example.org/papers/42",
            "official_pdf": "https://example.org/papers/42.pdf",
            "openreview_id": "test42",
            "arxiv_id": "2601.00042",
            "arxiv_pdf": "https://arxiv.org/pdf/2601.00042",
            "selected_by": "title-agent-term",
            "status": "selected",
            "provenance": "official-index",
            "downloaded_path": "/private/papers/42.pdf",
            "download_error": "private diagnostic",
            "pdf_url": "https://example.org/papers/42.pdf",
        }
        with manifest.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerow(row)
        return manifest

    def test_public_export_strips_local_download_fields(self) -> None:
        with TemporaryDirectory() as directory:
            catalog = build_public_catalog(self._manifest(directory))
            paper = catalog["papers"][0]
            self.assertNotIn("downloaded_path", paper)
            self.assertNotIn("download_error", paper)
            self.assertEqual(paper["authors"], ["Ada Example", "Lin Example"])
            self.assertEqual(paper["links"]["official_page"], "https://example.org/papers/42")
            self.assertEqual(paper["links"]["openreview"], "https://openreview.net/forum?id=test42")
            self.assertIsNone(paper["links"]["code"])

    def test_round_trip_search_and_render(self) -> None:
        with TemporaryDirectory() as directory:
            catalog = build_public_catalog(self._manifest(directory))
            target = Path(directory) / "catalog.json"
            write_public_catalog(catalog, target)
            loaded = load_public_catalog(target)
            paper = get_public_paper(loaded, "test-2026-42")
            self.assertEqual(paper["title"], "A Mobile Agent")
            results = search_public_catalog(loaded, "手机隐私智能体", limit=5)
            self.assertEqual([result.title for result in results], ["A Mobile Agent"])
            page = render_conference_page(loaded, "TEST")
            self.assertIn("https://example.org/papers/42", page)
            self.assertIn("2601.00042", page)

    def test_packaged_catalog_has_complete_manifest(self) -> None:
        catalog = load_public_catalog()
        self.assertEqual(catalog["summary"]["papers"], 1242)
        self.assertEqual(catalog["summary"]["with_official_page"], 1242)
        self.assertEqual(len(catalog["papers"]), 1242)
        root = Path(__file__).resolve().parents[1] / "awesome" / "all-agentic-papers-2026"
        pages = [
            (root / f"{conference}-2026.md").read_text(encoding="utf-8")
            for conference in catalog["summary"]["conferences"]
        ]
        self.assertEqual(sum(page.count("\n- **") for page in pages), 1242)
        for paper in catalog["papers"]:
            conference_page = pages[
                list(catalog["summary"]["conferences"]).index(paper["conference"])
            ]
            self.assertIn(paper["links"]["official_page"], conference_page)


if __name__ == "__main__":
    unittest.main()
