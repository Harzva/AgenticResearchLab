from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

FORBIDDEN_PATHS = re.compile(
    "(?:"
    + "|".join(
        re.escape(value)
        for value in (
            "/" + "Users/",
            "/" + "Volumes/",
            "/home/" + "runner/",
            ":\\" + "Users\\",
        )
    )
    + ")",
    re.IGNORECASE,
)
FORBIDDEN_FIELDS = {"downloaded_path", "download_error"}
FORBIDDEN_SUFFIXES = {".pdf", ".sqlite3", ".faiss"}


def violations(root: Path) -> list[str]:
    findings: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if path.suffix.casefold() in FORBIDDEN_SUFFIXES:
            findings.append(f"{relative}: forbidden private artifact type")
            continue
        if path.suffix.casefold() in {".png", ".gif", ".webm", ".mp4"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if FORBIDDEN_PATHS.search(text):
            findings.append(f"{relative}: private build path")
        for field in FORBIDDEN_FIELDS:
            if f'"{field}"' in text:
                findings.append(f"{relative}: private field {field}")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the generated Pages artifact")
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    if not args.root.is_dir():
        print(f"missing Pages artifact: {args.root}", file=sys.stderr)
        return 1
    findings = violations(args.root)
    if findings:
        print("\n".join(findings), file=sys.stderr)
        return 1
    print("Pages artifact safety: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
