from __future__ import annotations

import json
import re
from dataclasses import asdict
from importlib.resources import files
from pathlib import Path

from .models import Resource, Topic

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+.-]*", re.IGNORECASE)
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]+")
QUERY_ALIASES = {
    "手机": {"mobile", "smartphone", "android"},
    "移动端": {"mobile", "device"},
    "智能体": {"agent", "agentic"},
    "代理": {"agent", "agentic"},
    "隐私": {"privacy", "private"},
    "安全": {"safety", "safe"},
    "记忆": {"memory"},
    "规划": {"planning", "plan"},
    "反思": {"reflection", "reflect"},
    "评测": {"benchmark", "evaluation"},
    "基准": {"benchmark", "evaluation"},
    "多智能体": {"multi-agent", "multiagent"},
    "个性化": {"personalization", "personalized"},
    "端云": {"device", "cloud", "deployment"},
}


def load_topics() -> dict[str, Topic]:
    path = files("agentic_research_lab").joinpath("data/topics.json")
    raw = json.loads(path.read_text(encoding="utf-8"))
    topics: dict[str, Topic] = {}
    seen_resource_ids: set[str] = set()
    for item in raw["topics"]:
        resources = tuple(Resource.from_dict(resource) for resource in item["resources"])
        for resource in resources:
            if resource.id in seen_resource_ids:
                raise ValueError(f"duplicate resource id: {resource.id}")
            seen_resource_ids.add(resource.id)
        topic = Topic(
            id=item["id"],
            name=item["name"],
            description=item["description"],
            aliases=tuple(item.get("aliases", [])),
            resources=resources,
        )
        topics[topic.id] = topic
    return topics


def get_topic(topic_id: str) -> Topic:
    topics = load_topics()
    if topic_id not in topics:
        available = ", ".join(sorted(topics))
        raise KeyError(f"unknown topic {topic_id!r}; available: {available}")
    return topics[topic_id]


def tokenize(text: str) -> set[str]:
    tokens = {match.group(0).casefold() for match in TOKEN_RE.finditer(text)}
    for match in CJK_RE.finditer(text):
        value = match.group(0)
        tokens.update(value)
        tokens.update(value[index : index + 2] for index in range(len(value) - 1))
        for phrase, aliases in QUERY_ALIASES.items():
            if phrase in value:
                tokens.update(aliases)
    return tokens


def search(topic: Topic, query: str, kind: str | None = None, limit: int = 10) -> list[Resource]:
    query_tokens = tokenize(query)
    scored: list[tuple[float, Resource]] = []
    for resource in topic.resources:
        if kind and resource.kind != kind:
            continue
        title_tokens = tokenize(resource.title)
        tag_tokens = tokenize(" ".join(resource.tags))
        summary_tokens = tokenize(resource.summary)
        score = (
            5 * len(query_tokens & title_tokens)
            + 3 * len(query_tokens & tag_tokens)
            + len(query_tokens & summary_tokens)
        )
        if not query_tokens:
            score = resource.year / 1000
        elif score == 0:
            continue
        scored.append((score + resource.year / 10000, resource))
    scored.sort(key=lambda pair: (pair[0], pair[1].year, pair[1].title), reverse=True)
    return [resource for _, resource in scored[:limit]]


def topic_as_json(topic: Topic) -> str:
    return json.dumps(
        {
            "id": topic.id,
            "name": topic.name,
            "description": topic.description,
            "aliases": list(topic.aliases),
            "resources": [asdict(resource) for resource in topic.resources],
        },
        ensure_ascii=False,
        indent=2,
    )


def render_awesome(topic: Topic) -> str:
    groups = [
        ("Mobile agents and methods", {"paper"}, {"mobile"}),
        ("Benchmarks and datasets", {"benchmark", "dataset"}, {"mobile-benchmark"}),
        ("Open-source mobile systems", {"repository"}, {"mobile"}),
        ("Cross-platform GUI foundations", {"paper", "repository"}, {"cross-platform-gui"}),
        ("Related awesome lists", {"reading-list"}, {"meta"}),
    ]
    lines = [
        f"# Awesome {topic.name}",
        "",
        f"> {topic.description}",
        "",
        "Machine-readable source: `src/agentic_research_lab/data/topics.json`.",
        "Entries are evidence-linked and intentionally distinguish mobile-specific work from general GUI foundations.",
        "",
        "## Contents",
        "",
    ]
    for heading, _, _ in groups:
        anchor = heading.casefold().replace(" ", "-")
        lines.append(f"- [{heading}](#{anchor})")
    lines.append("")
    for heading, kinds, scopes in groups:
        resources = [r for r in topic.resources if r.kind in kinds and r.scope in scopes]
        if not resources:
            continue
        resources.sort(key=lambda resource: (resource.year, resource.title), reverse=True)
        lines.extend([f"## {heading}", ""])
        for resource in resources:
            links = []
            if resource.paper_url:
                links.append(f"[paper]({resource.paper_url})")
            if resource.code_url:
                links.append(f"[code]({resource.code_url})")
            metadata = " · ".join(
                filter(None, [str(resource.year), resource.venue, resource.license])
            )
            lines.append(f"- **{resource.title}** — {resource.summary} ({' · '.join(links)})")
            lines.append(f"  - `{metadata}` · tags: {', '.join(resource.tags)}")
        lines.append("")
    lines.extend(
        [
            "## Scope and contribution rules",
            "",
            "- Mobile-specific work must execute on, train for, or evaluate smartphone/tablet environments.",
            "- General GUI work belongs only in the cross-platform foundation section.",
            "- A code link must point to the project's official or author-linked repository.",
            "- Missing code, uncertain venue status, and non-standard licenses must be stated explicitly.",
            "- Do not add a paper solely because it mentions a device or user interface in passing.",
            "",
        ]
    )
    return "\n".join(lines)


def write_awesome(topic: Topic, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_awesome(topic), encoding="utf-8")
    return target
