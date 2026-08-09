from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .analysis import build_research_report, profile_repository, safe_output_name
from .catalog import get_topic, load_topics, render_awesome, search, topic_as_json, write_awesome
from .corpus import corpus_stats, optional_manifest, resolve_manifest, search_corpus

DEFAULT_TOPIC = "mobile-agentic-ai"


def _print_resources(resources: list, as_json: bool) -> None:
    if as_json:
        print(
            json.dumps([asdict(resource) for resource in resources], ensure_ascii=False, indent=2)
        )
        return
    for resource in resources:
        links = " ".join(filter(None, [resource.paper_url, resource.code_url]))
        print(f"[{resource.kind}] {resource.year} {resource.title}\n  {links}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="arl", description="AgenticResearchLab CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("topics", help="List built-in research topics")

    awesome = sub.add_parser("awesome", help="Render or export an Awesome topic")
    awesome.add_argument("topic", nargs="?", default=DEFAULT_TOPIC)
    awesome.add_argument("--json", action="store_true")
    awesome.add_argument("--write", type=Path)

    search_parser = sub.add_parser("search", help="Search a topic catalog")
    search_parser.add_argument("query")
    search_parser.add_argument("--topic", default=DEFAULT_TOPIC)
    search_parser.add_argument(
        "--kind", choices=["paper", "benchmark", "dataset", "repository", "reading-list"]
    )
    search_parser.add_argument("--limit", type=int, default=10)
    search_parser.add_argument("--json", action="store_true")

    analyze_topic = sub.add_parser(
        "analyze-topic", help="Create an evidence-grounded research report"
    )
    analyze_topic.add_argument("subject")
    analyze_topic.add_argument("--topic", default=DEFAULT_TOPIC)
    analyze_topic.add_argument("--top-k", type=int, default=8)
    analyze_topic.add_argument("--manifest")
    analyze_topic.add_argument("--output", type=Path)

    analyze_repo = sub.add_parser(
        "analyze-repo", help="Analyze a local project for agentic research opportunities"
    )
    analyze_repo.add_argument("path", type=Path)
    analyze_repo.add_argument("--topic", default=DEFAULT_TOPIC)
    analyze_repo.add_argument("--top-k", type=int, default=8)
    analyze_repo.add_argument("--manifest")
    analyze_repo.add_argument("--output", type=Path)

    stats = sub.add_parser("corpus-stats", help="Inspect an external paper manifest")
    stats.add_argument("--manifest")

    corpus_search = sub.add_parser("corpus-search", help="Search the external paper manifest")
    corpus_search.add_argument("query")
    corpus_search.add_argument("--manifest")
    corpus_search.add_argument("--limit", type=int, default=10)
    corpus_search.add_argument("--json", action="store_true")
    return parser


def _write_or_print(report: str, output: Path | None, default_name: str) -> None:
    if output:
        target = output
        if output.suffix.casefold() != ".md":
            target = output / f"{safe_output_name(default_name)}.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(report, encoding="utf-8")
        print(target)
    else:
        print(report)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "topics":
            for topic in load_topics().values():
                print(f"{topic.id}\t{topic.name}\t{len(topic.resources)} resources")
            return 0
        if args.command == "awesome":
            topic = get_topic(args.topic)
            if args.write:
                print(write_awesome(topic, args.write))
            elif args.json:
                print(topic_as_json(topic))
            else:
                print(render_awesome(topic))
            return 0
        if args.command == "search":
            resources = search(get_topic(args.topic), args.query, args.kind, args.limit)
            _print_resources(resources, args.json)
            return 0
        if args.command == "analyze-topic":
            topic = get_topic(args.topic)
            manifest = optional_manifest(args.manifest)
            external = search_corpus(manifest, args.subject, args.top_k) if manifest else []
            report = build_research_report(args.subject, "", topic, args.top_k, external)
            _write_or_print(report, args.output, args.subject)
            return 0
        if args.command == "analyze-repo":
            profile = profile_repository(args.path)
            context = f"{profile.text}\nExtensions: {profile.extensions}"
            manifest = optional_manifest(args.manifest)
            external = (
                search_corpus(manifest, f"{profile.name} {context[:20_000]}", args.top_k)
                if manifest
                else []
            )
            report = build_research_report(
                profile.name, context, get_topic(args.topic), args.top_k, external
            )
            _write_or_print(report, args.output, profile.name)
            return 0
        if args.command == "corpus-stats":
            print(
                json.dumps(
                    corpus_stats(resolve_manifest(args.manifest)), ensure_ascii=False, indent=2
                )
            )
            return 0
        if args.command == "corpus-search":
            resources = search_corpus(resolve_manifest(args.manifest), args.query, args.limit)
            _print_resources(resources, args.json)
            return 0
    except (KeyError, ValueError, FileNotFoundError, NotADirectoryError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
