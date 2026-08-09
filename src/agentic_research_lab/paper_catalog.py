from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from importlib.resources import files
from pathlib import Path
from typing import Any

from .catalog import tokenize
from .enrichment import (
    DECISIONS_FILENAME,
    REPOSITORY_CATALOG_FILENAME,
    build_code_gold_set,
    enrich_code_links,
    merge_repository_verification,
    write_repository_catalog,
)
from .models import Resource
from .taxonomy import enrich_taxonomy, write_taxonomy

CATALOG_ID = "conference-agent-papers-2026"
CATALOG_FILENAME = "conference_agent_papers_2026.json"
SCHEMA_VERSION = "2.0"
FORBIDDEN_PUBLIC_FIELDS = {"downloaded_path", "download_error"}
URL_FIELDS = {
    "official_page",
    "official_pdf",
    "resolved_pdf",
    "openreview",
    "arxiv_abs",
    "arxiv_pdf",
    "code",
}


def _clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _optional(value: str | None) -> str | None:
    cleaned = _clean(value)
    return cleaned or None


def _paper_id(row: dict[str, str]) -> str:
    conference = _clean(row.get("conference")).casefold()
    year = _clean(row.get("year"))
    source_id = _clean(row.get("paper_id") or row.get("openreview_id") or row.get("arxiv_id"))
    source_id = re.sub(r"[^a-zA-Z0-9._-]+", "-", source_id).strip("-")
    return f"{conference}-{year}-{source_id}"


def _authors(value: str | None) -> list[str]:
    cleaned = _clean(value)
    if not cleaned:
        return []
    return [author.strip() for author in re.split(r"\s*[;,]\s*", cleaned) if author.strip()]


def _links(row: dict[str, str]) -> dict[str, str | None]:
    arxiv_id = _clean(row.get("arxiv_id"))
    openreview_id = _clean(row.get("openreview_id"))
    return {
        "official_page": _optional(row.get("official_page")),
        "official_pdf": _optional(row.get("official_pdf")),
        "resolved_pdf": _optional(row.get("pdf_url")),
        "openreview": (
            f"https://openreview.net/forum?id={openreview_id}" if openreview_id else None
        ),
        "arxiv_abs": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else None,
        "arxiv_pdf": _optional(row.get("arxiv_pdf")),
        "code": None,
    }


def public_paper(row: dict[str, str]) -> dict[str, Any]:
    paper_id = _paper_id(row)
    return {
        "id": paper_id,
        "canonical_id": paper_id,
        "conference": _clean(row.get("conference")),
        "year": int(_clean(row.get("year")) or 0),
        "paper_id": _clean(row.get("paper_id")),
        "doi": None,
        "version": None,
        "updated_at": None,
        "title": _clean(row.get("title")),
        "authors": _authors(row.get("authors")),
        "abstract": _optional(row.get("abstract")),
        "track": _optional(row.get("track")),
        "selection": {
            "rule": _clean(row.get("selected_by")),
            "status": _clean(row.get("status")),
            "provenance": _clean(row.get("provenance")),
        },
        "links": _links(row),
        "topics": [],
        "tasks": [],
        "environments": [],
        "modalities": [],
        "agentic_components": [],
        "methods": [],
        "benchmarks": [],
        "datasets": [],
        "metrics": [],
        "claims": [],
        "limitations": [],
        "failure_modes": [],
        "artifacts": {"code_candidates": []},
        "evidence": [],
        "enrichment_status": {
            "code": "pending",
            "taxonomy": "pending",
            "fulltext": "pending",
        },
    }


def build_public_catalog(
    manifest: Path, decisions_path: Path | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_sha256 = hashlib.sha256(manifest.read_bytes()).hexdigest()
    with manifest.open(encoding="utf-8-sig", newline="") as stream:
        papers = [public_paper(row) for row in csv.DictReader(stream)]
    papers.sort(key=lambda paper: (paper["conference"], paper["title"].casefold()))
    repository_catalog = enrich_code_links(papers, decisions_path)
    conferences = Counter(paper["conference"] for paper in papers)
    catalog = {
        "schema_version": SCHEMA_VERSION,
        "catalog_version": f"2026.{manifest_sha256[:12]}",
        "id": CATALOG_ID,
        "title": "Conference Agent and Agentic Papers 2026",
        "description": (
            "Sanitized public metadata for the complete local 2026 Agent/Agentic conference "
            "paper manifest. Local paths and download diagnostics are excluded."
        ),
        "source": {
            "projection": "sanitized-conference-manifest",
            "records": len(papers),
            "sha256": manifest_sha256,
        },
        "summary": {
            "papers": len(papers),
            "conferences": dict(sorted(conferences.items())),
            "with_authors": sum(bool(paper["authors"]) for paper in papers),
            "with_abstract": sum(bool(paper["abstract"]) for paper in papers),
            "with_official_page": sum(bool(paper["links"]["official_page"]) for paper in papers),
            "with_resolved_pdf": sum(bool(paper["links"]["resolved_pdf"]) for paper in papers),
            "with_openreview": sum(bool(paper["links"]["openreview"]) for paper in papers),
            "with_arxiv": sum(bool(paper["links"]["arxiv_abs"]) for paper in papers),
            "with_code": sum(bool(paper["links"]["code"]) for paper in papers),
        },
        "papers": papers,
    }
    validate_public_catalog(catalog)
    return catalog, repository_catalog


def validate_public_catalog(catalog: dict[str, Any]) -> None:
    papers = catalog.get("papers", [])
    ids = [paper.get("id") for paper in papers]
    if len(ids) != len(set(ids)):
        raise ValueError("paper ids must be unique")
    for paper in papers:
        missing = [
            field
            for field in ("id", "conference", "year", "paper_id", "title")
            if not paper.get(field)
        ]
        if missing:
            raise ValueError(f"paper is missing required fields: {', '.join(missing)}")
        if FORBIDDEN_PUBLIC_FIELDS & set(paper):
            raise ValueError(f"paper {paper['id']} contains private download fields")
        links = paper.get("links", {})
        for field in URL_FIELDS:
            value = links.get(field)
            if value and not value.startswith(("https://", "http://")):
                raise ValueError(f"paper {paper['id']} has invalid {field} URL")
        if not links.get("official_page"):
            raise ValueError(f"paper {paper['id']} has no official page")


def write_public_catalog(catalog: dict[str, Any], target: Path) -> Path:
    validate_public_catalog(catalog)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def load_public_catalog(path: Path | None = None) -> dict[str, Any]:
    if path:
        raw = path.read_text(encoding="utf-8")
    else:
        raw = (
            files("agentic_research_lab")
            .joinpath(f"data/{CATALOG_FILENAME}")
            .read_text(encoding="utf-8")
        )
    catalog = json.loads(raw)
    validate_public_catalog(catalog)
    return catalog


def get_public_paper(catalog: dict[str, Any], paper_id: str) -> dict[str, Any]:
    normalized = paper_id.casefold()
    for paper in catalog["papers"]:
        if paper["id"].casefold() == normalized:
            return paper
    raise KeyError(f"unknown paper id: {paper_id}")


def paper_as_resource(paper: dict[str, Any]) -> Resource:
    links = paper["links"]
    abstract = paper.get("abstract")
    summary = abstract or (
        f"{paper['conference']} {paper['year']} paper. Abstract is not present in the catalog."
    )
    mobile_text = f"{paper['title']} {abstract or ''}".casefold()
    mobile = any(
        term in mobile_text
        for term in ("android", "ios", "mobile", "phone", "smartphone", "tablet")
    )
    return Resource(
        id=paper["id"],
        title=paper["title"],
        kind="paper",
        scope="mobile" if mobile else "general-agentic",
        year=int(paper["year"]),
        summary=summary[:500],
        tags=tuple(
            filter(
                None,
                [paper["conference"], paper.get("track"), paper["selection"].get("rule")],
            )
        ),
        venue=f"{paper['conference']} {paper['year']}",
        paper_url=links["official_page"],
        code_url=links.get("code") or "",
        status=paper["selection"].get("status") or "catalog",
    )


def search_public_catalog(
    catalog: dict[str, Any],
    query: str,
    limit: int = 10,
    conference: str | None = None,
) -> list[Resource]:
    query_tokens = tokenize(query)
    scored: list[tuple[float, Resource]] = []
    for paper in catalog["papers"]:
        if conference and paper["conference"].casefold() != conference.casefold():
            continue
        title_tokens = tokenize(paper["title"])
        abstract_tokens = tokenize(paper.get("abstract") or "")
        metadata_tokens = tokenize(
            " ".join(
                filter(
                    None,
                    [
                        paper["conference"],
                        paper.get("track"),
                        paper["selection"].get("rule"),
                    ],
                )
            )
        )
        score = (
            6 * len(query_tokens & title_tokens)
            + 2 * len(query_tokens & abstract_tokens)
            + len(query_tokens & metadata_tokens)
        )
        if query_tokens and score == 0:
            continue
        resource = paper_as_resource(paper)
        scored.append((score + resource.year / 10_000, resource))
    scored.sort(key=lambda pair: (pair[0], pair[1].title), reverse=True)
    return [resource for _, resource in scored[:limit]]


def _markdown_text(value: str) -> str:
    return value.replace("[", "\\[").replace("]", "\\]").replace("\n", " ")


def _paper_links(paper: dict[str, Any]) -> str:
    links = paper["links"]
    labels = [
        ("page", links.get("official_page")),
        ("pdf", links.get("resolved_pdf")),
        ("OpenReview", links.get("openreview")),
        ("arXiv", links.get("arxiv_abs")),
        ("code", links.get("code")),
    ]
    return " · ".join(f"[{label}]({url})" for label, url in labels if url)


def render_corpus_index(catalog: dict[str, Any]) -> str:
    summary = catalog["summary"]
    lines = [
        "# Awesome Conference Agent and Agentic Papers 2026",
        "",
        "> Complete, sanitized metadata for the 2026 conference Agent/Agentic paper corpus.",
        "",
        "The 32-entry Mobile Agentic AI theme remains the curated starting point. This section",
        "is the exhaustive corpus layer: every source-manifest row is retained and traceable.",
        "",
        "## Coverage",
        "",
        f"- Papers: **{summary['papers']:,}**",
        f"- Public paper pages: **{summary['with_official_page']:,}**",
        f"- Direct PDF links: **{summary['with_resolved_pdf']:,}**",
        f"- Abstracts: **{summary['with_abstract']:,}**",
        f"- Author lists: **{summary['with_authors']:,}**",
        f"- OpenReview links: **{summary['with_openreview']:,}**",
        f"- arXiv links: **{summary['with_arxiv']:,}**",
        f"- Verified code links: **{summary['with_code']:,}**",
        "",
        "## Conferences",
        "",
        "| Conference | Papers | Full list |",
        "| --- | ---: | --- |",
    ]
    for conference, count in summary["conferences"].items():
        lines.append(
            f"| {conference} 2026 | {count:,} | [{conference}-2026.md]({conference}-2026.md) |"
        )
    lines.extend(
        [
            "",
            "## Machine-readable catalog",
            "",
            "The complete records, including abstracts and all available public addresses, are in",
            f"[`{CATALOG_FILENAME}`](../../src/agentic_research_lab/data/{CATALOG_FILENAME}).",
            "",
            "Local download paths and download diagnostics are intentionally excluded. Missing",
            "authors, abstracts, direct PDFs, or code links remain explicit null/empty values.",
            "",
        ]
    )
    return "\n".join(lines)


def render_conference_page(catalog: dict[str, Any], conference: str) -> str:
    papers = [paper for paper in catalog["papers"] if paper["conference"] == conference]
    lines = [
        f"# {conference} 2026 Agent and Agentic Papers",
        "",
        f"**{len(papers):,} papers.** [Back to corpus index](README.md).",
        "",
        "Each entry links to the official paper page and every additional public address present",
        "in the source manifest. Full abstracts and structured metadata are in the JSON catalog.",
        "",
    ]
    for paper in papers:
        authors = ", ".join(paper["authors"]) if paper["authors"] else "Authors unavailable"
        metadata = " · ".join(
            filter(
                None,
                [
                    f"ID: {paper['paper_id']}",
                    paper.get("track"),
                    paper["selection"].get("status"),
                ],
            )
        )
        lines.append(f"- **{_markdown_text(paper['title'])}** — {_markdown_text(authors)}")
        lines.append(f"  - {_paper_links(paper)}")
        lines.append(f"  - `{_markdown_text(metadata)}`")
    lines.append("")
    return "\n".join(lines)


def write_corpus_awesome(catalog: dict[str, Any], target: Path) -> list[Path]:
    validate_public_catalog(catalog)
    target.mkdir(parents=True, exist_ok=True)
    outputs = [target / "README.md"]
    outputs[0].write_text(render_corpus_index(catalog), encoding="utf-8")
    for conference in catalog["summary"]["conferences"]:
        page = target / f"{conference}-2026.md"
        page.write_text(render_conference_page(catalog, conference), encoding="utf-8")
        outputs.append(page)
    return outputs


def build_public_assets(manifest: Path, data_target: Path, awesome_target: Path) -> dict[str, Any]:
    decisions_target = data_target.with_name(DECISIONS_FILENAME)
    catalog, repositories = build_public_catalog(
        manifest, decisions_target if decisions_target.is_file() else None
    )
    coverage = enrich_taxonomy(catalog)
    write_public_catalog(catalog, data_target)
    taxonomy_target = data_target.with_name("agentic_taxonomy.json")
    write_taxonomy(taxonomy_target)
    repository_target = data_target.with_name(REPOSITORY_CATALOG_FILENAME)
    merge_repository_verification(repositories, repository_target)
    write_repository_catalog(repositories, repository_target)
    gold_target = data_target.parents[3] / "evals" / "code_link_gold_v1.json"
    gold = build_code_gold_set(catalog["papers"], gold_target)
    pages = write_corpus_awesome(catalog, awesome_target)
    return {
        "papers": catalog["summary"]["papers"],
        "code_links": catalog["summary"]["with_code"],
        "repositories": repositories["summary"]["repositories"],
        "gold_examples": len(gold["examples"]),
        "taxonomy_coverage": coverage,
        "data": str(data_target),
        "taxonomy_data": str(taxonomy_target),
        "repository_data": str(repository_target),
        "code_gold": str(gold_target),
        "pages": [str(page) for page in pages],
    }
