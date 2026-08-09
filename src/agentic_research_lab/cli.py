from __future__ import annotations

import argparse
import json
import sys
from contextlib import closing
from dataclasses import asdict
from pathlib import Path

from .analysis import build_research_report, profile_repository, safe_output_name
from .catalog import get_topic, load_topics, render_awesome, search, topic_as_json, write_awesome
from .corpus import corpus_stats, optional_manifest, resolve_manifest, search_corpus
from .enrichment import (
    DECISIONS_FILENAME,
    REPOSITORY_CATALOG_FILENAME,
    apply_repository_statuses,
    build_code_gold_set,
    enrich_code_links,
    merge_repository_verification,
    verify_github_repositories,
    write_repository_catalog,
    write_verification_decisions,
)
from .evaluation import (
    build_human_evaluation_scaffold,
    build_retrieval_gold,
    evaluate_suite,
    resolve_evaluation_suite,
    validate_evaluation_suite,
    write_evaluation_report,
)
from .fulltext import MissingFulltextDependency, build_fulltext_index
from .paper_catalog import (
    CATALOG_FILENAME,
    build_public_assets,
    get_public_paper,
    load_public_catalog,
    search_public_catalog,
    write_corpus_awesome,
    write_public_catalog,
)
from .project_profile import inspect_project, write_project_profile
from .proposals import (
    build_proposal_bundle,
    compare_papers,
    reject_proposal,
    write_proposal_workspace,
)
from .server import serve
from .store import DEFAULT_STORE, connect_store, index_catalog, search_store, store_stats
from .taxonomy import build_relation_graph, enrich_taxonomy, write_taxonomy
from .vectors import build_vector_index, hybrid_search, provider_from_name

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
    corpus_search.add_argument("--catalog", type=Path)
    corpus_search.add_argument("--conference")
    corpus_search.add_argument("--limit", type=int, default=10)
    corpus_search.add_argument("--json", action="store_true")

    corpus_show = sub.add_parser(
        "corpus-show", help="Show the complete public metadata and addresses for one paper"
    )
    corpus_show.add_argument("paper_id")
    corpus_show.add_argument("--catalog", type=Path)

    corpus_build = sub.add_parser(
        "corpus-build", help="Build the sanitized public catalog and Awesome pages"
    )
    corpus_build.add_argument("--manifest")
    corpus_build.add_argument(
        "--data-output",
        type=Path,
        default=Path("src/agentic_research_lab/data") / CATALOG_FILENAME,
    )
    corpus_build.add_argument(
        "--awesome-output", type=Path, default=Path("awesome/all-agentic-papers-2026")
    )

    enrich_code = sub.add_parser(
        "enrich-code", help="Extract, verify, and publish evidence-backed paper code links"
    )
    enrich_code.add_argument(
        "--catalog",
        type=Path,
        default=Path("src/agentic_research_lab/data") / CATALOG_FILENAME,
    )
    enrich_code.add_argument(
        "--repository-output",
        type=Path,
        default=Path("src/agentic_research_lab/data") / REPOSITORY_CATALOG_FILENAME,
    )
    enrich_code.add_argument(
        "--gold-output", type=Path, default=Path("evals/code_link_gold_v1.json")
    )
    enrich_code.add_argument("--decisions", type=Path)
    enrich_code.add_argument(
        "--decisions-output",
        type=Path,
        default=Path("src/agentic_research_lab/data") / DECISIONS_FILENAME,
    )
    enrich_code.add_argument("--awesome-output", type=Path)
    enrich_code.add_argument("--verify-github", action="store_true")
    enrich_code.add_argument("--resume", action="store_true")
    enrich_code.add_argument("--dry-run", action="store_true")

    index_build = sub.add_parser("index-build", help="Build the local SQLite/FTS5 paper index")
    index_build.add_argument("--catalog", type=Path)
    index_build.add_argument("--store", type=Path, default=DEFAULT_STORE)

    fulltext_build = sub.add_parser(
        "fulltext-build", help="Extract local PDFs into page-aware full-text chunks"
    )
    fulltext_build.add_argument("--manifest")
    fulltext_build.add_argument("--store", type=Path, default=DEFAULT_STORE)
    fulltext_build.add_argument("--limit", type=int)
    fulltext_build.add_argument("--missing-only", action="store_true")

    retrieve = sub.add_parser("retrieve", help="Retrieve page-aware evidence from the local index")
    retrieve.add_argument("query")
    retrieve.add_argument("--store", type=Path, default=DEFAULT_STORE)
    retrieve.add_argument("--conference")
    retrieve.add_argument("--limit", type=int, default=10)
    retrieve.add_argument("--json", action="store_true")
    retrieve.add_argument("--vector-provider", choices=["hash", "sentence-transformers"])
    retrieve.add_argument("--vector-model")

    stats_store = sub.add_parser("store-stats", help="Show local knowledge-store coverage")
    stats_store.add_argument("--store", type=Path, default=DEFAULT_STORE)

    taxonomy_build = sub.add_parser(
        "taxonomy-build", help="Classify papers and build the local research relation graph"
    )
    taxonomy_build.add_argument(
        "--catalog",
        type=Path,
        default=Path("src/agentic_research_lab/data") / CATALOG_FILENAME,
    )
    taxonomy_build.add_argument(
        "--taxonomy-output",
        type=Path,
        default=Path("src/agentic_research_lab/data/agentic_taxonomy.json"),
    )
    taxonomy_build.add_argument("--store", type=Path, default=DEFAULT_STORE)
    taxonomy_build.add_argument("--awesome-output", type=Path)

    vector_build = sub.add_parser("vector-build", help="Build an optional local vector index")
    vector_build.add_argument("--catalog", type=Path)
    vector_build.add_argument("--store", type=Path, default=DEFAULT_STORE)
    vector_build.add_argument(
        "--provider", choices=["hash", "sentence-transformers"], default="hash"
    )
    vector_build.add_argument("--model")

    compare = sub.add_parser("compare", help="Compare two papers across research dimensions")
    compare.add_argument("left_id")
    compare.add_argument("right_id")
    compare.add_argument("--catalog", type=Path)

    propose = sub.add_parser(
        "propose", help="Create evidence-grounded Agentic research proposal candidates"
    )
    propose.add_argument("subject")
    propose.add_argument("--catalog", type=Path)
    propose.add_argument("--store", type=Path, default=DEFAULT_STORE)
    propose.add_argument("--top-k", type=int, default=8)
    propose.add_argument("--candidates", type=int, default=3)
    propose.add_argument("--workspace", type=Path)

    reject = sub.add_parser("reject", help="Run rejection gates on a proposal JSON file")
    reject.add_argument("proposal", type=Path)

    repo_inspect = sub.add_parser(
        "repo-inspect", help="Create a deep, read-only project capability profile"
    )
    repo_inspect.add_argument("path", type=Path)
    repo_inspect.add_argument("--output", type=Path)

    serve_parser = sub.add_parser("serve", help="Run the local research dashboard and JSON API")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8765)
    serve_parser.add_argument("--store", type=Path, default=DEFAULT_STORE)

    eval_build = sub.add_parser("eval-build", help="Build deterministic public regression sets")
    eval_build.add_argument("--catalog", type=Path)
    eval_build.add_argument(
        "--retrieval-output", type=Path, default=Path("evals/retrieval_gold_v1.json")
    )
    eval_build.add_argument("--limit", type=int, default=100)

    eval_scaffold = sub.add_parser(
        "eval-scaffold", help="Create unreviewed human Gold annotation scaffolds"
    )
    eval_scaffold.add_argument("--catalog", type=Path)
    eval_scaffold.add_argument("--output", type=Path, default=Path("evals"))
    eval_scaffold.add_argument("--fulltext-limit", type=int, default=100)
    eval_scaffold.add_argument("--force", action="store_true")

    eval_validate = sub.add_parser(
        "eval-validate", help="Validate an evaluation suite and its human-review readiness"
    )
    eval_validate.add_argument("suite", help="smoke, human, or an evaluation suite path")
    eval_validate.add_argument("--require-ready", action="store_true")

    evaluate = sub.add_parser("evaluate", help="Run a versioned evaluation suite")
    evaluate.add_argument("--catalog", type=Path)
    evaluate.add_argument("--store", type=Path, default=DEFAULT_STORE)
    evaluate.add_argument("--suite", default="smoke")
    evaluate.add_argument("--output", type=Path, default=Path("evals/latest_metrics.json"))
    evaluate.add_argument("--report", type=Path)
    evaluate.add_argument("--baseline", type=Path)
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
            external = (
                search_corpus(manifest, args.subject, args.top_k)
                if manifest
                else search_public_catalog(load_public_catalog(), args.subject, args.top_k)
            )
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
                else search_public_catalog(
                    load_public_catalog(), f"{profile.name} {context[:20_000]}", args.top_k
                )
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
            resources = (
                search_corpus(resolve_manifest(args.manifest), args.query, args.limit)
                if args.manifest
                else search_public_catalog(
                    load_public_catalog(args.catalog),
                    args.query,
                    args.limit,
                    args.conference,
                )
            )
            _print_resources(resources, args.json)
            return 0
        if args.command == "corpus-show":
            paper = get_public_paper(load_public_catalog(args.catalog), args.paper_id)
            print(json.dumps(paper, ensure_ascii=False, indent=2))
            return 0
        if args.command == "corpus-build":
            result = build_public_assets(
                resolve_manifest(args.manifest), args.data_output, args.awesome_output
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "enrich-code":
            catalog = load_public_catalog(args.catalog)
            repositories = enrich_code_links(catalog["papers"], args.decisions)
            if args.resume:
                merge_repository_verification(repositories, args.repository_output)
            verification = (
                verify_github_repositories(repositories, resume=args.resume)
                if args.verify_github
                else {}
            )
            linked_papers = (
                apply_repository_statuses(catalog["papers"], repositories)
                if args.verify_github
                else repositories["summary"]["linked_papers"]
            )
            catalog["summary"]["with_code"] = linked_papers
            result = {
                "dry_run": args.dry_run,
                "linked_papers": repositories["summary"]["linked_papers"],
                "repositories": repositories["summary"]["repositories"],
                "verification": verification,
            }
            if not args.dry_run:
                write_public_catalog(catalog, args.catalog)
                write_repository_catalog(repositories, args.repository_output)
                if args.verify_github:
                    write_verification_decisions(repositories, args.decisions_output)
                build_code_gold_set(catalog["papers"], args.gold_output)
                if args.awesome_output:
                    write_corpus_awesome(catalog, args.awesome_output)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "index-build":
            result = index_catalog(load_public_catalog(args.catalog), args.store)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "fulltext-build":
            if not args.store.is_file():
                index_catalog(load_public_catalog(), args.store)
            result = build_fulltext_index(
                resolve_manifest(args.manifest),
                args.store,
                limit=args.limit,
                missing_only=args.missing_only,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "retrieve":
            hits = (
                hybrid_search(
                    args.query,
                    args.store,
                    provider_from_name(args.vector_provider, args.vector_model),
                    args.limit,
                    args.conference,
                )
                if args.vector_provider
                else search_store(args.query, args.store, args.limit, args.conference)
            )
            if args.json:
                print(json.dumps([hit.to_dict() for hit in hits], ensure_ascii=False, indent=2))
            else:
                for hit in hits:
                    location = (
                        f"{hit.section or 'unknown section'}, page {hit.page_start}"
                        if hit.page_start
                        else "metadata"
                    )
                    print(
                        f"[{hit.paper_id}] {hit.title}\n"
                        f"  {location} · {hit.source_url}\n  {hit.excerpt}"
                    )
            return 0
        if args.command == "store-stats":
            print(json.dumps(store_stats(args.store), ensure_ascii=False, indent=2))
            return 0
        if args.command == "taxonomy-build":
            catalog = load_public_catalog(args.catalog)
            coverage = enrich_taxonomy(catalog)
            write_public_catalog(catalog, args.catalog)
            write_taxonomy(args.taxonomy_output)
            index_catalog(catalog, args.store)
            with closing(connect_store(args.store)) as connection:
                graph = build_relation_graph(catalog, connection)
            if args.awesome_output:
                write_corpus_awesome(catalog, args.awesome_output)
            print(json.dumps({"coverage": coverage, "graph": graph}, ensure_ascii=False, indent=2))
            return 0
        if args.command == "compare":
            result = compare_papers(args.left_id, args.right_id, load_public_catalog(args.catalog))
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "propose":
            bundle = build_proposal_bundle(
                args.subject,
                catalog=load_public_catalog(args.catalog),
                store_path=args.store,
                top_k=args.top_k,
                candidate_count=args.candidates,
            )
            if args.workspace:
                outputs = write_proposal_workspace(bundle, args.workspace)
                print(json.dumps({"outputs": [str(path) for path in outputs]}, indent=2))
            else:
                print(json.dumps(bundle, ensure_ascii=False, indent=2))
            return 0
        if args.command == "reject":
            raw = json.loads(args.proposal.read_text(encoding="utf-8"))
            proposals = raw.get("candidates", [raw])
            print(
                json.dumps(
                    [reject_proposal(proposal) for proposal in proposals],
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        if args.command == "vector-build":
            provider = provider_from_name(args.provider, args.model)
            result = build_vector_index(load_public_catalog(args.catalog), args.store, provider)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "repo-inspect":
            profile = inspect_project(args.path)
            if args.output:
                print(write_project_profile(profile, args.output))
            else:
                print(json.dumps(profile, ensure_ascii=False, indent=2))
            return 0
        if args.command == "serve":
            serve(args.host, args.port, args.store)
            return 0
        if args.command == "eval-build":
            gold = build_retrieval_gold(
                load_public_catalog(args.catalog), args.retrieval_output, args.limit
            )
            print(
                json.dumps(
                    {"output": str(args.retrieval_output), "examples": len(gold["examples"])},
                    indent=2,
                )
            )
            return 0
        if args.command == "eval-scaffold":
            outputs = build_human_evaluation_scaffold(
                load_public_catalog(args.catalog),
                args.output,
                fulltext_limit=args.fulltext_limit,
                force=args.force,
            )
            print(json.dumps({"status": "draft", "outputs": [str(path) for path in outputs]}))
            return 0
        if args.command == "eval-validate":
            validation = validate_evaluation_suite(resolve_evaluation_suite(args.suite))
            print(json.dumps(validation, ensure_ascii=False, indent=2))
            if not validation["valid"]:
                return 4
            if args.require_ready and not validation["gate_ready"]:
                return 5
            return 0
        if args.command == "evaluate":
            report = evaluate_suite(
                resolve_evaluation_suite(args.suite),
                catalog_path=args.catalog,
                store_path=args.store,
                baseline_path=args.baseline,
            )
            outputs = write_evaluation_report(report, args.output, args.report)
            print(
                json.dumps(
                    {**report, "outputs": {"json": str(outputs[0]), "markdown": str(outputs[1])}},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            if report["summary"]["blocked"]:
                return 5
            return 0 if report["passed"] else 4
    except (KeyError, TypeError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except MissingFulltextDependency as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
