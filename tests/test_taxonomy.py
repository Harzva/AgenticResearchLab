import sqlite3
import unittest

from agentic_research_lab.paper_catalog import load_public_catalog
from agentic_research_lab.store import initialize_store
from agentic_research_lab.taxonomy import build_relation_graph, classify_text, enrich_taxonomy


class TaxonomyTests(unittest.TestCase):
    def test_mobile_agent_components(self) -> None:
        labels = classify_text(
            "An Android mobile GUI agent with long-term memory, reflection and safety verification"
        )
        self.assertIn("mobile-agentic-ai", labels["topics"])
        self.assertIn("memory", labels["agentic_components"])
        self.assertIn("reflection", labels["agentic_components"])
        self.assertIn("android", labels["environments"])

    def test_catalog_graph_is_traceable(self) -> None:
        catalog = load_public_catalog()
        enrich_taxonomy(catalog)
        connection = sqlite3.connect(":memory:")
        try:
            initialize_store(connection)
            stats = build_relation_graph(catalog, connection)
            self.assertGreater(stats["entities"], 20)
            self.assertGreater(stats["edges"], 1000)
            evidence = connection.execute("SELECT evidence_json FROM edges LIMIT 1").fetchone()[0]
            self.assertIn("source", evidence)
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
