from __future__ import annotations

import hashlib
import math
from array import array
from collections import defaultdict
from collections.abc import Sequence
from contextlib import closing
from pathlib import Path
from typing import Any, Protocol

from .catalog import tokenize
from .store import DEFAULT_STORE, EvidenceHit, connect_store, search_store


class EmbeddingProvider(Protocol):
    name: str
    dimensions: int

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class HashEmbeddingProvider:
    name = "hash-v1"

    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        output = []
        for text in texts:
            vector = [0.0] * self.dimensions
            for token in tokenize(text):
                digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
                value = int.from_bytes(digest)
                index = value % self.dimensions
                vector[index] += -1.0 if value & 1 else 1.0
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            output.append([value / norm for value in vector])
        return output


class SentenceTransformerProvider:
    def __init__(self, model: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "install the embeddings extra: python -m pip install -e '.[embeddings]'"
            ) from exc
        self.model_name = model
        self.name = f"sentence-transformers:{model}"
        self._model = SentenceTransformer(model)
        self.dimensions = int(self._model.get_sentence_embedding_dimension())

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = self._model.encode(list(texts), normalize_embeddings=True)
        return [vector.tolist() for vector in vectors]


def provider_from_name(name: str, model: str | None = None) -> EmbeddingProvider:
    if name == "hash":
        return HashEmbeddingProvider()
    if name == "sentence-transformers":
        return SentenceTransformerProvider(model or "sentence-transformers/all-MiniLM-L6-v2")
    raise ValueError(f"unknown embedding provider: {name}")


def _blob(vector: Sequence[float]) -> bytes:
    return array("f", vector).tobytes()


def _vector(blob: bytes) -> list[float]:
    values = array("f")
    values.frombytes(blob)
    return list(values)


def build_vector_index(
    catalog: dict[str, Any],
    store_path: Path = DEFAULT_STORE,
    provider: EmbeddingProvider | None = None,
    batch_size: int = 64,
) -> dict[str, Any]:
    provider = provider or HashEmbeddingProvider()
    papers = catalog["papers"]
    with closing(connect_store(store_path)) as connection:
        connection.execute("DELETE FROM paper_vectors WHERE model = ?", (provider.name,))
        for start in range(0, len(papers), batch_size):
            batch = papers[start : start + batch_size]
            texts = [
                f"{paper['title']}\n{paper.get('abstract') or ''}\n"
                f"{' '.join(paper.get('topics', []))} {' '.join(paper.get('agentic_components', []))}"
                for paper in batch
            ]
            vectors = provider.embed(texts)
            connection.executemany(
                "INSERT INTO paper_vectors(paper_id, model, dimensions, vector) VALUES (?, ?, ?, ?)",
                [
                    (paper["id"], provider.name, provider.dimensions, _blob(vector))
                    for paper, vector in zip(batch, vectors, strict=True)
                ],
            )
        connection.commit()
    return {"papers": len(papers), "model": provider.name, "dimensions": provider.dimensions}


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def vector_search(
    query: str,
    store_path: Path = DEFAULT_STORE,
    provider: EmbeddingProvider | None = None,
    limit: int = 10,
    conference: str | None = None,
) -> list[EvidenceHit]:
    provider = provider or HashEmbeddingProvider()
    query_vector = provider.embed([query])[0]
    params: list[Any] = [provider.name]
    conference_filter = "AND p.conference = ?" if conference else ""
    if conference:
        params.append(conference)
    results = []
    with closing(connect_store(store_path)) as connection:
        rows = connection.execute(
            f"""
            SELECT p.id, p.title, p.abstract, p.official_page, v.vector
            FROM paper_vectors v JOIN papers p ON p.id = v.paper_id
            WHERE v.model = ? {conference_filter}
            """,
            params,
        )
        for row in rows:
            score = _cosine(query_vector, _vector(row["vector"]))
            results.append(
                EvidenceHit(
                    paper_id=row["id"],
                    title=row["title"],
                    source_url=row["official_page"],
                    excerpt=(row["abstract"] or "")[:500],
                    score=score,
                    kind="vector",
                )
            )
    results.sort(key=lambda hit: (hit.score, hit.title), reverse=True)
    return results[:limit]


def hybrid_search(
    query: str,
    store_path: Path = DEFAULT_STORE,
    provider: EmbeddingProvider | None = None,
    limit: int = 10,
    conference: str | None = None,
) -> list[EvidenceHit]:
    provider = provider or HashEmbeddingProvider()
    lexical = search_store(query, store_path, limit * 3, conference)
    semantic = vector_search(query, store_path, provider, limit * 3, conference)
    scores: defaultdict[str, float] = defaultdict(float)
    best: dict[str, EvidenceHit] = {}
    for rank, hit in enumerate(lexical, 1):
        scores[hit.paper_id] += 2.0 / (60 + rank)
        best[hit.paper_id] = hit
    for rank, hit in enumerate(semantic, 1):
        scores[hit.paper_id] += 1.0 / (60 + rank)
        best.setdefault(hit.paper_id, hit)
    ranked = sorted(best, key=lambda paper_id: scores[paper_id], reverse=True)
    return [
        EvidenceHit(**{**best[paper_id].to_dict(), "score": scores[paper_id]})
        for paper_id in ranked[:limit]
    ]
