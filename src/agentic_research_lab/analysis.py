from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .catalog import search, tokenize
from .models import Resource, Topic

SKIP_DIRS = {".git", ".venv", "node_modules", "build", "dist", "vendor", "outputs"}
TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".kt",
    ".java",
    ".swift",
    ".dart",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
}

DIMENSIONS = {
    "perception-grounding": ("screen", "screenshot", "ui", "vision", "grounding", "accessibility"),
    "planning-control": ("plan", "workflow", "task", "action", "control", "navigation"),
    "memory-reflection": ("memory", "history", "reflection", "recovery", "long-horizon"),
    "personalization-privacy": ("personal", "user", "privacy", "permission", "sensitive"),
    "safety-robustness": ("safety", "attack", "injection", "robust", "failure", "anomaly"),
    "efficiency-deployment": ("latency", "efficient", "device", "cloud", "cost", "mobile"),
    "evaluation": ("benchmark", "evaluation", "success", "trajectory", "verifier"),
}


@dataclass(frozen=True)
class ProjectProfile:
    path: Path
    name: str
    text: str
    extensions: tuple[tuple[str, int], ...]


def profile_repository(path: Path) -> ProjectProfile:
    root = path.expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(root)
    fragments: list[str] = []
    extensions: Counter[str] = Counter()
    for candidate in root.rglob("*"):
        if any(part in SKIP_DIRS for part in candidate.parts):
            continue
        if not candidate.is_file() or candidate.suffix.casefold() not in TEXT_SUFFIXES:
            continue
        extensions[candidate.suffix.casefold()] += 1
        if candidate.name.casefold().startswith("readme") or candidate.name in {
            "pyproject.toml",
            "package.json",
            "pubspec.yaml",
        }:
            try:
                fragments.append(candidate.read_text(encoding="utf-8", errors="replace")[:80_000])
            except OSError:
                pass
    return ProjectProfile(
        path=root,
        name=root.name,
        text="\n".join(fragments)[:240_000],
        extensions=tuple(extensions.most_common(12)),
    )


def _covered_dimensions(text: str) -> set[str]:
    lowered = text.casefold()
    tokens = tokenize(text)
    return {
        dimension
        for dimension, keywords in DIMENSIONS.items()
        if any(keyword in lowered or tokenize(keyword) & tokens for keyword in keywords)
    }


def _evidence_lines(resources: list[Resource]) -> list[str]:
    lines = []
    for resource in resources:
        url = resource.paper_url or resource.code_url
        lines.append(f"- [{resource.title}]({url}) — {resource.summary}")
    return lines


def build_research_report(
    subject: str,
    context: str,
    topic: Topic,
    top_k: int = 8,
    extra_evidence: list[Resource] | None = None,
) -> str:
    query = f"{subject} {context[:20_000]}"
    curated_limit = max(1, top_k // 2) if extra_evidence else top_k
    evidence = search(topic, query, limit=curated_limit)
    seen = {resource.id for resource in evidence}
    for resource in extra_evidence or []:
        if resource.id not in seen:
            evidence.append(resource)
            seen.add(resource.id)
    evidence = evidence[:top_k]
    covered = _covered_dimensions(query)
    gaps = [dimension for dimension in DIMENSIONS if dimension not in covered]
    candidates = []
    for dimension in gaps[:4]:
        if dimension == "memory-reflection":
            candidates.append(
                "加入跨任务记忆、失败反思与状态恢复闭环，并与无记忆/固定历史窗口做消融。"
            )
        elif dimension == "safety-robustness":
            candidates.append(
                "构造环境注入、UI 异常和误操作风险模型，让 Agent 在执行前后进行安全验证。"
            )
        elif dimension == "evaluation":
            candidates.append(
                "把贡献绑定到可复现移动环境、过程级检查点和任务成功验证器，而非只用主观案例。"
            )
        elif dimension == "personalization-privacy":
            candidates.append(
                "研究个性化目标与隐私最小披露之间的约束决策，加入权限和敏感操作审计。"
            )
        elif dimension == "efficiency-deployment":
            candidates.append("设计端云协同路由，以延迟、token、能耗和成功率构成联合优化目标。")
        elif dimension == "perception-grounding":
            candidates.append("融合截图、UI 树和可交互区域，并评测跨分辨率、主题、语言与布局泛化。")
        elif dimension == "planning-control":
            candidates.append("拆分规划、执行、进度管理和纠错角色，验证多 Agent 是否确有必要。")
    if not evidence:
        evidence = list(topic.resources[:top_k])
    lines = [
        "# Agentic research opportunity report",
        "",
        f"## Subject\n\n{subject}",
        "",
        "## Evidence retrieved",
        "",
        *_evidence_lines(evidence),
        "",
        "## Current capability signals",
        "",
        f"Detected dimensions: {', '.join(sorted(covered)) if covered else 'none yet'}.",
        "",
        "## Candidate research upgrades",
        "",
        *[f"{index}. {candidate}" for index, candidate in enumerate(candidates, 1)],
        "",
        "## Required rejection gates",
        "",
        "- Agentic necessity: show why a deterministic workflow or single model is insufficient.",
        "- Novelty: compare each claim against the closest retrieved work, not against a generic baseline.",
        "- Evaluation: define executable tasks, success predicates, cost, latency, safety, and recovery metrics.",
        "- Ablation: isolate planning, memory, reflection, tools, multi-agent roles, and extra inference compute.",
        "- Reproducibility: freeze apps, device configuration, model versions, prompts, and task seeds.",
        "",
    ]
    return "\n".join(lines)


def safe_output_name(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-.")
    return value[:80] or "research-report"
