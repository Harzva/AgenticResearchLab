import unittest
from pathlib import Path

from agentic_research_lab.evaluation import (
    build_retrieval_gold,
    evaluate_code_links,
    evaluate_proposals,
    evaluate_retrieval,
)
from agentic_research_lab.paper_catalog import load_public_catalog


class EvaluationTests(unittest.TestCase):
    def test_code_and_retrieval_gates(self) -> None:
        catalog = load_public_catalog()
        code = evaluate_code_links(catalog, Path("evals/code_link_gold_v1.json"))
        self.assertTrue(code["passed"])
        retrieval = evaluate_retrieval(
            catalog, Path("evals/retrieval_gold_v1.json"), Path("does-not-exist.sqlite3")
        )
        self.assertGreaterEqual(retrieval["recall_at_k"], 0.85)

    def test_gold_builder_and_proposal_regression(self) -> None:
        catalog = load_public_catalog()
        with self.subTest("gold-size"):
            gold = build_retrieval_gold(catalog, Path(".arl/test-retrieval-gold.json"), 100)
            self.assertEqual(len(gold["examples"]), 100)
        proposal = evaluate_proposals(catalog, Path("does-not-exist.sqlite3"))
        self.assertTrue(proposal["passed"])


if __name__ == "__main__":
    unittest.main()
