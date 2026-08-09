from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

TAXONOMY_VERSION = "1.0"

TAXONOMY: dict[str, dict[str, tuple[str, ...]]] = {
    "topics": {
        "mobile-agentic-ai": ("mobile", "android", "smartphone", "phone agent"),
        "gui-agents": ("gui agent", "computer use", "graphical user interface", "web agent"),
        "multi-agent-systems": ("multi-agent", "multiagent", "agent collaboration", "agent team"),
        "agent-memory": ("agent memory", "long-term memory", "episodic memory", "memory system"),
        "agent-safety": (
            "agent safety",
            "safe agent",
            "prompt injection",
            "environmental injection",
        ),
        "agentic-rl": ("agentic reinforcement learning", "multi-turn rl", "reinforcement learning"),
        "coding-agents": ("coding agent", "software engineering agent", "code agent"),
        "scientific-agents": ("scientific agent", "science agent", "research agent"),
        "embodied-agents": ("embodied agent", "robot", "navigation agent"),
        "evaluation": ("benchmark", "evaluation", "arena", "testbed"),
    },
    "agentic_components": {
        "planning": ("planning", "planner", "plan generation"),
        "memory": ("memory", "remember", "experience replay"),
        "reflection": ("reflection", "self-reflect", "self-correction", "critique"),
        "tool-use": ("tool use", "tool-use", "tool calling", "mcp"),
        "multi-agent": ("multi-agent", "multiagent", "agent collaboration", "agent team"),
        "verification": ("verification", "verifier", "validate", "guardrail"),
        "exploration": ("exploration", "explore", "search agent"),
        "self-evolution": ("self-evol", "test-time learning", "continual learning"),
        "world-model": ("world model", "imagination", "simulate futures"),
        "human-in-the-loop": ("human-in-the-loop", "human feedback", "human-agent"),
    },
    "environments": {
        "android": ("android",),
        "ios": ("ios", "iphone", "ipad"),
        "web": ("web agent", "browser", "website", "web navigation"),
        "desktop": ("desktop", "operating system", "computer use"),
        "robotics": ("robot", "embodied", "manipulation"),
        "scientific-workflow": ("scientific", "laboratory", "experiment agent"),
        "software-repository": ("software engineering", "repository", "coding agent"),
    },
    "modalities": {
        "text": ("language model", "text", "llm"),
        "vision": ("vision", "visual", "image", "screenshot", "vlm"),
        "audio": ("audio", "speech", "sound"),
        "structured-ui": ("ui tree", "accessibility", "dom", "xml"),
    },
    "failure_modes": {
        "prompt-injection": ("prompt injection", "indirect injection"),
        "environmental-injection": ("environmental injection", "visual injection"),
        "hallucination": ("hallucination", "hallucinate"),
        "error-propagation": ("error propagation", "snowballing", "cascading failure"),
        "privacy-leakage": ("privacy", "sensitive information", "data leakage"),
        "unsafe-action": ("unsafe action", "irreversible action", "harmful action"),
        "bias-amplification": ("bias amplification", "biased swarm"),
        "collusion": ("collusion", "collude"),
        "long-horizon-drift": ("long-horizon", "long horizon", "misesvolve"),
    },
}

RELATIONS = {
    "topics": "targets",
    "agentic_components": "contains",
    "environments": "operates_in",
    "modalities": "uses_modality",
    "failure_modes": "fails_under",
}


def classify_text(text: str) -> dict[str, list[str]]:
    lowered = text.casefold()
    return {
        group: [label for label, terms in labels.items() if any(term in lowered for term in terms)]
        for group, labels in TAXONOMY.items()
    }


def _named_benchmarks(text: str) -> list[str]:
    matches = re.findall(
        r"\b([A-Z][A-Za-z0-9²³$+_.-]{2,}(?:Bench|World|Arena|Gym|Lab|Suite))\b", text
    )
    return sorted(set(matches), key=str.casefold)


def enrich_taxonomy(catalog: dict[str, Any]) -> dict[str, int]:
    coverage = {group: 0 for group in TAXONOMY}
    for paper in catalog["papers"]:
        text = f"{paper['title']}\n{paper.get('abstract') or ''}"
        labels = classify_text(text)
        for group, values in labels.items():
            paper[group] = values
            if values:
                coverage[group] += 1
        paper["benchmarks"] = _named_benchmarks(text)
        paper["enrichment_status"]["taxonomy"] = "rule-derived"
    catalog["summary"]["taxonomy_coverage"] = coverage
    catalog["taxonomy_version"] = TAXONOMY_VERSION
    return coverage


def taxonomy_document() -> dict[str, Any]:
    return {
        "schema_version": TAXONOMY_VERSION,
        "description": "Deterministic AgenticResearchLab research taxonomy.",
        "groups": {
            group: [{"id": label, "keywords": list(terms)} for label, terms in labels.items()]
            for group, labels in TAXONOMY.items()
        },
    }


def write_taxonomy(target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(taxonomy_document(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return target


def build_relation_graph(catalog: dict[str, Any], connection: sqlite3.Connection) -> dict[str, int]:
    connection.execute("DELETE FROM edges")
    connection.execute("DELETE FROM entities")
    for group, labels in TAXONOMY.items():
        for label in labels:
            entity_id = f"{group}:{label}"
            connection.execute(
                "INSERT INTO entities(id, kind, name, normalized_name) VALUES (?, ?, ?, ?)",
                (entity_id, group, label, label.casefold()),
            )
    for paper in catalog["papers"]:
        for group, relation in RELATIONS.items():
            for label in paper.get(group, []):
                connection.execute(
                    """
                    INSERT OR REPLACE INTO edges(
                        source_id, relation, target_id, paper_id, evidence_json
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        paper["id"],
                        relation,
                        f"{group}:{label}",
                        paper["id"],
                        json.dumps(
                            {"source": "title+abstract", "method": "keyword-taxonomy-v1"},
                            ensure_ascii=False,
                        ),
                    ),
                )
        code_url = paper["links"].get("code")
        if code_url:
            repository_id = f"repository:{code_url.casefold()}"
            connection.execute(
                "INSERT OR IGNORE INTO entities(id, kind, name, normalized_name) VALUES (?, 'repository', ?, ?)",
                (repository_id, code_url, code_url.casefold()),
            )
            connection.execute(
                "INSERT OR REPLACE INTO edges(source_id, relation, target_id, paper_id, evidence_json) VALUES (?, 'implemented_by', ?, ?, ?)",
                (
                    paper["id"],
                    repository_id,
                    paper["id"],
                    json.dumps({"source": "verified-code-catalog"}),
                ),
            )
    connection.commit()
    return {
        "entities": connection.execute("SELECT COUNT(*) FROM entities").fetchone()[0],
        "edges": connection.execute("SELECT COUNT(*) FROM edges").fetchone()[0],
    }
