from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict
from collections.abc import Iterable
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .catalog import tokenize

DEFAULT_STORE = Path(".arl/catalog.sqlite3")
SCHEMA_VERSION = "1"


@dataclass(frozen=True)
class EvidenceHit:
    paper_id: str
    title: str
    source_url: str
    excerpt: str
    score: float
    section: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    chunk_id: str | None = None
    kind: str = "metadata"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def connect_store(path: Path = DEFAULT_STORE) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    initialize_store(connection)
    return connection


def initialize_store(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS papers (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            abstract TEXT,
            conference TEXT NOT NULL,
            year INTEGER NOT NULL,
            official_page TEXT NOT NULL,
            pdf_url TEXT,
            code_url TEXT,
            record_json TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
            paper_id UNINDEXED,
            title,
            abstract,
            tags,
            tokenize='unicode61'
        );
        CREATE TABLE IF NOT EXISTS chunks (
            paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
            chunk_id TEXT NOT NULL,
            page_start INTEGER NOT NULL,
            page_end INTEGER NOT NULL,
            section TEXT,
            kind TEXT NOT NULL,
            text TEXT NOT NULL,
            token_count INTEGER NOT NULL,
            pdf_checksum TEXT NOT NULL,
            extractor_version TEXT NOT NULL,
            PRIMARY KEY (paper_id, chunk_id)
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            paper_id UNINDEXED,
            chunk_id UNINDEXED,
            section,
            text,
            tokenize='unicode61'
        );
        CREATE TABLE IF NOT EXISTS fulltext_runs (
            paper_id TEXT PRIMARY KEY,
            pdf_path TEXT,
            pdf_checksum TEXT,
            status TEXT NOT NULL,
            error_code TEXT,
            pages INTEGER NOT NULL DEFAULT 0,
            chunks INTEGER NOT NULL DEFAULT 0,
            extractor_version TEXT,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS entities (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            name TEXT NOT NULL,
            normalized_name TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS edges (
            source_id TEXT NOT NULL,
            relation TEXT NOT NULL,
            target_id TEXT NOT NULL,
            paper_id TEXT,
            evidence_json TEXT NOT NULL DEFAULT '{}',
            PRIMARY KEY (source_id, relation, target_id, paper_id)
        );
        CREATE TABLE IF NOT EXISTS paper_vectors (
            paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
            model TEXT NOT NULL,
            dimensions INTEGER NOT NULL,
            vector BLOB NOT NULL,
            PRIMARY KEY (paper_id, model)
        );
        """
    )
    connection.execute(
        "INSERT OR REPLACE INTO metadata(key, value) VALUES('schema_version', ?)",
        (SCHEMA_VERSION,),
    )
    connection.commit()


def index_catalog(catalog: dict[str, Any], path: Path = DEFAULT_STORE) -> dict[str, int]:
    with closing(connect_store(path)) as connection:
        connection.execute("DELETE FROM papers_fts")
        for paper in catalog["papers"]:
            links = paper["links"]
            connection.execute(
                """
                INSERT INTO papers(
                    id, title, abstract, conference, year, official_page, pdf_url, code_url,
                    record_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    abstract=excluded.abstract,
                    conference=excluded.conference,
                    year=excluded.year,
                    official_page=excluded.official_page,
                    pdf_url=excluded.pdf_url,
                    code_url=excluded.code_url,
                    record_json=excluded.record_json
                """,
                (
                    paper["id"],
                    paper["title"],
                    paper.get("abstract"),
                    paper["conference"],
                    paper["year"],
                    links["official_page"],
                    links.get("resolved_pdf"),
                    links.get("code"),
                    json.dumps(paper, ensure_ascii=False),
                ),
            )
            searchable = " ".join(
                str(value)
                for value in [
                    paper.get("track") or "",
                    " ".join(paper.get("topics", [])),
                    " ".join(paper.get("tasks", [])),
                    " ".join(paper.get("agentic_components", [])),
                    " ".join(paper.get("benchmarks", [])),
                ]
                if value
            )
            connection.execute(
                "INSERT INTO papers_fts(paper_id, title, abstract, tags) VALUES (?, ?, ?, ?)",
                (paper["id"], paper["title"], paper.get("abstract") or "", searchable),
            )
        connection.execute(
            "INSERT OR REPLACE INTO metadata(key, value) VALUES('catalog_version', ?)",
            (catalog.get("catalog_version", "unknown"),),
        )
        connection.commit()
        return {
            "papers": connection.execute("SELECT COUNT(*) FROM papers").fetchone()[0],
            "chunks": connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0],
        }


def replace_paper_chunks(
    connection: sqlite3.Connection,
    paper_id: str,
    chunks: Iterable[dict[str, Any]],
) -> int:
    connection.execute("DELETE FROM chunks WHERE paper_id = ?", (paper_id,))
    connection.execute("DELETE FROM chunks_fts WHERE paper_id = ?", (paper_id,))
    count = 0
    for chunk in chunks:
        connection.execute(
            """
            INSERT INTO chunks(
                paper_id, chunk_id, page_start, page_end, section, kind, text, token_count,
                pdf_checksum, extractor_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                paper_id,
                chunk["chunk_id"],
                chunk["page_start"],
                chunk["page_end"],
                chunk.get("section"),
                chunk.get("kind", "body"),
                chunk["text"],
                chunk["token_count"],
                chunk["pdf_checksum"],
                chunk["extractor_version"],
            ),
        )
        connection.execute(
            "INSERT INTO chunks_fts(paper_id, chunk_id, section, text) VALUES (?, ?, ?, ?)",
            (paper_id, chunk["chunk_id"], chunk.get("section") or "", chunk["text"]),
        )
        count += 1
    return count


def _fts_query(query: str) -> str:
    terms = sorted(tokenize(query), key=lambda value: (-len(value), value))
    safe = [re.sub(r"[^\w.+-]", "", term, flags=re.UNICODE) for term in terms]
    return " OR ".join(f'"{term}"' for term in safe if term) or '"agent"'


def search_store(
    query: str,
    path: Path = DEFAULT_STORE,
    limit: int = 10,
    conference: str | None = None,
) -> list[EvidenceHit]:
    fts_query = _fts_query(query)
    chunk_hits: list[EvidenceHit] = []
    metadata_hits: list[EvidenceHit] = []
    with closing(connect_store(path)) as connection:
        conference_filter = "AND p.conference = ?" if conference else ""
        params: list[Any] = [fts_query]
        if conference:
            params.append(conference)
        params.append(limit * 8)
        seen_papers: set[str] = set()
        for row in connection.execute(
            f"""
            SELECT p.id, p.title, p.official_page, p.pdf_url,
                   snippet(chunks_fts, 3, '[', ']', ' … ', 28) AS excerpt,
                   bm25(chunks_fts, 0.0, 0.0, 1.0, 3.0) AS rank,
                   c.section, c.page_start, c.page_end, c.chunk_id
            FROM chunks_fts
            JOIN chunks c ON c.paper_id = chunks_fts.paper_id
                         AND c.chunk_id = chunks_fts.chunk_id
            JOIN papers p ON p.id = c.paper_id
            WHERE chunks_fts MATCH ? {conference_filter}
            ORDER BY rank
            LIMIT ?
            """,
            params,
        ):
            source_url = row["pdf_url"] or row["official_page"]
            if row["id"] in seen_papers:
                continue
            seen_papers.add(row["id"])
            if row["page_start"] and source_url:
                source_url = f"{source_url}#page={row['page_start']}"
            chunk_hits.append(
                EvidenceHit(
                    paper_id=row["id"],
                    title=row["title"],
                    source_url=source_url,
                    excerpt=row["excerpt"],
                    score=-float(row["rank"]),
                    section=row["section"],
                    page_start=row["page_start"],
                    page_end=row["page_end"],
                    chunk_id=row["chunk_id"],
                    kind="fulltext",
                )
            )
            if len(chunk_hits) >= limit * 4:
                break
        params = [fts_query]
        if conference:
            params.append(conference)
        params.append(limit * 8)
        for row in connection.execute(
            f"""
            SELECT p.id, p.title, p.official_page,
                   snippet(papers_fts, 2, '[', ']', ' … ', 28) AS excerpt,
                   bm25(papers_fts, 0.0, 8.0, 2.0, 1.0) AS rank
            FROM papers_fts
            JOIN papers p ON p.id = papers_fts.paper_id
            WHERE papers_fts MATCH ? {conference_filter}
            ORDER BY rank
            LIMIT ?
            """,
            params,
        ):
            metadata_hits.append(
                EvidenceHit(
                    paper_id=row["id"],
                    title=row["title"],
                    source_url=row["official_page"],
                    excerpt=row["excerpt"],
                    score=-float(row["rank"]),
                )
            )
    scores: defaultdict[str, float] = defaultdict(float)
    best: dict[str, EvidenceHit] = {}
    for rank, hit in enumerate(metadata_hits, 1):
        scores[hit.paper_id] += 2.0 / (60 + rank)
        best.setdefault(hit.paper_id, hit)
    for rank, hit in enumerate(chunk_hits, 1):
        scores[hit.paper_id] += 1.0 / (60 + rank)
        best[hit.paper_id] = hit
    query_tokens = tokenize(query)
    for paper_id, hit in best.items():
        scores[paper_id] += 0.03 * len(query_tokens & tokenize(hit.title))
    ranked = sorted(
        best, key=lambda paper_id: (scores[paper_id], best[paper_id].title), reverse=True
    )
    return [
        EvidenceHit(**{**best[paper_id].to_dict(), "score": scores[paper_id]})
        for paper_id in ranked[:limit]
    ]


def store_stats(path: Path = DEFAULT_STORE) -> dict[str, Any]:
    with closing(connect_store(path)) as connection:
        result = {
            "papers": connection.execute("SELECT COUNT(*) FROM papers").fetchone()[0],
            "chunks": connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0],
            "entities": connection.execute("SELECT COUNT(*) FROM entities").fetchone()[0],
            "edges": connection.execute("SELECT COUNT(*) FROM edges").fetchone()[0],
            "vectors": connection.execute("SELECT COUNT(*) FROM paper_vectors").fetchone()[0],
            "fulltext_status": dict(
                connection.execute(
                    "SELECT status, COUNT(*) FROM fulltext_runs GROUP BY status"
                ).fetchall()
            ),
        }
        return result
