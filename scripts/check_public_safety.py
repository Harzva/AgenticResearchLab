from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PATHS = re.compile(r"(?:/Users/|/Volumes/|[A-Za-z]:\\Users\\)")
SECRET_ASSIGNMENT = re.compile(
    r"(?:api[_-]?key|access[_-]?token|client[_-]?secret|authorization)\s*[:=]\s*['\"]?[A-Za-z0-9_-]{16,}",
    re.IGNORECASE,
)


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-co", "--exclude-standard", "-z"],
        check=True,
        capture_output=True,
    )
    return [ROOT / value.decode() for value in result.stdout.split(b"\0") if value]


def main() -> int:
    violations = []
    for path in tracked_files():
        if not path.is_file() or path.suffix.casefold() in {".png", ".gif", ".webm", ".mp4"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        relative = path.relative_to(ROOT)
        # This scanner necessarily contains the forbidden-path patterns that it
        # detects. Exclude only its own source from that one self-referential check.
        if relative != Path("scripts/check_public_safety.py") and FORBIDDEN_PATHS.search(text):
            violations.append(f"{relative}: private absolute path")
        if SECRET_ASSIGNMENT.search(text):
            violations.append(f"{relative}: credential-like assignment")
    catalog = json.loads(
        (ROOT / "src/agentic_research_lab/data/conference_agent_papers_2026.json").read_text()
    )
    serialized = json.dumps(catalog)
    for field in ("downloaded_path", "download_error"):
        if f'"{field}"' in serialized:
            violations.append(f"public catalog contains {field}")
    if violations:
        print("\n".join(violations), file=sys.stderr)
        return 1
    print("public safety: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
