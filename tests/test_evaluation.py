import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agentic_research_lab.evaluation import (
    build_human_evaluation_scaffold,
    build_retrieval_gold,
    compare_evaluation_reports,
    evaluate_code_links,
    evaluate_proposals,
    evaluate_retrieval,
    evaluate_suite,
    render_evaluation_markdown,
    validate_evaluation_set,
    validate_evaluation_suite,
    write_evaluation_report,
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

    def test_human_scaffold_is_valid_but_explicitly_blocked(self) -> None:
        catalog = load_public_catalog()
        with TemporaryDirectory() as directory:
            root = Path(directory)
            outputs = build_human_evaluation_scaffold(catalog, root)
            self.assertEqual(len(outputs), 4)
            fulltext = json.loads(outputs[0].read_text(encoding="utf-8"))
            self.assertEqual(len(fulltext["examples"]), 100)
            self.assertEqual(fulltext["review_status"], "draft")
            self.assertTrue(all(not example["annotations"] for example in fulltext["examples"]))

            validation = validate_evaluation_suite(outputs[-1])
            self.assertTrue(validation["valid"])
            self.assertFalse(validation["gate_ready"])
            self.assertIn("reviewed examples 0/100", " ".join(validation["readiness_reasons"]))
            self.assertFalse(Path(validation["datasets"][0]["path"]).is_absolute())

            with self.assertRaises(FileExistsError):
                build_human_evaluation_scaffold(catalog, root)

    def test_review_status_cannot_bypass_independent_adjudication(self) -> None:
        catalog = load_public_catalog()
        with TemporaryDirectory() as directory:
            outputs = build_human_evaluation_scaffold(catalog, Path(directory))
            fulltext_path = outputs[0]
            fulltext = json.loads(fulltext_path.read_text(encoding="utf-8"))
            fulltext["review_status"] = "reviewed"
            fulltext_path.write_text(
                json.dumps(fulltext, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            validation = validate_evaluation_set(fulltext_path)
            self.assertTrue(validation["valid"])
            self.assertFalse(validation["gate_ready"])
            self.assertEqual(validation["reviewed_examples"], 0)

    def test_versioned_suite_report_and_baseline_difference(self) -> None:
        report = evaluate_suite(
            Path("evals/suites/smoke-v1.json"), store_path=Path("does-not-exist.sqlite3")
        )
        self.assertTrue(report["passed"])
        self.assertEqual(report["report_schema_version"], "1.0")
        self.assertEqual(report["evaluation_suite"]["tier"], "required")
        self.assertEqual(report["corpus"]["papers"], 1242)
        self.assertEqual(
            report["evaluations"]["retrieval-smoke"]["error_categories"],
            {"no_relevant_in_top_k": 0, "partial_recall": 0},
        )
        comparison = compare_evaluation_reports(report, report)
        self.assertTrue(comparison["metrics"])
        self.assertTrue(all(metric["delta"] == 0 for metric in comparison["metrics"].values()))

        markdown = render_evaluation_markdown(report)
        self.assertIn("Status: **PASSED**", markdown)
        self.assertIn("Interpretation boundary", markdown)
        with TemporaryDirectory() as directory:
            json_path = Path(directory) / "report.json"
            outputs = write_evaluation_report(report, json_path)
            self.assertTrue(all(path.is_file() for path in outputs))


if __name__ == "__main__":
    unittest.main()
