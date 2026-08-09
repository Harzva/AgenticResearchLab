from __future__ import annotations

import json
import math
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from .paper_catalog import load_public_catalog
from .proposals import build_proposal_bundle, reject_proposal
from .store import DEFAULT_STORE, index_catalog, search_store

STOPWORDS = {
    "agent",
    "agents",
    "agentic",
    "large",
    "language",
    "model",
    "models",
    "using",
    "with",
    "for",
    "from",
    "towards",
    "toward",
    "the",
    "and",
}


def build_retrieval_gold(catalog: dict[str, Any], target: Path, limit: int = 100) -> dict[str, Any]:
    examples = []
    for paper in catalog["papers"]:
        signals = (
            paper.get("topics", [])
            + paper.get("agentic_components", [])
            + paper.get("environments", [])
            + paper.get("failure_modes", [])
        )
        words = [
            word.casefold()
            for word in re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}", paper["title"])
            if word.casefold() not in STOPWORDS
        ]
        query_terms = list(dict.fromkeys([*signals[:3], *words[:3]]))
        if len(query_terms) < 3 or not paper.get("abstract"):
            continue
        examples.append(
            {
                "id": f"retrieval-{len(examples) + 1:03d}",
                "query": " ".join(query_terms),
                "relevant_paper_ids": [paper["id"]],
                "source": "taxonomy-plus-title-sanity-query",
            }
        )
        if len(examples) >= limit:
            break
    gold = {
        "schema_version": "1.0",
        "id": "retrieval-smoke-gold-v1",
        "description": (
            "A deterministic 100-query retrieval regression set. It is a smoke benchmark, "
            "not a substitute for the planned human-authored semantic research-query set."
        ),
        "examples": examples,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(gold, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return gold


def evaluate_code_links(catalog: dict[str, Any], gold_path: Path) -> dict[str, Any]:
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    papers = {paper["id"]: paper for paper in catalog["papers"]}
    correct = 0
    false_positive = 0
    missing = 0
    for example in gold["examples"]:
        paper = papers.get(example["paper_id"])
        actual = paper["links"].get("code") if paper else None
        if actual == example["expected_code_url"]:
            correct += 1
        elif actual:
            false_positive += 1
        else:
            missing += 1
    predicted = correct + false_positive
    return {
        "examples": len(gold["examples"]),
        "correct": correct,
        "false_positive": false_positive,
        "missing": missing,
        "precision": correct / predicted if predicted else 0.0,
        "recall": correct / len(gold["examples"]) if gold["examples"] else 0.0,
        "passed": false_positive == 0 and missing == 0,
    }


def _evaluate_retrieval_with_store(
    gold: dict[str, Any], store_path: Path, k: int
) -> dict[str, Any]:
    recall_total = 0.0
    reciprocal_rank = 0.0
    ndcg_total = 0.0
    for example in gold["examples"]:
        expected = set(example["relevant_paper_ids"])
        result_ids = [hit.paper_id for hit in search_store(example["query"], store_path, k)]
        result_ids = list(dict.fromkeys(result_ids))
        matched = expected & set(result_ids)
        recall_total += len(matched) / len(expected)
        ranks = [result_ids.index(paper_id) + 1 for paper_id in matched]
        if ranks:
            best_rank = min(ranks)
            reciprocal_rank += 1 / best_rank
            ndcg_total += 1 / math.log2(best_rank + 1)
    count = len(gold["examples"])
    return {
        "examples": count,
        "k": k,
        "recall_at_k": recall_total / count if count else 0.0,
        "mrr": reciprocal_rank / count if count else 0.0,
        "ndcg_at_k": ndcg_total / count if count else 0.0,
    }


def evaluate_retrieval(
    catalog: dict[str, Any], gold_path: Path, store_path: Path = DEFAULT_STORE, k: int = 20
) -> dict[str, Any]:
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    if store_path.is_file():
        result = _evaluate_retrieval_with_store(gold, store_path, k)
    else:
        with TemporaryDirectory() as directory:
            temporary = Path(directory) / "catalog.sqlite3"
            index_catalog(catalog, temporary)
            result = _evaluate_retrieval_with_store(gold, temporary, k)
    result["passed"] = result["recall_at_k"] >= 0.85 and result["ndcg_at_k"] >= 0.75
    return result


def evaluate_proposals(catalog: dict[str, Any], store_path: Path = DEFAULT_STORE) -> dict[str, Any]:
    subjects = [
        "privacy-aware mobile agent with long-term memory",
        "safe GUI agent under environmental injection",
        "efficient device cloud routing for mobile agents",
        "self-evolving coding agent with verified memory",
        "multi-agent scientific workflow with independent verification",
        "web agent recovery under dynamic page changes",
        "personalized assistant with permission-aware tool use",
        "long-horizon embodied planning with world models",
        "agent benchmark with process-level success verifiers",
        "cost-aware multi-agent collaboration under equal inference budget",
    ]
    results = []
    for subject in subjects:
        bundle = build_proposal_bundle(subject, catalog=catalog, store_path=store_path, top_k=5)
        statuses = [reject_proposal(proposal) for proposal in bundle["candidates"]]
        results.append(
            {
                "subject": subject,
                "candidates": len(statuses),
                "passed": sum(status["status"] == "pass" for status in statuses),
                "evidence": len(bundle["nearest_work"]),
            }
        )
    passed = all(
        result["passed"] == result["candidates"] and result["evidence"] >= 3 for result in results
    )
    return {"subjects": len(subjects), "passed": passed, "results": results}


def evaluate_all(
    *,
    catalog_path: Path | None = None,
    code_gold: Path = Path("evals/code_link_gold_v1.json"),
    retrieval_gold: Path = Path("evals/retrieval_gold_v1.json"),
    store_path: Path = DEFAULT_STORE,
) -> dict[str, Any]:
    catalog = load_public_catalog(catalog_path)
    result = {
        "code_links": evaluate_code_links(catalog, code_gold),
        "retrieval": evaluate_retrieval(catalog, retrieval_gold, store_path),
        "proposals": evaluate_proposals(catalog, store_path),
    }
    result["passed"] = all(value.get("passed") for value in result.values())
    return result


def write_metrics(metrics: dict[str, Any], target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target
