from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .catalog import tokenize
from .paper_catalog import get_public_paper, load_public_catalog, search_public_catalog
from .store import DEFAULT_STORE, EvidenceHit, search_store
from .taxonomy import classify_text

PROPOSAL_SCHEMA_VERSION = "1.0"

BLUEPRINTS = {
    "memory-reflection": {
        "components": ["episodic memory", "failure reflection", "state recovery"],
        "claim": "cross-session experience should improve recovery without an unbounded context cost",
        "failure": "the agent repeats previously observed failures or loses state across sessions",
    },
    "safety-verification": {
        "components": ["risk classifier", "pre-action verifier", "post-action audit"],
        "claim": "process-level verification should reduce unsafe actions while preserving task utility",
        "failure": "the agent executes injected, irreversible, or permission-sensitive actions",
    },
    "planning-control": {
        "components": ["hierarchical planner", "progress monitor", "adaptive replanner"],
        "claim": "feedback-conditioned replanning should improve long-horizon completion under change",
        "failure": "a fixed plan becomes invalid after environment or tool feedback",
    },
    "efficient-routing": {
        "components": ["difficulty estimator", "device/cloud router", "budget controller"],
        "claim": "adaptive routing should preserve success while reducing latency, tokens, and energy",
        "failure": "every step uses the most expensive model regardless of task difficulty",
    },
    "multi-agent-necessity": {
        "components": ["role-specific agents", "shared evidence board", "conflict verifier"],
        "claim": "specialized independent evidence paths should outperform an equal-budget single agent",
        "failure": "one policy cannot independently generate and verify competing hypotheses",
    },
}


def _necessity(subject: str) -> tuple[str, list[str]]:
    expanded = f"{subject} {' '.join(tokenize(subject))}".casefold()
    signals = {
        "sequential-state": ("multi-step", "long-horizon", "sequential", "memory"),
        "environment-feedback": ("environment", "mobile", "android", "gui", "feedback"),
        "adaptive-recovery": ("recover", "reflection", "dynamic", "failure"),
        "tool-interaction": ("tool", "action", "control", "navigation"),
        "independent-verification": (
            "safety",
            "verify",
            "verification",
            "verifier",
            "privacy",
            "risk",
        ),
        "multi-agent-coordination": ("multi-agent", "multiagent", "collaboration", "coordination"),
        "process-evaluation": ("benchmark", "process-level", "evaluation"),
    }
    detected = [name for name, terms in signals.items() if any(term in expanded for term in terms)]
    if not detected:
        return (
            (
                "Agentic necessity is not established: first compare against a deterministic "
                "workflow and a single model under the same inference budget."
            ),
            [],
        )
    return (
        "The task exhibits "
        + ", ".join(detected)
        + ", so an observe–decide–act–verify loop is testable against fixed-workflow baselines.",
        detected,
    )


def _evidence(
    subject: str, catalog: dict[str, Any], store_path: Path, top_k: int
) -> list[EvidenceHit]:
    if store_path.is_file():
        hits = search_store(subject, store_path, top_k)
        if hits:
            return hits
    return [
        EvidenceHit(
            paper_id=resource.id,
            title=resource.title,
            source_url=resource.paper_url,
            excerpt=resource.summary,
            score=1.0,
        )
        for resource in search_public_catalog(catalog, subject, top_k)
    ]


def compare_papers(
    left_id: str, right_id: str, catalog: dict[str, Any] | None = None
) -> dict[str, Any]:
    catalog = catalog or load_public_catalog()
    left = get_public_paper(catalog, left_id)
    right = get_public_paper(catalog, right_id)
    fields = [
        "topics",
        "tasks",
        "environments",
        "modalities",
        "agentic_components",
        "benchmarks",
        "failure_modes",
    ]
    comparison = {}
    for field in fields:
        left_values = set(left.get(field, []))
        right_values = set(right.get(field, []))
        comparison[field] = {
            "shared": sorted(left_values & right_values),
            "left_only": sorted(left_values - right_values),
            "right_only": sorted(right_values - left_values),
        }
    return {
        "left": {"id": left["id"], "title": left["title"], "url": left["links"]["official_page"]},
        "right": {
            "id": right["id"],
            "title": right["title"],
            "url": right["links"]["official_page"],
        },
        "dimensions": comparison,
    }


def _blueprint_order(subject: str) -> list[str]:
    expanded = f"{subject} {' '.join(tokenize(subject))}".casefold()
    preferred = []
    if any(term in expanded for term in ("privacy", "safety", "injection", "risk")):
        preferred.append("safety-verification")
    if any(term in expanded for term in ("memory", "long-term", "reflection")):
        preferred.append("memory-reflection")
    if any(term in expanded for term in ("mobile", "device", "latency", "cost")):
        preferred.append("efficient-routing")
    preferred.extend(BLUEPRINTS)
    return list(dict.fromkeys(preferred))


def _nearest_work(hits: list[EvidenceHit], catalog: dict[str, Any]) -> list[dict[str, Any]]:
    paper_map = {paper["id"]: paper for paper in catalog["papers"]}
    matrix = []
    for hit in hits:
        paper = paper_map.get(hit.paper_id, {})
        matrix.append(
            {
                "paper_id": hit.paper_id,
                "title": hit.title,
                "url": hit.source_url,
                "section": hit.section,
                "pages": [hit.page_start, hit.page_end] if hit.page_start else None,
                "evidence_excerpt": hit.excerpt,
                "components": paper.get("agentic_components", []),
                "environments": paper.get("environments", []),
                "failure_modes": paper.get("failure_modes", []),
            }
        )
    return matrix


def build_proposal_bundle(
    subject: str,
    *,
    catalog: dict[str, Any] | None = None,
    store_path: Path = DEFAULT_STORE,
    top_k: int = 8,
    candidate_count: int = 3,
) -> dict[str, Any]:
    catalog = catalog or load_public_catalog()
    hits = _evidence(subject, catalog, store_path, top_k)
    nearest = _nearest_work(hits, catalog)
    necessity, signals = _necessity(subject)
    expanded = f"{subject} {' '.join(tokenize(subject))}"
    detected = classify_text(expanded)
    candidates = []
    for index, blueprint_id in enumerate(_blueprint_order(subject)[:candidate_count], 1):
        blueprint = BLUEPRINTS[blueprint_id]
        proposal = {
            "id": f"candidate-{index}-{blueprint_id}",
            "subject": subject,
            "problem": (
                f"Current approaches to {subject} need an explicit evaluation of when "
                f"{blueprint['failure']}."
            ),
            "target_failure_condition": blueprint["failure"],
            "agentic_necessity": necessity,
            "nearest_work": nearest,
            "falsifiable_claim": (
                f"Under the target failure condition, {blueprint['claim']}; the claim is rejected "
                "if gains disappear after equalizing model, token, tool, and interaction budgets."
            ),
            "method_blueprint": [
                {
                    "component": component,
                    "responsibility": responsibility,
                }
                for component, responsibility in zip(
                    blueprint["components"],
                    [
                        "observe and maintain task state",
                        "choose or revise actions from feedback",
                        "verify outcomes and trigger recovery",
                    ],
                    strict=True,
                )
            ],
            "baseline_ladder": [
                "deterministic workflow without an LLM agent",
                "single-model one-pass policy",
                "single agent with the same tools and total inference budget",
                "closest retrieved Agentic method under equalized budget",
            ],
            "experiment_matrix": [
                {
                    "condition": "clean environment",
                    "metrics": ["task success", "latency", "tokens", "cost"],
                },
                {
                    "condition": blueprint["failure"],
                    "metrics": ["task success", "recovery rate", "unsafe action rate"],
                },
                {
                    "condition": "cross-app/version/language generalization",
                    "metrics": ["task success", "failure taxonomy distribution"],
                },
            ],
            "ablation_matrix": [
                {"remove": component, "tests": "component necessity and compute-normalized gain"}
                for component in blueprint["components"]
            ],
            "metrics": [
                "task success",
                "process checkpoint accuracy",
                "recovery rate",
                "unsafe action rate",
                "latency",
                "tokens",
                "energy or API cost",
            ],
            "budget": {
                "model_calls": "report per successful task",
                "tokens": "equalize across primary baselines",
                "latency": "report p50 and p95",
                "energy": "measure on-device work when applicable",
            },
            "risks": [
                "extra inference compute may explain gains",
                "benchmark leakage or app-version drift",
                "the verifier may share failure modes with the policy",
                "privacy-sensitive or irreversible actions require explicit confirmation",
            ],
            "evidence": [hit.to_dict() for hit in hits],
            "detected_context": detected,
            "necessity_signals": signals,
        }
        proposal["rejection_gates"] = reject_proposal(proposal)["gates"]
        candidates.append(proposal)
    return {
        "schema_version": PROPOSAL_SCHEMA_VERSION,
        "subject": subject,
        "detected_context": detected,
        "nearest_work": nearest,
        "candidates": candidates,
    }


def reject_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
    checks = [
        ("agentic-necessity", bool(proposal.get("necessity_signals"))),
        ("nearest-work", len(proposal.get("nearest_work", [])) >= 3),
        ("falsifiable-claim", "rejected if" in proposal.get("falsifiable_claim", "").casefold()),
        ("baseline-ladder", len(proposal.get("baseline_ladder", [])) >= 4),
        ("experiments", len(proposal.get("experiment_matrix", [])) >= 3),
        ("ablations", len(proposal.get("ablation_matrix", [])) >= 2),
        ("cost-budget", bool(proposal.get("budget", {}).get("tokens"))),
        (
            "safety-risk",
            any("privacy" in risk or "irreversible" in risk for risk in proposal.get("risks", [])),
        ),
        ("evidence", len(proposal.get("evidence", [])) >= 3),
    ]
    gates = [
        {"id": gate_id, "passed": passed, "reason": "satisfied" if passed else "missing evidence"}
        for gate_id, passed in checks
    ]
    passed = sum(gate["passed"] for gate in gates)
    return {
        "proposal_id": proposal.get("id"),
        "status": "pass" if passed == len(gates) else "needs-revision",
        "score": passed / len(gates),
        "gates": gates,
    }


def _markdown(bundle: dict[str, Any]) -> dict[str, str]:
    nearest_lines = ["# Nearest work", ""]
    for item in bundle["nearest_work"]:
        location = f" pages {item['pages'][0]}–{item['pages'][1]}" if item["pages"] else ""
        excerpt = re.sub(r"\s+", " ", item["evidence_excerpt"])
        nearest_lines.append(f"- [{item['title']}]({item['url']}){location}")
        nearest_lines.append(f"  - {excerpt[:500]}")
    candidate_lines = ["# Proposal candidates", ""]
    experiment_lines = ["# Experiment plan", ""]
    rejection_lines = ["# Rejection report", ""]
    for proposal in bundle["candidates"]:
        candidate_lines.extend(
            [
                f"## {proposal['id']}",
                "",
                proposal["problem"],
                "",
                f"**Agentic necessity:** {proposal['agentic_necessity']}",
                "",
                f"**Claim:** {proposal['falsifiable_claim']}",
                "",
            ]
        )
        experiment_lines.extend([f"## {proposal['id']}", ""])
        for experiment in proposal["experiment_matrix"]:
            experiment_lines.append(
                f"- **{experiment['condition']}** — {', '.join(experiment['metrics'])}"
            )
        experiment_lines.append("")
        result = reject_proposal(proposal)
        rejection_lines.extend(
            [f"## {proposal['id']} — {result['status']} ({result['score']:.0%})", ""]
        )
        for gate in result["gates"]:
            rejection_lines.append(
                f"- {'✅' if gate['passed'] else '❌'} `{gate['id']}` — {gate['reason']}"
            )
        rejection_lines.append("")
    return {
        "nearest-work.md": "\n".join(nearest_lines) + "\n",
        "proposal-candidates.md": "\n".join(candidate_lines) + "\n",
        "experiment-plan.md": "\n".join(experiment_lines) + "\n",
        "rejection-report.md": "\n".join(rejection_lines) + "\n",
    }


def write_proposal_workspace(bundle: dict[str, Any], target: Path) -> list[Path]:
    target.mkdir(parents=True, exist_ok=True)
    outputs = [target / "proposals.json"]
    outputs[0].write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name, content in _markdown(bundle).items():
        path = target / name
        path.write_text(content, encoding="utf-8")
        outputs.append(path)
    return outputs
