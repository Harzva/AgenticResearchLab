import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agentic_research_lab.paper_catalog import load_public_catalog
from agentic_research_lab.proposals import (
    build_proposal_bundle,
    compare_papers,
    reject_proposal,
    write_proposal_workspace,
)
from agentic_research_lab.store import index_catalog
from agentic_research_lab.taxonomy import enrich_taxonomy


class ProposalTests(unittest.TestCase):
    def test_proposal_bundle_is_evidence_grounded_and_rejectable(self) -> None:
        with TemporaryDirectory() as directory:
            catalog = load_public_catalog()
            enrich_taxonomy(catalog)
            store = Path(directory) / "catalog.sqlite3"
            index_catalog(catalog, store)
            bundle = build_proposal_bundle(
                "privacy-aware mobile agent with long-term memory",
                catalog=catalog,
                store_path=store,
                top_k=6,
            )
            self.assertEqual(len(bundle["candidates"]), 3)
            proposal = bundle["candidates"][0]
            self.assertGreaterEqual(len(proposal["nearest_work"]), 3)
            self.assertIn("rejected if", proposal["falsifiable_claim"])
            result = reject_proposal(proposal)
            self.assertEqual(result["status"], "pass")
            outputs = write_proposal_workspace(bundle, Path(directory) / "workspace")
            self.assertTrue(all(path.is_file() for path in outputs))

    def test_compare_papers_has_research_dimensions(self) -> None:
        catalog = load_public_catalog()
        enrich_taxonomy(catalog)
        mobile = [paper for paper in catalog["papers"] if "mobile-agentic-ai" in paper["topics"]]
        result = compare_papers(mobile[0]["id"], mobile[1]["id"], catalog)
        self.assertIn("agentic_components", result["dimensions"])
        self.assertNotEqual(result["left"]["id"], result["right"]["id"])


if __name__ == "__main__":
    unittest.main()
