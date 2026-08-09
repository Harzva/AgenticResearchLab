import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agentic_research_lab.paper_catalog import load_public_catalog
from agentic_research_lab.store import index_catalog
from agentic_research_lab.vectors import HashEmbeddingProvider, build_vector_index, hybrid_search


class VectorTests(unittest.TestCase):
    def test_hash_vector_index_and_hybrid_search(self) -> None:
        with TemporaryDirectory() as directory:
            store = Path(directory) / "catalog.sqlite3"
            catalog = load_public_catalog()
            index_catalog(catalog, store)
            result = build_vector_index(catalog, store, HashEmbeddingProvider(128))
            self.assertEqual(result["papers"], 1242)
            hits = hybrid_search(
                "mobile GUI agent Android memory",
                store,
                HashEmbeddingProvider(128),
                limit=10,
            )
            self.assertTrue(hits)
            self.assertTrue(any("Mobile" in hit.title or "GUI" in hit.title for hit in hits))


if __name__ == "__main__":
    unittest.main()
