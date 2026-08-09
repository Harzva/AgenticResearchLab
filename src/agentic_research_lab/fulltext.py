from __future__ import annotations

import csv
import hashlib
import re
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .store import DEFAULT_STORE, connect_store, replace_paper_chunks

EXTRACTOR_VERSION = "pymupdf-page-chunks-v1"
SECTION_RE = re.compile(
    r"^(?:\d+(?:\.\d+)*\s+)?(abstract|introduction|related work|background|method(?:ology)?|"
    r"approach|experiments?|evaluation|results?|discussion|limitations?|conclusion|references|"
    r"appendix)\b",
    re.IGNORECASE,
)


class MissingFulltextDependency(RuntimeError):
    pass


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _section(text: str, previous: str | None) -> str | None:
    for line in text.splitlines()[:8]:
        line = re.sub(r"\s+", " ", line).strip()
        match = SECTION_RE.match(line)
        if match:
            return match.group(1).casefold()
    return previous


def _split_page(text: str, max_chars: int = 4000, overlap: int = 350) -> list[str]:
    cleaned = re.sub(r"[ \t]+", " ", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    if not cleaned:
        return []
    chunks = []
    start = 0
    while start < len(cleaned):
        end = min(start + max_chars, len(cleaned))
        if end < len(cleaned):
            boundary = max(cleaned.rfind("\n", start, end), cleaned.rfind(". ", start, end))
            if boundary > start + max_chars // 2:
                end = boundary + 1
        chunks.append(cleaned[start:end].strip())
        if end >= len(cleaned):
            break
        start = max(end - overlap, start + 1)
    return [chunk for chunk in chunks if chunk]


def extract_pdf_chunks(pdf_path: Path, paper_id: str) -> tuple[list[dict[str, Any]], int, str]:
    try:
        import pymupdf
    except ImportError as exc:
        raise MissingFulltextDependency(
            "install the fulltext extra: python -m pip install -e '.[fulltext]'"
        ) from exc
    checksum = file_sha256(pdf_path)
    chunks: list[dict[str, Any]] = []
    current_section: str | None = None
    with pymupdf.open(pdf_path) as document:
        for page_index, page in enumerate(document):
            text = page.get_text("text")
            current_section = _section(text, current_section)
            for chunk_index, content in enumerate(_split_page(text)):
                chunks.append(
                    {
                        "chunk_id": f"{paper_id}-p{page_index + 1:04d}-c{chunk_index + 1:02d}",
                        "page_start": page_index + 1,
                        "page_end": page_index + 1,
                        "section": current_section,
                        "kind": "body",
                        "text": content,
                        "token_count": len(content.split()),
                        "pdf_checksum": checksum,
                        "extractor_version": EXTRACTOR_VERSION,
                    }
                )
        return chunks, len(document), checksum


def local_pdf_records(manifest: Path) -> list[tuple[str, Path]]:
    base = manifest.parent.resolve()
    records: list[tuple[str, Path]] = []
    with manifest.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            relative = (row.get("downloaded_path") or "").strip()
            if not relative:
                continue
            pdf_path = (base / relative).resolve()
            if base not in pdf_path.parents or not pdf_path.is_file():
                continue
            conference = (row.get("conference") or "paper").casefold()
            year = row.get("year") or "unknown"
            source_id = row.get("paper_id") or row.get("openreview_id") or row.get("arxiv_id")
            source_id = re.sub(r"[^a-zA-Z0-9._-]+", "-", source_id or "").strip("-")
            records.append((f"{conference}-{year}-{source_id}", pdf_path))
    return records


def build_fulltext_index(
    manifest: Path,
    store_path: Path = DEFAULT_STORE,
    *,
    limit: int | None = None,
    missing_only: bool = False,
) -> dict[str, Any]:
    records = local_pdf_records(manifest)
    if limit is not None:
        records = records[:limit]
    summary = {"requested": len(records), "indexed": 0, "skipped": 0, "failed": 0, "chunks": 0}
    with closing(connect_store(store_path)) as connection:
        for paper_id, pdf_path in records:
            if missing_only:
                existing = connection.execute(
                    "SELECT status FROM fulltext_runs WHERE paper_id = ?", (paper_id,)
                ).fetchone()
                if existing and existing["status"] == "indexed":
                    summary["skipped"] += 1
                    continue
            now = datetime.now(UTC).replace(microsecond=0).isoformat()
            try:
                chunks, pages, checksum = extract_pdf_chunks(pdf_path, paper_id)
                if not chunks:
                    raise ValueError("empty-pdf-text")
                chunk_count = replace_paper_chunks(connection, paper_id, chunks)
                connection.execute(
                    """
                    INSERT OR REPLACE INTO fulltext_runs(
                        paper_id, pdf_path, pdf_checksum, status, error_code, pages, chunks,
                        extractor_version, updated_at
                    ) VALUES (?, ?, ?, 'indexed', NULL, ?, ?, ?, ?)
                    """,
                    (
                        paper_id,
                        str(pdf_path),
                        checksum,
                        pages,
                        chunk_count,
                        EXTRACTOR_VERSION,
                        now,
                    ),
                )
                summary["indexed"] += 1
                summary["chunks"] += chunk_count
            except MissingFulltextDependency:
                raise
            except (OSError, RuntimeError, ValueError) as exc:
                error_code = type(exc).__name__.casefold()
                connection.execute(
                    """
                    INSERT OR REPLACE INTO fulltext_runs(
                        paper_id, pdf_path, status, error_code, pages, chunks, updated_at
                    ) VALUES (?, ?, 'failed', ?, 0, 0, ?)
                    """,
                    (paper_id, str(pdf_path), error_code, now),
                )
                summary["failed"] += 1
            connection.commit()
    return summary
