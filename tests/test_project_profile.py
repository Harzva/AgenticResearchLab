import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agentic_research_lab.project_profile import inspect_project


class ProjectProfileTests(unittest.TestCase):
    def test_inspection_detects_capabilities_and_skips_secrets(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text(
                "# Mobile Assistant\n\nAn Android agent that plans actions and recovers from failures.",
                encoding="utf-8",
            )
            (root / "main.kt").write_text(
                "// Android planner with tool_call, memory, verifier, retry and screenshot",
                encoding="utf-8",
            )
            (root / ".env").write_text("API_KEY=private", encoding="utf-8")
            tests = root / "tests"
            tests.mkdir()
            (tests / "test_main.py").write_text("def test_ok(): pass", encoding="utf-8")
            profile = inspect_project(root)
            self.assertIn("Kotlin", profile["languages"])
            self.assertIn("planning", profile["agentic_capabilities"])
            self.assertIn("memory", profile["agentic_capabilities"])
            self.assertEqual(profile["quality"]["test_files"], 1)
            serialized = str(profile)
            self.assertNotIn("API_KEY", serialized)
            self.assertNotIn("API_KEY=private", serialized)


if __name__ == "__main__":
    unittest.main()
