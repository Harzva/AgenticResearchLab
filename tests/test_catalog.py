import unittest

from agentic_research_lab.catalog import get_topic, load_topics, render_awesome, search, tokenize


class CatalogTests(unittest.TestCase):
    def test_catalog_is_valid_and_unique(self) -> None:
        topics = load_topics()
        topic = topics["mobile-agentic-ai"]
        ids = [resource.id for resource in topic.resources]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreaterEqual(len(ids), 25)

    def test_search_finds_mobile_safety(self) -> None:
        results = search(
            get_topic("mobile-agentic-ai"), "mobile safety environmental injection", limit=5
        )
        titles = " ".join(resource.title for resource in results)
        self.assertTrue("MobileSafetyBench" in titles or "GhostEI" in titles)

    def test_awesome_has_expected_sections(self) -> None:
        rendered = render_awesome(get_topic("mobile-agentic-ai"))
        self.assertIn("## Mobile agents and methods", rendered)
        self.assertIn("## Benchmarks and datasets", rendered)
        self.assertIn("AndroidWorld", rendered)

    def test_tokenize_supports_chinese_queries(self) -> None:
        tokens = tokenize("手机隐私 Agent")
        self.assertTrue({"手机", "隐私", "agent", "mobile", "privacy"}.issubset(tokens))

    def test_chinese_search_finds_mobile_safety(self) -> None:
        results = search(get_topic("mobile-agentic-ai"), "手机智能体安全评测", limit=5)
        titles = " ".join(resource.title for resource in results)
        self.assertTrue("MobileSafetyBench" in titles or "GhostEI" in titles)


if __name__ == "__main__":
    unittest.main()
