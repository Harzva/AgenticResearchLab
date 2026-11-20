#!/usr/bin/env python3
"""Build the public research catalog offline from versioned sources."""

import argparse
import csv
import hashlib
import ipaddress
import json
import re
import shutil
import tempfile
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit


KNOWLEDGE_BASE = Path(__file__).resolve().parent
REPOSITORY = KNOWLEDGE_BASE.parent
STATIC_FILES = ("index.html", "styles.css", "app.js", "graph.js", "research.js")
VENUES = {
    "cvpr": ("CVPR", "conference"),
    "iclr": ("ICLR", "conference"),
    "icml": ("ICML", "conference"),
    "aaai": ("AAAI", "conference"),
    "ijcai": ("IJCAI", "conference"),
    "eccv": ("ECCV", "conference"),
    "tpami": ("TPAMI", "journal"),
}
URL_FIELDS = ("paper_url", "pdf_url", "code_url", "source_url")
ROUTE_PATTERNS = (
    ("research-automation", "科研自动化", r"scientific discovery|scientific workflows?|research agents?|research automation|science agents?|autonomous research|automated research|experiment design|automated experiments?"),
    ("retrieval", "检索与知识接地", r"retrieval-augmented|retrieval|retriev(?:e|es|ing)|knowledge graphs?|knowledge[- ]based|RAG"),
    ("planning", "规划与推理", r"planning|planners?|reasoning|chain of thought|chain-of-thought|task decomposition|tree search"),
    ("tool-use", "工具调用", r"tool use|tool usage|tool[- ]using|tool calling|tool calls?|tool learning|function calling|API calls?"),
    ("memory", "记忆与反思", r"memory|memories|reflection|reflective|self-reflect(?:ion|ing)|lifelong learning|life-long learning"),
    ("evaluation", "评测与基准", r"benchmark(?:s|ing)?|leaderboard|evaluation suite|testbed|agent evaluation"),
    ("multi-agent", "多智能体协作", r"multi[- ]agent|multiagent|agent collaboration|agent coordination"),
    ("embodied", "具身与环境交互", r"embodied|robotics|robot navigation|vision[- ]language navigation|Minecraft"),
    ("gui", "界面与网页操作", r"GUI|computer use|computer-use|web agents?|browser agents?|mobile agents?|screen grounding"),
)
ROUTES = tuple(
    (route_id, label, re.compile(rf"(?<!\w)(?:{patterns})(?!\w)", re.IGNORECASE))
    for route_id, label, patterns in ROUTE_PATTERNS
)


def clean_text(value):
    return " ".join(value.split()) if value else None


def public_url(value):
    if not value:
        return None
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or "." not in parsed.hostname
        or parsed.hostname.endswith((".local", ".internal", ".localhost"))
        or parsed.username is not None
        or parsed.password is not None
        or any(char.isspace() or char in '<>"\\' for char in value)
    ):
        raise ValueError(f"Invalid public HTTPS URL: {parsed.hostname or '(missing host)'}")
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        return value
    if not address.is_global:
        raise ValueError("Non-public IP address in URL")
    return value


def extract_routes(title, abstract):
    routes = []
    for route_id, label, terms in ROUTES:
        for field, content in (("标题", title), ("摘要", abstract)):
            match = terms.search(content or "")
            if match:
                start = max(0, match.start() - 32)
                end = min(len(content), match.end() + 64)
                excerpt = content[start:end]
                routes.append({
                    "id": route_id,
                    "label": label,
                    "term": match.group(0),
                    "evidence": f"{field}：{'…' if start else ''}{excerpt}{'…' if end < len(content) else ''}",
                })
                break
    return routes


def bibtex_for(paper, raw):
    def tex(text):
        escapes = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "&": r"\&", "%": r"\%", "_": r"\_", "#": r"\#", "$": r"\$"}
        return "".join(escapes.get(char, char) for char in text)

    name, kind = VENUES[paper["venue"]]
    fields = {"title": tex(paper["title"]), "year": str(paper["year"])}
    if paper["authors"]:
        fields["author"] = " and ".join(tex(author) for author in paper["authors"])
    if kind == "journal":
        fields["journal"] = raw["journal"]
        fields.update({key: str(raw[key]) for key in ("volume", "number", "pages") if raw.get(key)})
    else:
        fields["booktitle"] = name
    if paper["doi"]:
        fields["doi"] = paper["doi"]
    fields["url"] = paper["paper_url"]
    entry_type = "article" if kind == "journal" else "inproceedings"
    body = ",\n".join(f"  {key} = {{{value}}}" for key, value in fields.items())
    return f"@{entry_type}{{{paper['id']},\n{body}\n}}"


def make_paper(raw, source):
    links = raw.get("links", {})
    paper = {
        "id": raw["id"],
        "title": clean_text(raw["title"]),
        "authors": [clean_text(author) for author in raw["authors"] if clean_text(author)],
        "venue": raw.get("conference", raw.get("venue", "")).lower(),
        "year": int(raw["year"]),
        "abstract": clean_text(raw.get("abstract")),
        "summary_zh": clean_text(raw.get("note_title")),
        "paper_url": raw.get("paper_url") or links.get("official_page"),
        "pdf_url": raw.get("pdf_url") or links.get("resolved_pdf") or links.get("official_pdf") or links.get("arxiv_pdf"),
        "code_url": raw.get("code_url") or links.get("code"),
        "doi": clean_text(raw.get("doi")),
        "source_url": raw.get("source_url") or source["url"],
    }
    if (
        not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", paper["id"])
        or not paper["title"]
        or paper["venue"] not in VENUES
        or not 1900 <= paper["year"] <= 2100
        or not paper["paper_url"]
    ):
        raise ValueError(f"Invalid paper entry: {paper['id']}")
    for field in URL_FIELDS:
        paper[field] = public_url(paper[field])
    paper["routes"] = extract_routes(paper["title"], paper["abstract"])
    paper["bibtex"] = bibtex_for(paper, raw)
    return paper


def load_catalog():
    manifest = json.loads((KNOWLEDGE_BASE / "sources/manifest.json").read_text(encoding="utf-8"))
    papers = []
    sources = []
    for source in manifest["sources"]:
        data_path = REPOSITORY / source["path"]
        data = data_path.read_bytes()
        if hashlib.sha256(data).hexdigest() != source["sha256"]:
            raise ValueError(f"Source digest changed: {source['id']}")
        source_papers = json.loads(data)["papers"]
        if len(source_papers) != source["count"]:
            raise ValueError(f"Source count changed: {source['id']}")
        public_url(source["url"])
        papers.extend(make_paper(raw, source) for raw in source_papers)
        sources.append({key: value for key, value in source.items() if key != "path"})

    ids = {paper["id"] for paper in papers}
    title_keys = {
        "".join(char for char in unicodedata.normalize("NFKC", paper["title"]).casefold() if char.isalnum())
        for paper in papers
    }
    if len(ids) != len(papers) or len(title_keys) != len(papers):
        raise ValueError("Duplicate paper ID or normalized title needs review")
    counts = Counter(paper["venue"] for paper in papers)
    venues = [
        {"id": venue_id, "name": label, "kind": kind, "count": counts[venue_id]}
        for venue_id, (label, kind) in VENUES.items()
    ]
    papers.sort(key=lambda paper: (paper["venue"], -paper["year"], paper["id"]))
    return {"schema_version": 1, "venues": venues, "papers": papers, "sources": sources}


def markdown_escape(value):
    return re.sub(r"([\\`*_[\]#])", r"\\\1", value).replace("<", "&lt;").replace(">", "&gt;")


def markdown_for(paper):
    name, _ = VENUES[paper["venue"]]
    authors = ", ".join(markdown_escape(author) for author in paper["authors"]) or "未登记"
    lines = [f"# {markdown_escape(paper['title'])}", "", f"- 发表：{name} {paper['year']}", f"- 作者：{authors}"]
    if paper["doi"]:
        lines.append(f"- DOI：{paper['doi']}")
    for field, label in (("paper_url", "论文原文"), ("pdf_url", "公开 PDF"), ("code_url", "代码"), ("source_url", "数据来源")):
        if paper[field]:
            lines.append(f"- [{label}](<{paper[field]}>)")
    lines.append(f"- [机器可读 JSON]({paper['id']}.json)")
    if paper["summary_zh"]:
        lines.extend(("", "## 中文导读标题", "", markdown_escape(paper["summary_zh"])))
    if paper["abstract"]:
        lines.extend(("", "## 摘要", "", markdown_escape(paper["abstract"])))
    if paper["routes"]:
        lines.extend(("", "## 技术路线关键词", ""))
        lines.extend(f"- {route['label']} · {markdown_escape(route['evidence'])}" for route in paper["routes"])
    lines.extend(("", "## BibTeX", "", "```bibtex", paper["bibtex"], "```", ""))
    return "\n".join(lines)


def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def write_catalog(out, catalog):
    papers_dir = out / "papers"
    papers_dir.mkdir()
    write_json(out / "catalog.json", catalog)
    llms = [
        "# Agent 论文知识库", "",
        "> 按会议和期刊整理的 Agent 论文索引，含官方论文、可公开获取的 PDF、代码和可追溯的技术路线关键词。", "",
        "- [结构化目录](catalog.json)", "- [CSV 目录](catalog.csv)",
    ]
    papers_by_venue = {venue["id"]: [] for venue in catalog["venues"]}
    columns = ("id", "title", "authors", "venue", "year", "abstract", "summary_zh", *URL_FIELDS, "doi", "routes", "bibtex")
    with (out / "catalog.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for paper in catalog["papers"]:
            paper_id = paper["id"]
            write_json(papers_dir / f"{paper_id}.json", paper)
            (papers_dir / f"{paper_id}.md").write_text(markdown_for(paper), encoding="utf-8")
            papers_by_venue[paper["venue"]].append(paper)
            row = {**paper, "authors": "; ".join(paper["authors"]), "routes": "; ".join(route["id"] for route in paper["routes"])}
            writer.writerow(row)
    for venue in catalog["venues"]:
        llms.extend(("", f"## {venue['name']}", ""))
        llms.extend(
            f"- [{markdown_escape(paper['title'])}](papers/{paper['id']}.md)"
            for paper in papers_by_venue[venue["id"]]
        )
    (out / "llms.txt").write_text("\n".join(llms) + "\n", encoding="utf-8")


def build(out):
    out = out.resolve()
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError("Output must be a new or empty directory")
    catalog = load_catalog()
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".knowledge-base-", dir=out.parent) as scratch:
        staging = Path(scratch) / "site"
        staging.mkdir()
        for filename in STATIC_FILES:
            asset = KNOWLEDGE_BASE / filename
            if asset.is_file():
                shutil.copyfile(asset, staging / filename)
        write_catalog(staging, catalog)
        staging.replace(out)
    return catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path, help="New or empty output directory")
    args = parser.parse_args()
    try:
        catalog = build(args.out)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Build failed: {error}\n")
    print(f"Built {len(catalog['papers'])} papers across {len(catalog['venues'])} venues in {args.out}")


if __name__ == "__main__":
    main()
