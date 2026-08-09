import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agentic_research_lab.enrichment import (
    enrich_code_links,
    extract_repository_urls,
    normalize_repository_url,
)


class EnrichmentTests(unittest.TestCase):
    def test_extract_and_normalize_repository_urls(self) -> None:
        text = "Code: https://github.com/Example/Agent.git."
        self.assertEqual(extract_repository_urls(text), ["https://github.com/Example/Agent"])
        self.assertEqual(
            normalize_repository_url(
                "https://github.com/example/mono/tree/main/agent", canonical=True
            ),
            "https://github.com/example/mono",
        )

    def test_explicit_official_url_is_verified(self) -> None:
        paper = {
            "id": "test-2026-1",
            "title": "Test Agent",
            "abstract": "Implementation: https://github.com/example/test-agent",
            "links": {"official_page": "https://example.org/paper", "code": None},
            "artifacts": {"code_candidates": []},
            "enrichment_status": {"code": "pending"},
        }
        catalog = enrich_code_links([paper])
        self.assertEqual(paper["links"]["code"], "https://github.com/example/test-agent")
        self.assertEqual(paper["enrichment_status"]["code"], "verified")
        self.assertEqual(catalog["summary"]["repositories"], 1)
        self.assertEqual(catalog["repositories"][0]["verification"][0]["confidence"], 1.0)

    def test_unavailable_decision_is_retained_as_negative_evidence(self) -> None:
        paper = {
            "id": "test-2026-missing",
            "title": "Missing Agent",
            "abstract": "Code: https://github.com/example/missing-agent",
            "links": {"official_page": "https://example.org/paper", "code": None},
            "artifacts": {"code_candidates": []},
            "enrichment_status": {"code": "pending"},
        }
        decisions = {
            "schema_version": "1.0",
            "decisions": {
                paper["id"]: {
                    "status": "unavailable",
                    "url": "https://github.com/example/missing-agent",
                    "reason": "github-http-404",
                }
            },
        }
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "decisions.json"
            path.write_text(json.dumps(decisions), encoding="utf-8")
            catalog = enrich_code_links([paper], path)

        self.assertIsNone(paper["links"]["code"])
        self.assertEqual(catalog["summary"]["repositories"], 1)
        self.assertEqual(catalog["repositories"][0]["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
