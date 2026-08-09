from __future__ import annotations

import csv
import os
import re
import tomllib
from collections import Counter
from pathlib import Path

from .catalog import tokenize
from .models import Resource

LOCAL_CONFIG = "agentic-research-lab.local.toml"
MOBILE_TERMS = {
    "android",
    "ios",
    "mobile",
    "phone",
    "smartphone",
    "tablet",
    "手机",
    "移动端",
    "移动设备",
}


def _configured_manifest(config: Path | None = None) -> str:
    path = config or Path.cwd() / LOCAL_CONFIG
    if not path.is_file():
        return ""
    with path.open("rb") as stream:
        raw = tomllib.load(stream)
    return str(raw.get("corpus", {}).get("manifest", ""))


def resolve_manifest(explicit: str | None = None, config: Path | None = None) -> Path:
    value = explicit or os.environ.get("ARL_CORPUS_MANIFEST", "") or _configured_manifest(config)
    if not value:
        raise ValueError(f"pass --manifest, set ARL_CORPUS_MANIFEST, or create {LOCAL_CONFIG}")
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def optional_manifest(explicit: str | None = None, config: Path | None = None) -> Path | None:
    try:
        return resolve_manifest(explicit, config)
    except ValueError:
        return None


def corpus_stats(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    conferences = Counter(row.get("conference", "unknown") for row in rows)
    downloadable = sum(
        bool(row.get("pdf_url") or row.get("official_pdf") or row.get("arxiv_pdf")) for row in rows
    )
    return {
        "manifest": str(path),
        "papers": len(rows),
        "downloadable": downloadable,
        "conferences": dict(sorted(conferences.items())),
    }


def _resource_url(row: dict[str, str]) -> str:
    if row.get("official_page"):
        return row["official_page"]
    if row.get("arxiv_id"):
        return f"https://arxiv.org/abs/{row['arxiv_id']}"
    return row.get("pdf_url") or row.get("official_pdf") or row.get("arxiv_pdf") or ""


def _summary(row: dict[str, str]) -> str:
    abstract = re.sub(r"\s+", " ", row.get("abstract", "")).strip()
    if abstract:
        return abstract[:500]
    conference = row.get("conference", "Research")
    track = row.get("track", "agentic systems")
    return f"{conference} paper selected from {track}. Abstract is not present in the manifest."


def _is_mobile(text: str) -> bool:
    lowered = text.casefold()
    return any(term in lowered for term in MOBILE_TERMS)


def search_corpus(path: Path, query: str, limit: int = 10) -> list[Resource]:
    query_tokens = tokenize(query)
    scored: list[tuple[float, Resource]] = []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            url = _resource_url(row)
            title = row.get("title", "").strip()
            if not title or not url:
                continue
            title_tokens = tokenize(title)
            abstract_tokens = tokenize(row.get("abstract", ""))
            metadata = " ".join(
                [row.get("track", ""), row.get("selected_by", ""), row.get("conference", "")]
            )
            metadata_tokens = tokenize(metadata)
            score = (
                6 * len(query_tokens & title_tokens)
                + 2 * len(query_tokens & abstract_tokens)
                + len(query_tokens & metadata_tokens)
            )
            if query_tokens and score == 0:
                continue
            year = int(row.get("year") or 2000)
            scope = (
                "mobile" if _is_mobile(f"{title} {row.get('abstract', '')}") else "general-agentic"
            )
            resource = Resource(
                id=f"corpus-{row.get('conference', 'paper').casefold()}-{row.get('paper_id') or row.get('openreview_id') or row.get('arxiv_id') or len(scored)}",
                title=title,
                kind="paper",
                scope=scope,
                year=year,
                summary=_summary(row),
                tags=tuple(
                    filter(
                        None,
                        [
                            row.get("conference", ""),
                            row.get("track", ""),
                            row.get("selected_by", ""),
                        ],
                    )
                ),
                venue=" ".join(filter(None, [row.get("conference", ""), row.get("year", "")])),
                paper_url=url,
                status=row.get("status", "manifest"),
            )
            resource.validate()
            scored.append((score + year / 10_000, resource))
    scored.sort(key=lambda pair: (pair[0], pair[1].year, pair[1].title), reverse=True)
    return [resource for _, resource in scored[:limit]]
