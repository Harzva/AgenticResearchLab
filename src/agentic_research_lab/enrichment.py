from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

REPOSITORY_CATALOG_FILENAME = "code_repositories_2026.json"
DECISIONS_FILENAME = "code_link_decisions.json"
GIT_REPOSITORY_RE = re.compile(
    r"https?://(?:www\.)?(?:github\.com|gitlab\.com)/[^\s<>\"'\\\\}]+",
    re.IGNORECASE,
)
TRAILING_URL_CHARS = ".,;:!?)]}\\"


def normalize_repository_url(url: str, *, canonical: bool = False) -> str:
    cleaned = url.strip().rstrip(TRAILING_URL_CHARS)
    parts = urlsplit(cleaned)
    path_parts = [part for part in parts.path.split("/") if part]
    if len(path_parts) < 2:
        return ""
    owner, repository = path_parts[:2]
    repository = repository.removesuffix(".git")
    path = f"/{owner}/{repository}"
    if not canonical and len(path_parts) > 2:
        path += "/" + "/".join(path_parts[2:])
    return urlunsplit(("https", parts.netloc.casefold().removeprefix("www."), path, "", ""))


def extract_repository_urls(text: str | None) -> list[str]:
    urls: list[str] = []
    for match in GIT_REPOSITORY_RE.findall(text or ""):
        normalized = normalize_repository_url(match)
        if normalized and normalized not in urls:
            urls.append(normalized)
    return urls


def _manual_decisions(path: Path | None) -> dict[str, dict[str, Any]]:
    if not path or not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    decisions = raw.get("decisions", raw)
    if not isinstance(decisions, dict):
        raise TypeError("code-link decisions must be an object keyed by paper id")
    return decisions


def enrich_code_links(
    papers: list[dict[str, Any]], decisions_path: Path | None = None
) -> dict[str, Any]:
    decisions = _manual_decisions(decisions_path)
    repositories: dict[str, dict[str, Any]] = {}
    status_counts: defaultdict[str, int] = defaultdict(int)
    for paper in papers:
        explicit_urls = extract_repository_urls(paper.get("abstract"))
        decision = decisions.get(paper["id"], {})
        decision_status = decision.get("status")
        selected_url = decision.get("url")
        method = "manual-decision" if decision else "official-abstract-explicit-url"
        if decision_status in {"rejected", "ambiguous", "not-found", "unavailable"}:
            selected_url = None
            status = decision_status
        elif selected_url:
            selected_url = normalize_repository_url(str(selected_url))
            status = "verified"
        elif explicit_urls:
            selected_url = explicit_urls[0]
            status = "verified" if len(explicit_urls) == 1 else "ambiguous"
            if status == "ambiguous":
                selected_url = None
        else:
            status = "not-found"
        status_counts[status] += 1
        paper["links"]["code"] = selected_url
        paper["enrichment_status"]["code"] = status
        paper["artifacts"]["code_candidates"] = explicit_urls
        # Keep rejected/unavailable candidates in the repository audit catalog even
        # though they must never be exposed as a verified paper code link. This
        # makes a decisions-backed offline rebuild reproduce the live verification
        # result instead of silently dropping negative evidence.
        repository_url = selected_url or decision.get("url")
        if not repository_url:
            continue
        repository_url = normalize_repository_url(str(repository_url))
        if not repository_url:
            continue
        canonical_url = normalize_repository_url(repository_url, canonical=True)
        repository_id = canonical_url.removeprefix("https://").casefold()
        record = repositories.setdefault(
            repository_id,
            {
                "id": repository_id,
                "url": canonical_url,
                "source_urls": [],
                "paper_ids": [],
                "license": None,
                "default_branch": None,
                "archived": None,
                "languages": [],
                "frameworks": [],
                "entrypoints": [],
                "tests": [],
                "environments": [],
                "installability": "not-checked",
                "reproducibility_assets": [],
                "last_verified_at": None,
                "status": status,
                "verification": [],
            },
        )
        if repository_url not in record["source_urls"]:
            record["source_urls"].append(repository_url)
        if paper["id"] not in record["paper_ids"]:
            record["paper_ids"].append(paper["id"])
        record["verification"].append(
            {
                "paper_id": paper["id"],
                "source": "abstract" if not decision else "manual-decision",
                "source_url": paper["links"]["official_page"],
                "method": method,
                "confidence": 1.0,
            }
        )
    records = sorted(repositories.values(), key=lambda item: item["id"])
    return {
        "schema_version": "1.0",
        "id": "verified-code-repositories-2026",
        "description": (
            "Verified paper-to-code links extracted from official paper metadata. "
            "Unknown repository metadata remains null until independently checked."
        ),
        "summary": {
            "repositories": len(records),
            "linked_papers": sum(bool(paper["links"]["code"]) for paper in papers),
            "paper_extraction_status": dict(sorted(status_counts.items())),
            "repository_status": dict(
                sorted(
                    {
                        status: sum(record["status"] == status for record in records)
                        for status in {record["status"] for record in records}
                    }.items()
                )
            ),
        },
        "repositories": records,
    }


def write_repository_catalog(catalog: dict[str, Any], target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def verify_github_repositories(
    catalog: dict[str, Any], *, token: str | None = None, resume: bool = False
) -> dict[str, int]:
    github_token = token or os.environ.get("ARL_GITHUB_TOKEN")
    counts: defaultdict[str, int] = defaultdict(int)
    for repository in catalog["repositories"]:
        if resume and repository.get("last_verified_at"):
            counts["skipped"] += 1
            continue
        parts = urlsplit(repository["url"])
        path_parts = [part for part in parts.path.split("/") if part]
        if parts.netloc.casefold() != "github.com" or len(path_parts) != 2:
            counts["unsupported"] += 1
            continue
        request = Request(
            f"https://api.github.com/repos/{path_parts[0]}/{path_parts[1]}",
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "AgenticResearchLab/0.2",
                **({"Authorization": f"Bearer {github_token}"} if github_token else {}),
            },
        )
        try:
            with urlopen(request, timeout=20) as response:
                payload = json.load(response)
        except HTTPError as exc:
            repository["status"] = "unavailable" if exc.code == 404 else "verification-error"
            repository["verification_error"] = f"github-http-{exc.code}"
            repository["last_verified_at"] = datetime.now(UTC).replace(microsecond=0).isoformat()
            counts[repository["status"]] += 1
            continue
        except (URLError, TimeoutError):
            repository["status"] = "verification-error"
            repository["verification_error"] = "github-network-error"
            repository["last_verified_at"] = datetime.now(UTC).replace(microsecond=0).isoformat()
            counts["verification-error"] += 1
            continue
        repository["url"] = payload.get("html_url") or repository["url"]
        repository["license"] = (payload.get("license") or {}).get("spdx_id")
        repository["default_branch"] = payload.get("default_branch")
        repository["archived"] = bool(payload.get("archived"))
        repository["languages"] = list(filter(None, [payload.get("language")]))
        repository["last_verified_at"] = datetime.now(UTC).replace(microsecond=0).isoformat()
        repository["status"] = "archived" if repository["archived"] else "verified"
        repository.pop("verification_error", None)
        counts[repository["status"]] += 1
    catalog["summary"]["github_verification"] = dict(sorted(counts.items()))
    return dict(counts)


def merge_repository_verification(target: dict[str, Any], existing_path: Path) -> dict[str, Any]:
    if not existing_path.is_file():
        return target
    existing = json.loads(existing_path.read_text(encoding="utf-8"))
    previous = {record["id"]: record for record in existing.get("repositories", [])}
    preserved_fields = {
        "license",
        "default_branch",
        "archived",
        "languages",
        "last_verified_at",
        "status",
        "verification_error",
    }
    for repository in target["repositories"]:
        old = previous.get(repository["id"])
        if not old:
            continue
        for field in preserved_fields:
            if field in old:
                repository[field] = old[field]
    return target


def apply_repository_statuses(
    papers: list[dict[str, Any]], repository_catalog: dict[str, Any]
) -> int:
    statuses = {record["id"]: record["status"] for record in repository_catalog["repositories"]}
    linked = 0
    for paper in papers:
        code_url = paper["links"].get("code")
        if not code_url:
            continue
        repository_id = normalize_repository_url(code_url, canonical=True)
        repository_id = repository_id.removeprefix("https://").casefold()
        status = statuses.get(repository_id, "verification-error")
        paper["enrichment_status"]["code"] = status
        if status not in {"verified", "archived"}:
            paper["links"]["code"] = None
            continue
        linked += 1
    repository_catalog["summary"]["linked_papers"] = linked
    repository_catalog["summary"]["repository_status"] = dict(
        sorted(
            {
                status: sum(
                    record["status"] == status for record in repository_catalog["repositories"]
                )
                for status in {record["status"] for record in repository_catalog["repositories"]}
            }.items()
        )
    )
    return linked


def write_verification_decisions(catalog: dict[str, Any], target: Path) -> Path:
    decisions: dict[str, dict[str, Any]] = {}
    for repository in catalog["repositories"]:
        if repository["status"] in {"verified", "archived"}:
            continue
        for paper_id in repository["paper_ids"]:
            decisions[paper_id] = {
                "status": repository["status"],
                "url": repository["url"],
                "reason": repository.get("verification_error")
                or "repository-not-publicly-available",
            }
    payload = {
        "schema_version": "1.0",
        "description": "Persistent exceptions from public repository verification.",
        "decisions": dict(sorted(decisions.items())),
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def build_code_gold_set(
    papers: list[dict[str, Any]], target: Path, limit: int = 100
) -> dict[str, Any]:
    examples = []
    for paper in papers:
        code_url = paper["links"].get("code")
        if not code_url:
            continue
        examples.append(
            {
                "paper_id": paper["id"],
                "title": paper["title"],
                "expected_status": "verified",
                "expected_code_url": code_url,
                "evidence_source": "official-abstract-explicit-url",
            }
        )
        if len(examples) >= limit:
            break
    gold = {
        "schema_version": "1.0",
        "id": "code-link-gold-v1",
        "description": "Deterministic positive examples with code URLs explicitly stated in official paper abstracts.",
        "examples": examples,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(gold, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return gold
