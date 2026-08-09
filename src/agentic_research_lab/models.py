from __future__ import annotations

from dataclasses import dataclass
from typing import Any

ALLOWED_KINDS = {"paper", "benchmark", "dataset", "repository", "reading-list"}
ALLOWED_SCOPES = {
    "mobile",
    "mobile-benchmark",
    "cross-platform-gui",
    "general-agentic",
    "meta",
}


@dataclass(frozen=True)
class Resource:
    id: str
    title: str
    kind: str
    scope: str
    year: int
    summary: str
    tags: tuple[str, ...]
    venue: str = ""
    paper_url: str = ""
    code_url: str = ""
    license: str = ""
    status: str = "verified"

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Resource:
        resource = cls(
            id=str(raw["id"]),
            title=str(raw["title"]),
            kind=str(raw["kind"]),
            scope=str(raw["scope"]),
            year=int(raw["year"]),
            summary=str(raw["summary"]),
            tags=tuple(str(tag) for tag in raw.get("tags", [])),
            venue=str(raw.get("venue", "")),
            paper_url=str(raw.get("paper_url", "")),
            code_url=str(raw.get("code_url", "")),
            license=str(raw.get("license", "")),
            status=str(raw.get("status", "verified")),
        )
        resource.validate()
        return resource

    def validate(self) -> None:
        if not self.id or not self.title or not self.summary:
            raise ValueError("resource id, title, and summary are required")
        if self.kind not in ALLOWED_KINDS:
            raise ValueError(f"unsupported resource kind: {self.kind}")
        if self.scope not in ALLOWED_SCOPES:
            raise ValueError(f"unsupported resource scope: {self.scope}")
        if self.year < 2000 or self.year > 2100:
            raise ValueError(f"implausible resource year: {self.year}")
        if not (self.paper_url or self.code_url):
            raise ValueError(f"resource {self.id} must have a paper or code URL")


@dataclass(frozen=True)
class Topic:
    id: str
    name: str
    description: str
    aliases: tuple[str, ...]
    resources: tuple[Resource, ...]
