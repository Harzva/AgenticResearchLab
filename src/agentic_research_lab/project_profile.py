from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

LANGUAGES = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".java": "Java",
    ".swift": "Swift",
    ".dart": "Dart",
    ".rs": "Rust",
    ".go": "Go",
    ".cpp": "C++",
    ".cc": "C++",
    ".c": "C",
    ".rb": "Ruby",
    ".php": "PHP",
    ".md": "Markdown",
    ".toml": "TOML",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
}

SKIP_DIRS = {
    ".git",
    ".venv",
    ".arl",
    "node_modules",
    "build",
    "dist",
    "vendor",
    ".gradle",
    "Pods",
    "DerivedData",
    "__pycache__",
}
SENSITIVE_NAMES = re.compile(
    r"(^|[._-])(env|secret|credential|cookie|token|keychain|auth)([._-]|$)", re.IGNORECASE
)
FRAMEWORK_SIGNALS = {
    "FastAPI": ("fastapi",),
    "PyTorch": ("torch", "pytorch"),
    "Transformers": ("transformers", "huggingface"),
    "LangChain": ("langchain",),
    "AutoGen": ("autogen",),
    "CrewAI": ("crewai",),
    "React": ("react",),
    "Next.js": ("next", "nextjs"),
    "Android": ("androidmanifest.xml", "com.android.application"),
    "SwiftUI": ("swiftui",),
    "Flutter": ("flutter", "pubspec.yaml"),
    "SQLite": ("sqlite", "sqlite3"),
}
CAPABILITY_SIGNALS = {
    "planning": ("planner", "planning", "plan_step"),
    "memory": ("memory", "episodic", "history store"),
    "reflection": ("reflection", "reflect", "critic"),
    "tool-use": ("tool_call", "tools", "mcp", "function calling"),
    "verification": ("verifier", "verification", "validate_action", "guardrail"),
    "multi-agent": ("multi_agent", "multi-agent", "agent team", "autogen"),
    "recovery": ("retry", "recover", "rollback", "fallback"),
    "environment-feedback": ("observation", "environment", "screenshot", "accessibility"),
}


def _git_files(root: Path) -> list[Path] | None:
    if not (root / ".git").exists():
        return None
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-co", "--exclude-standard", "-z"],
        check=False,
        capture_output=True,
    )
    if result.returncode:
        return None
    return [root / value.decode() for value in result.stdout.split(b"\0") if value]


def _candidate_files(root: Path) -> Iterable[Path]:
    git_files = _git_files(root)
    candidates = git_files if git_files is not None else root.rglob("*")
    for path in candidates:
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        if SENSITIVE_NAMES.search(path.name):
            continue
        if not path.is_file() or path.is_symlink():
            continue
        try:
            if path.stat().st_size > 512_000:
                continue
        except OSError:
            continue
        yield path


def _read_text(path: Path) -> str:
    if path.suffix.casefold() not in LANGUAGES and path.name not in {
        "Dockerfile",
        "Makefile",
        "Podfile",
        "Gemfile",
    }:
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _goal(readmes: list[tuple[str, str]]) -> str | None:
    if not readmes:
        return None
    text = readmes[0][1]
    paragraphs = [re.sub(r"\s+", " ", value).strip(" #>\n") for value in text.split("\n\n")]
    return next((paragraph[:600] for paragraph in paragraphs if len(paragraph) > 30), None)


def inspect_project(path: Path) -> dict[str, Any]:
    root = path.expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(root)
    languages: Counter[str] = Counter()
    framework_evidence: dict[str, list[str]] = {name: [] for name in FRAMEWORK_SIGNALS}
    capability_evidence: dict[str, list[str]] = {name: [] for name in CAPABILITY_SIGNALS}
    components: Counter[str] = Counter()
    readmes: list[tuple[str, str]] = []
    tests = 0
    ci = 0
    files_scanned = 0
    for candidate in _candidate_files(root):
        relative = candidate.relative_to(root).as_posix()
        language = LANGUAGES.get(candidate.suffix.casefold())
        if language:
            languages[language] += 1
        lowered_path = relative.casefold()
        if "test" in candidate.name.casefold() or "/tests/" in f"/{lowered_path}/":
            tests += 1
        if lowered_path.startswith(".github/workflows/"):
            ci += 1
        if len(candidate.relative_to(root).parts) > 1:
            components[candidate.relative_to(root).parts[0]] += 1
        text = _read_text(candidate)
        if not text:
            continue
        files_scanned += 1
        lowered = f"{lowered_path}\n{text[:100_000]}".casefold()
        if candidate.name.casefold().startswith("readme"):
            readmes.append((relative, text))
        for framework, signals in FRAMEWORK_SIGNALS.items():
            if any(signal in lowered for signal in signals):
                framework_evidence[framework].append(relative)
        for capability, signals in CAPABILITY_SIGNALS.items():
            if any(signal in lowered for signal in signals):
                capability_evidence[capability].append(relative)
    frameworks = sorted(name for name, evidence in framework_evidence.items() if evidence)
    capabilities = sorted(name for name, evidence in capability_evidence.items() if evidence)
    constraints = []
    if any(framework in frameworks for framework in ("Android", "SwiftUI", "Flutter")):
        constraints.extend(["mobile-device constraints", "app-version and UI-layout drift"])
    if "tool-use" in capabilities:
        constraints.append("external tool reliability and permission boundaries")
    if "environment-feedback" in capabilities:
        constraints.append("dynamic environment observations")
    evidence = []
    for name, paths in framework_evidence.items():
        if paths:
            evidence.append({"kind": "framework", "value": name, "files": sorted(set(paths))[:8]})
    for name, paths in capability_evidence.items():
        if paths:
            evidence.append(
                {"kind": "agentic-capability", "value": name, "files": sorted(set(paths))[:8]}
            )
    return {
        "schema_version": "1.0",
        "name": root.name,
        "root": str(root),
        "goal": _goal(readmes),
        "languages": dict(languages.most_common()),
        "frameworks": frameworks,
        "components": [name for name, _ in components.most_common(20)],
        "agentic_capabilities": capabilities,
        "constraints": sorted(set(constraints)),
        "quality": {"test_files": tests, "ci_workflows": ci, "text_files_scanned": files_scanned},
        "evidence": evidence,
        "safety": {
            "mode": "read-only",
            "gitignore_respected": _git_files(root) is not None,
            "sensitive_names_skipped": True,
            "max_file_bytes": 512_000,
        },
    }


def write_project_profile(profile: dict[str, Any], target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target
