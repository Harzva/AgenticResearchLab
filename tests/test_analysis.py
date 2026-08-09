import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agentic_research_lab.analysis import build_research_report, profile_repository
from agentic_research_lab.catalog import get_topic


class AnalysisTests(unittest.TestCase):
    def test_topic_report_is_grounded(self) -> None:
        report = build_research_report(
            "privacy-aware Android assistant with long-term memory",
            "",
            get_topic("mobile-agentic-ai"),
            top_k=5,
        )
        self.assertIn("Evidence retrieved", report)
        self.assertIn("Agentic necessity", report)
        self.assertIn("http", report)

    def test_repository_profile(self) -> None:
        with TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            (tmp_path / "README.md").write_text(
                "An Android app automation project", encoding="utf-8"
            )
            (tmp_path / "main.kt").write_text("fun main() = Unit", encoding="utf-8")
            profile = profile_repository(tmp_path)
            self.assertIn("Android", profile.text)
            self.assertIn((".kt", 1), profile.extensions)

    def test_chinese_report_detects_capabilities(self) -> None:
        report = build_research_report(
            "手机端隐私感知的长期记忆智能体",
            "",
            get_topic("mobile-agentic-ai"),
            top_k=5,
        )
        self.assertIn("memory-reflection", report)
        self.assertIn("personalization-privacy", report)
        self.assertIn("efficiency-deployment", report)


if __name__ == "__main__":
    unittest.main()
