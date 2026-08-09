from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "src/agentic_research_lab/data/conference_agent_papers_2026.json"
SOURCE = ROOT / "site"
DEFAULT_OUTPUT = ROOT / "_site"


def public_web_paper(paper: dict[str, Any]) -> dict[str, Any]:
    links = paper["links"]
    taxonomy = [
        *paper.get("topics", []),
        *paper.get("agentic_components", []),
        *paper.get("environments", []),
        *paper.get("modalities", []),
        *paper.get("failure_modes", []),
    ]
    return {
        "id": paper["id"],
        "title": paper["title"],
        "conference": paper["conference"],
        "year": paper["year"],
        "abstract": paper.get("abstract"),
        "taxonomy": list(dict.fromkeys(taxonomy)),
        "links": {
            "official_page": links["official_page"],
            "pdf": links.get("resolved_pdf"),
            "code": links.get("code"),
        },
    }


def build(output: Path) -> dict[str, Any]:
    resolved_output = output.resolve()
    if resolved_output in {ROOT.resolve(), ROOT.parent.resolve()}:
        raise ValueError("refusing to replace the repository or its parent")
    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(SOURCE, output)
    (output / ".nojekyll").write_text("", encoding="utf-8")
    payload = json.loads(CATALOG.read_text(encoding="utf-8"))
    web_catalog = {
        "schema_version": "1.0",
        "catalog_version": payload["catalog_version"],
        "summary": payload["summary"],
        "papers": [public_web_paper(paper) for paper in payload["papers"]],
    }
    data = output / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "catalog.json").write_text(
        json.dumps(web_catalog, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    result = {
        "output": str(output),
        "papers": len(web_catalog["papers"]),
        "with_code": payload["summary"]["with_code"],
        "catalog_bytes": (data / "catalog.json").stat().st_size,
    }
    (output / "build.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the static AgenticResearchLab Pages site")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build(args.output), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
