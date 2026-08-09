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

EVALUATION_SET_SCHEMA_VERSION = "1.0"
EVALUATION_SUITE_SCHEMA_VERSION = "1.0"
EVALUATION_REPORT_SCHEMA_VERSION = "1.0"
DEFAULT_SMOKE_SUITE = Path("evals/suites/smoke-v1.json")
DEFAULT_HUMAN_SUITE = Path("evals/suites/human-v1.draft.json")
SUITE_ALIASES = {"smoke": DEFAULT_SMOKE_SUITE, "human": DEFAULT_HUMAN_SUITE}

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
    error_categories = {"no_relevant_in_top_k": 0, "partial_recall": 0}
    slices: dict[str, dict[str, float]] = {}
    for example in gold["examples"]:
        expected = set(example["relevant_paper_ids"])
        result_ids = [hit.paper_id for hit in search_store(example["query"], store_path, k)]
        result_ids = list(dict.fromkeys(result_ids))
        matched = expected & set(result_ids)
        example_recall = len(matched) / len(expected)
        recall_total += example_recall
        if not matched:
            error_categories["no_relevant_in_top_k"] += 1
        elif example_recall < 1.0:
            error_categories["partial_recall"] += 1
        ranks = [result_ids.index(paper_id) + 1 for paper_id in matched]
        language = example.get("language", "unspecified")
        language_slice = slices.setdefault(language, {"examples": 0, "recall_total": 0.0})
        language_slice["examples"] += 1
        language_slice["recall_total"] += example_recall
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
        "error_categories": error_categories,
        "slices": {
            key: {
                "examples": int(value["examples"]),
                "recall_at_k": value["recall_total"] / value["examples"],
            }
            for key, value in slices.items()
        },
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


def resolve_evaluation_suite(value: str | Path) -> Path:
    key = str(value)
    return SUITE_ALIASES.get(key, Path(key))


def _catalog_identity(catalog: dict[str, Any]) -> dict[str, Any]:
    source = catalog.get("source", {})
    return {
        "id": catalog["id"],
        "catalog_version": catalog["catalog_version"],
        "schema_version": catalog["schema_version"],
        "source_sha256": source.get("sha256"),
        "papers": catalog.get("summary", {}).get("papers", len(catalog.get("papers", []))),
    }


def _write_json(value: dict[str, Any], target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def _balanced_fulltext_seed(catalog: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    by_conference: dict[str, list[dict[str, Any]]] = {}
    for paper in catalog["papers"]:
        if paper.get("links", {}).get("resolved_pdf"):
            by_conference.setdefault(paper["conference"], []).append(paper)
    examples: list[dict[str, Any]] = []
    offsets = {conference: 0 for conference in by_conference}
    conferences = sorted(by_conference)
    while len(examples) < limit:
        advanced = False
        for conference in conferences:
            offset = offsets[conference]
            papers = by_conference[conference]
            if offset >= len(papers):
                continue
            paper = papers[offset]
            offsets[conference] += 1
            advanced = True
            examples.append(
                {
                    "id": f"fulltext-{len(examples) + 1:03d}",
                    "paper_id": paper["id"],
                    "title": paper["title"],
                    "conference": conference,
                    "source_url": paper["links"]["resolved_pdf"],
                    "page_start": None,
                    "page_end": None,
                    "chunk_id": None,
                    "extraction_success": None,
                    "title_correct": None,
                    "page_correct": None,
                    "chunk_boundary_correct": None,
                    "error_category": None,
                    "annotations": [],
                    "adjudication": {"status": "pending", "decision": None, "notes": None},
                }
            )
            if len(examples) >= limit:
                break
        if not advanced:
            break
    return examples


def build_human_evaluation_scaffold(
    catalog: dict[str, Any], target_root: Path, *, fulltext_limit: int = 100, force: bool = False
) -> list[Path]:
    identity = _catalog_identity(catalog)
    human_dir = target_root / "human"
    suite_dir = target_root / "suites"
    targets = [
        human_dir / "fulltext_quality_v1.draft.json",
        human_dir / "semantic_retrieval_v1.draft.json",
        human_dir / "citation_quality_v1.draft.json",
        suite_dir / "human-v1.draft.json",
    ]
    existing = [path for path in targets if path.exists()]
    if existing and not force:
        raise FileExistsError(
            "refusing to replace evaluation drafts: " + ", ".join(str(path) for path in existing)
        )

    policy = {
        "required_annotators": 2,
        "adjudication_required": True,
        "blind_independent_pass": True,
    }
    provenance = {
        "corpus": identity,
        "status": "unreviewed",
        "note": "Generated structure and candidates are not human Gold labels.",
    }
    fulltext = {
        "schema_version": EVALUATION_SET_SCHEMA_VERSION,
        "id": "fulltext-quality-human-v1-draft",
        "version": "0.1.0-draft",
        "task": "fulltext-quality",
        "review_status": "draft",
        "minimum_examples": 100,
        "annotation_policy": policy,
        "provenance": {
            **provenance,
            "method": "deterministic-balanced-public-catalog-seed",
        },
        "examples": _balanced_fulltext_seed(catalog, fulltext_limit),
    }
    retrieval = {
        "schema_version": EVALUATION_SET_SCHEMA_VERSION,
        "id": "semantic-retrieval-human-v1-draft",
        "version": "0.1.0-draft",
        "task": "semantic-retrieval",
        "review_status": "draft",
        "minimum_examples": 120,
        "annotation_policy": policy,
        "provenance": {
            **provenance,
            "method": "maintainer-authored-bilingual-queries-required",
        },
        "examples": [],
    }
    citation = {
        "schema_version": EVALUATION_SET_SCHEMA_VERSION,
        "id": "citation-quality-human-v1-draft",
        "version": "0.1.0-draft",
        "task": "citation-quality",
        "review_status": "draft",
        "minimum_examples": 100,
        "annotation_policy": policy,
        "provenance": {
            **provenance,
            "method": "maintainer-authored-claim-evidence-triples-required",
        },
        "examples": [],
    }
    suite = {
        "schema_version": EVALUATION_SUITE_SCHEMA_VERSION,
        "id": "human-gold-v1-draft",
        "version": "0.1.0-draft",
        "title": "Human evaluation gate draft",
        "tier": "manual",
        "review_status": "draft",
        "description": (
            "Annotation-ready scaffolds for ARL-401/402/403. This suite is structurally valid "
            "but blocked until independent human review and adjudication are complete."
        ),
        "corpus": identity,
        "evaluations": [
            {
                "id": "fulltext-quality-human",
                "task": "fulltext-quality",
                "dataset": "../human/fulltext_quality_v1.draft.json",
                "thresholds": {
                    "extraction_success_rate": 0.98,
                    "title_accuracy": 0.98,
                    "page_accuracy": 0.95,
                    "chunk_boundary_accuracy": 0.95,
                },
            },
            {
                "id": "semantic-retrieval-human",
                "task": "semantic-retrieval",
                "dataset": "../human/semantic_retrieval_v1.draft.json",
                "configuration": {"k": 20},
                "thresholds": {"recall_at_k": 0.85, "ndcg_at_k": 0.75},
            },
            {
                "id": "citation-quality-human",
                "task": "citation-quality",
                "dataset": "../human/citation_quality_v1.draft.json",
                "thresholds": {"paper_accuracy": 0.98, "page_accuracy": 0.95},
            },
        ],
    }
    for value, target in zip((fulltext, retrieval, citation, suite), targets, strict=True):
        _write_json(value, target)
    return targets


TASK_REQUIRED_FIELDS = {
    "fulltext-quality": {
        "paper_id",
        "source_url",
        "extraction_success",
        "title_correct",
        "page_correct",
        "chunk_boundary_correct",
    },
    "semantic-retrieval": {
        "query",
        "language",
        "relevant_paper_ids",
        "difficulty",
        "phenomena",
    },
    "citation-quality": {
        "query",
        "claim",
        "cited_paper_id",
        "cited_pages",
        "paper_correct",
        "page_correct",
        "support_label",
    },
}


def _human_judgments_complete(task: str, example: dict[str, Any]) -> bool:
    required = TASK_REQUIRED_FIELDS.get(task, set())
    if not all(example.get(field) is not None for field in required):
        return False
    if task == "semantic-retrieval":
        return (
            example.get("language") in {"zh", "en", "zh-to-en", "en-to-zh"}
            and example.get("difficulty") in {"easy", "medium", "hard"}
            and isinstance(example.get("relevant_paper_ids"), list)
            and bool(example["relevant_paper_ids"])
            and isinstance(example.get("phenomena"), list)
            and bool(example["phenomena"])
        )
    if task == "citation-quality":
        return (
            example.get("support_label") in {"support", "partial", "not-support"}
            and isinstance(example.get("cited_pages"), list)
            and bool(example["cited_pages"])
        )
    return True


def validate_evaluation_set(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"path": str(path), "valid": False, "gate_ready": False, "errors": [str(exc)]}
    required = {
        "schema_version",
        "id",
        "version",
        "task",
        "review_status",
        "minimum_examples",
        "annotation_policy",
        "provenance",
        "examples",
    }
    missing = sorted(required - set(data))
    if missing:
        errors.append("missing fields: " + ", ".join(missing))
    if data.get("schema_version") != EVALUATION_SET_SCHEMA_VERSION:
        errors.append(f"unsupported schema_version: {data.get('schema_version')!r}")
    task = data.get("task")
    if task not in TASK_REQUIRED_FIELDS:
        errors.append(f"unsupported human evaluation task: {task!r}")
    if data.get("review_status") not in {"draft", "reviewed"}:
        errors.append("review_status must be draft or reviewed")
    examples = data.get("examples")
    if not isinstance(examples, list):
        errors.append("examples must be an array")
        examples = []
    policy = data.get("annotation_policy", {})
    required_annotators = policy.get("required_annotators", 0)
    if not isinstance(required_annotators, int) or required_annotators < 2:
        errors.append("annotation_policy.required_annotators must be at least 2")
        required_annotators = 2
    minimum_examples = data.get("minimum_examples", 0)
    if not isinstance(minimum_examples, int) or minimum_examples < 1:
        errors.append("minimum_examples must be a positive integer")
        minimum_examples = 1

    reviewed = 0
    incomplete = 0
    seen_ids: set[str] = set()
    task_fields = TASK_REQUIRED_FIELDS.get(task, set())
    for index, example in enumerate(examples):
        if not isinstance(example, dict):
            errors.append(f"examples[{index}] must be an object")
            continue
        example_id = example.get("id")
        if not example_id:
            errors.append(f"examples[{index}] is missing id")
        elif example_id in seen_ids:
            errors.append(f"duplicate example id: {example_id}")
        else:
            seen_ids.add(example_id)
        missing_example = sorted(task_fields - set(example))
        if missing_example:
            errors.append(f"examples[{index}] missing task fields: " + ", ".join(missing_example))
        annotations = example.get("annotations", [])
        adjudication = example.get("adjudication", {})
        if not isinstance(annotations, list):
            errors.append(f"examples[{index}].annotations must be an array")
            annotations = []
        if not isinstance(adjudication, dict):
            errors.append(f"examples[{index}].adjudication must be an object")
            adjudication = {}
        resolved = adjudication.get("status") == "resolved"
        independent_annotators = {
            annotation.get("annotator_id")
            for annotation in annotations
            if isinstance(annotation, dict)
            and annotation.get("annotator_id")
            and isinstance(annotation.get("labels"), dict)
            and annotation["labels"]
        }
        judgments_complete = _human_judgments_complete(task, example)
        adjudication_complete = resolved and isinstance(adjudication.get("decision"), dict)
        if (
            adjudication_complete
            and len(independent_annotators) >= required_annotators
            and judgments_complete
        ):
            reviewed += 1
        else:
            incomplete += 1

    provenance_status = data.get("provenance", {}).get("status")
    gate_ready = (
        not errors
        and data.get("review_status") == "reviewed"
        and provenance_status == "reviewed"
        and reviewed >= minimum_examples
        and incomplete == 0
    )
    readiness_reasons = []
    if data.get("review_status") != "reviewed":
        readiness_reasons.append("dataset review_status is not reviewed")
    if provenance_status != "reviewed":
        readiness_reasons.append("dataset provenance status is not reviewed")
    if reviewed < minimum_examples:
        readiness_reasons.append(f"reviewed examples {reviewed}/{minimum_examples}")
    if incomplete:
        readiness_reasons.append(f"examples awaiting complete adjudication: {incomplete}")
    return {
        "path": str(path),
        "id": data.get("id"),
        "task": task,
        "version": data.get("version"),
        "review_status": data.get("review_status"),
        "corpus": data.get("provenance", {}).get("corpus"),
        "examples": len(examples),
        "reviewed_examples": reviewed,
        "valid": not errors,
        "gate_ready": gate_ready,
        "errors": errors,
        "readiness_reasons": readiness_reasons,
    }


def validate_evaluation_suite(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        suite = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"path": str(path), "valid": False, "gate_ready": False, "errors": [str(exc)]}
    required = {
        "schema_version",
        "id",
        "version",
        "title",
        "tier",
        "review_status",
        "corpus",
        "evaluations",
    }
    missing = sorted(required - set(suite))
    if missing:
        errors.append("missing fields: " + ", ".join(missing))
    if suite.get("schema_version") != EVALUATION_SUITE_SCHEMA_VERSION:
        errors.append(f"unsupported schema_version: {suite.get('schema_version')!r}")
    if suite.get("tier") not in {"required", "scheduled", "manual"}:
        errors.append("tier must be required, scheduled, or manual")
    if suite.get("review_status") not in {"automated", "draft", "reviewed"}:
        errors.append("review_status must be automated, draft, or reviewed")
    corpus = suite.get("corpus", {})
    for field in ("id", "catalog_version", "schema_version", "source_sha256"):
        if not corpus.get(field):
            errors.append(f"corpus.{field} is required")
    evaluations = suite.get("evaluations")
    if not isinstance(evaluations, list) or not evaluations:
        errors.append("evaluations must be a non-empty array")
        evaluations = []
    dataset_results = []
    seen_ids: set[str] = set()
    for index, evaluation in enumerate(evaluations):
        if not isinstance(evaluation, dict):
            errors.append(f"evaluations[{index}] must be an object")
            continue
        evaluation_id = evaluation.get("id")
        if not evaluation_id:
            errors.append(f"evaluations[{index}] is missing id")
        elif evaluation_id in seen_ids:
            errors.append(f"duplicate evaluation id: {evaluation_id}")
        else:
            seen_ids.add(evaluation_id)
        task = evaluation.get("task")
        if task not in {
            "code-links",
            "retrieval-smoke",
            "proposal-regression",
            *TASK_REQUIRED_FIELDS,
        }:
            errors.append(f"evaluations[{index}] has unsupported task: {task!r}")
        dataset = evaluation.get("dataset")
        if dataset:
            dataset_path = (path.parent / dataset).resolve()
            if not dataset_path.is_file():
                errors.append(f"evaluation dataset does not exist: {dataset}")
            elif task in TASK_REQUIRED_FIELDS:
                dataset_result = validate_evaluation_set(dataset_path)
                dataset_result["path"] = dataset
                dataset_results.append(dataset_result)
                if dataset_result.get("task") != task:
                    errors.append(
                        f"{evaluation_id}: dataset task {dataset_result.get('task')!r} "
                        f"does not match {task!r}"
                    )
                if dataset_result.get("corpus") != corpus:
                    errors.append(f"{evaluation_id}: dataset corpus does not match suite corpus")
                if not dataset_result["valid"]:
                    errors.extend(
                        f"{evaluation_id}: {message}" for message in dataset_result["errors"]
                    )
        elif task != "proposal-regression":
            errors.append(f"evaluations[{index}] requires dataset")

    human_ready = all(result["gate_ready"] for result in dataset_results)
    status_ready = suite.get("review_status") in {"automated", "reviewed"}
    gate_ready = not errors and status_ready and human_ready
    readiness_reasons = []
    if not status_ready:
        readiness_reasons.append("suite review_status is not automated or reviewed")
    for result in dataset_results:
        if not result["gate_ready"]:
            readiness_reasons.extend(
                f"{result['id']}: {reason}" for reason in result["readiness_reasons"]
            )
    return {
        "path": str(path),
        "id": suite.get("id"),
        "version": suite.get("version"),
        "tier": suite.get("tier"),
        "review_status": suite.get("review_status"),
        "valid": not errors,
        "gate_ready": gate_ready,
        "errors": errors,
        "readiness_reasons": readiness_reasons,
        "datasets": dataset_results,
    }


def _meets_thresholds(metrics: dict[str, Any], thresholds: dict[str, Any]) -> bool:
    return all(
        isinstance(metrics.get(metric), (int, float)) and metrics[metric] >= minimum
        for metric, minimum in thresholds.items()
    )


def _evaluate_fulltext_quality(gold: dict[str, Any]) -> dict[str, Any]:
    examples = gold["examples"]
    count = len(examples)
    extraction = sum(example["extraction_success"] is True for example in examples)
    title_correct = sum(example["title_correct"] is True for example in examples)
    page_correct = sum(example["page_correct"] is True for example in examples)
    chunk_correct = sum(example["chunk_boundary_correct"] is True for example in examples)
    errors: dict[str, int] = {}
    for example in examples:
        category = example.get("error_category")
        if category:
            errors[category] = errors.get(category, 0) + 1
    return {
        "examples": count,
        "extraction_success_rate": extraction / count if count else 0.0,
        "title_accuracy": title_correct / count if count else 0.0,
        "page_accuracy": page_correct / count if count else 0.0,
        "chunk_boundary_accuracy": chunk_correct / count if count else 0.0,
        "error_categories": errors,
    }


def _evaluate_citation_quality(gold: dict[str, Any]) -> dict[str, Any]:
    examples = gold["examples"]
    count = len(examples)
    paper_correct = sum(example["paper_correct"] is True for example in examples)
    page_correct = sum(example["page_correct"] is True for example in examples)
    support_labels: dict[str, int] = {}
    for example in examples:
        label = example["support_label"]
        support_labels[label] = support_labels.get(label, 0) + 1
    return {
        "examples": count,
        "paper_accuracy": paper_correct / count if count else 0.0,
        "page_accuracy": page_correct / count if count else 0.0,
        "support_labels": support_labels,
    }


def _numeric_metrics(value: Any, prefix: str = "") -> dict[str, float]:
    flattened: dict[str, float] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else key
            flattened.update(_numeric_metrics(child, path))
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        flattened[prefix] = float(value)
    return flattened


def compare_evaluation_reports(current: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    current_metrics = _numeric_metrics(current.get("evaluations", {}))
    baseline_metrics = _numeric_metrics(baseline.get("evaluations", {}))
    shared = sorted(current_metrics.keys() & baseline_metrics.keys())
    return {
        "report_id": baseline.get("id"),
        "suite_id": baseline.get("evaluation_suite", {}).get("id"),
        "metrics": {
            key: {
                "baseline": baseline_metrics[key],
                "current": current_metrics[key],
                "delta": current_metrics[key] - baseline_metrics[key],
            }
            for key in shared
        },
    }


def evaluate_suite(
    suite_path: Path,
    *,
    catalog_path: Path | None = None,
    store_path: Path = DEFAULT_STORE,
    baseline_path: Path | None = None,
) -> dict[str, Any]:
    suite_path = resolve_evaluation_suite(suite_path)
    validation = validate_evaluation_suite(suite_path)
    if not validation["valid"]:
        raise ValueError("invalid evaluation suite: " + "; ".join(validation["errors"]))
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    catalog = load_public_catalog(catalog_path)
    identity = _catalog_identity(catalog)
    if suite["corpus"] != identity:
        raise ValueError(
            "evaluation suite corpus does not match the loaded catalog; rebuild or migrate the suite"
        )
    report: dict[str, Any] = {
        "report_schema_version": EVALUATION_REPORT_SCHEMA_VERSION,
        "id": f"{suite['id']}-report",
        "evaluation_suite": {
            "id": suite["id"],
            "version": suite["version"],
            "tier": suite["tier"],
            "review_status": suite["review_status"],
        },
        "corpus": identity,
        "configuration": {
            "offline_capable": True,
            "store_mode": "existing-local-index" if store_path.is_file() else "temporary-index",
        },
        "evaluations": {},
        "summary": {"status": "blocked", "passed": False, "blocked": True},
        "passed": False,
    }
    if not validation["gate_ready"]:
        report["summary"]["blocked_reasons"] = validation["readiness_reasons"]
        report["validation"] = validation
        return report

    for evaluation in suite["evaluations"]:
        task = evaluation["task"]
        dataset_path = (
            (suite_path.parent / evaluation["dataset"]).resolve()
            if evaluation.get("dataset")
            else None
        )
        if task == "code-links":
            metrics = evaluate_code_links(catalog, dataset_path)
        elif task in {"retrieval-smoke", "semantic-retrieval"}:
            k = evaluation.get("configuration", {}).get("k", 20)
            metrics = evaluate_retrieval(catalog, dataset_path, store_path, k)
        elif task == "proposal-regression":
            metrics = evaluate_proposals(catalog, store_path)
        else:
            gold = json.loads(dataset_path.read_text(encoding="utf-8"))
            metrics = (
                _evaluate_fulltext_quality(gold)
                if task == "fulltext-quality"
                else _evaluate_citation_quality(gold)
            )
        thresholds = evaluation.get("thresholds", {})
        if thresholds:
            metrics["passed"] = _meets_thresholds(metrics, thresholds)
        metrics["task"] = task
        dataset = json.loads(dataset_path.read_text(encoding="utf-8")) if dataset_path else {}
        metrics["dataset_version"] = dataset.get(
            "version", dataset.get("schema_version", "built-in-v1")
        )
        metrics["thresholds"] = thresholds
        report["evaluations"][evaluation["id"]] = metrics

    passed = all(result.get("passed") is True for result in report["evaluations"].values())
    report["summary"] = {
        "status": "passed" if passed else "failed",
        "passed": passed,
        "blocked": False,
        "evaluations": len(report["evaluations"]),
        "passed_evaluations": sum(
            result.get("passed") is True for result in report["evaluations"].values()
        ),
    }
    report["passed"] = passed
    if baseline_path:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        report["baseline_comparison"] = compare_evaluation_reports(report, baseline)
    return report


def render_evaluation_markdown(report: dict[str, Any]) -> str:
    suite = report["evaluation_suite"]
    corpus = report["corpus"]
    summary = report["summary"]
    lines = [
        f"# Evaluation report: {suite['id']}",
        "",
        f"- Suite version: `{suite['version']}`",
        f"- Tier: `{suite['tier']}`",
        f"- Review status: `{suite['review_status']}`",
        f"- Corpus: `{corpus['id']}` / `{corpus['catalog_version']}`",
        f"- Source checksum: `{corpus['source_sha256']}`",
        f"- Status: **{summary['status'].upper()}**",
        "",
    ]
    if summary.get("blocked_reasons"):
        lines.extend(["## Blocked reasons", ""])
        lines.extend(f"- {reason}" for reason in summary["blocked_reasons"])
        lines.append("")
    if report["evaluations"]:
        lines.extend(
            [
                "## Evaluation gates",
                "",
                "| Evaluation | Task | Examples | Result |",
                "| --- | --- | ---: | --- |",
            ]
        )
        for evaluation_id, metrics in report["evaluations"].items():
            status = "PASS" if metrics.get("passed") else "FAIL"
            lines.append(
                f"| `{evaluation_id}` | `{metrics['task']}` | "
                f"{metrics.get('examples', metrics.get('subjects', '—'))} | {status} |"
            )
        lines.append("")
    comparison = report.get("baseline_comparison")
    if comparison:
        lines.extend(["## Baseline difference", ""])
        if comparison["metrics"]:
            lines.extend(
                [
                    "| Metric | Baseline | Current | Delta |",
                    "| --- | ---: | ---: | ---: |",
                ]
            )
            for key, values in comparison["metrics"].items():
                lines.append(
                    f"| `{key}` | {values['baseline']:.6g} | {values['current']:.6g} | "
                    f"{values['delta']:+.6g} |"
                )
        else:
            lines.append("No comparable numeric metrics were found.")
        lines.append("")
    lines.extend(
        [
            "## Interpretation boundary",
            "",
            (
                "Automated smoke results prevent engineering regressions. They do not substitute "
                "for maintainer-authored bilingual queries, independent annotation, "
                "adjudication, or expert assessment of research novelty."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def write_evaluation_report(
    report: dict[str, Any], json_target: Path, markdown_target: Path | None = None
) -> tuple[Path, Path]:
    write_metrics(report, json_target)
    markdown_target = markdown_target or json_target.with_suffix(".md")
    markdown_target.parent.mkdir(parents=True, exist_ok=True)
    markdown_target.write_text(render_evaluation_markdown(report), encoding="utf-8")
    return json_target, markdown_target
