from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    data = ROOT / "src/agentic_research_lab/data"
    catalog = json.loads((data / "conference_agent_papers_2026.json").read_text())
    repositories = json.loads((data / "code_repositories_2026.json").read_text())
    metrics = json.loads((ROOT / "evals/latest_metrics.json").read_text())
    assert catalog["summary"]["papers"] == 1242
    assert catalog["summary"]["with_code"] == 154
    assert repositories["summary"]["repositories"] == 158
    assert repositories["summary"]["linked_papers"] == 154
    assert metrics["passed"] is True
    assert len({paper["id"] for paper in catalog["papers"]}) == 1242
    pages = ROOT / "awesome/all-agentic-papers-2026"
    entries = sum(
        (pages / f"{conference}-2026.md").read_text().count("\n- **")
        for conference in catalog["summary"]["conferences"]
    )
    assert entries == 1242
    for schema in (ROOT / "schemas").glob("*.json"):
        json.loads(schema.read_text())
    print("repository validation: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
