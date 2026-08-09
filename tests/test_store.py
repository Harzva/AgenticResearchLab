import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from agentic_research_lab.paper_catalog import load_public_catalog
from agentic_research_lab.store import (
    connect_store,
    index_catalog,
    replace_paper_chunks,
    search_store,
)


class StoreTests(unittest.TestCase):
    def test_catalog_and_fulltext_evidence_search(self) -> None:
        with TemporaryDirectory() as directory:
            store = Path(directory) / "catalog.sqlite3"
            catalog = load_public_catalog()
            stats = index_catalog(catalog, store)
            self.assertEqual(stats["papers"], 1242)
            paper = next(paper for paper in catalog["papers"] if "Memory" in paper["title"])
            with closing(connect_store(store)) as connection:
                replace_paper_chunks(
                    connection,
                    paper["id"],
                    [
                        {
                            "chunk_id": f"{paper['id']}-p0003-c01",
                            "page_start": 3,
                            "page_end": 3,
                            "section": "method",
                            "kind": "body",
                            "text": "A selective episodic memory retrieves prior mobile actions.",
                            "token_count": 9,
                            "pdf_checksum": "abc",
                            "extractor_version": "test",
                        }
                    ],
                )
                connection.commit()
            hits = search_store("selective episodic memory", store, limit=5)
            self.assertTrue(hits)
            self.assertEqual(hits[0].kind, "fulltext")
            self.assertEqual(hits[0].page_start, 3)
            self.assertIn("#page=3", hits[0].source_url)


if __name__ == "__main__":
    unittest.main()
