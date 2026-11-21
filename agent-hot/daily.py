#!/usr/bin/env python3
"""Generate one date of public AgentHot research coverage, or an explicit review."""

import argparse
from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime
import fcntl
from gzip import GzipFile
from html import escape as html_escape
from http.client import HTTPException
import json
import os
from pathlib import Path
import re
import signal
import sys
import tempfile
from textwrap import shorten
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo
import zlib

from build import ATOM, BASE_URL, markdown_inline, publication_time, public_url, validate


ARXIV_ATOM = "https://rss.arxiv.org/atom/cs.AI"
SHANGHAI = ZoneInfo("Asia/Shanghai")
MAX_ATOM_BYTES = 2 * 1024 * 1024
MAX_ATOM_CANDIDATES = 24
REQUEST_SECONDS = 65
AGENT = re.compile(r"\bagent(?:s|ic)?\b|\bmultiagent\b", re.IGNORECASE)
ARXIV_HOSTS = {"arxiv.org", "export.arxiv.org", "www.arxiv.org"}
ARXIV_PAPER = re.compile(r"/abs/(\d{4}\.\d{4,5})(?:v\d+)?\Z", re.ASCII)
SOURCE_ERRORS = (OSError, EOFError, HTTPException, zlib.error, ValueError, ET.ParseError)
DATE_FILE = re.compile(r"\d{4}-\d{2}-\d{2}\.json\Z", re.ASCII)
EXCERPT_CHARS = 300
SENTENCE_END = re.compile(r"""[.!?]["'”’）)\]]*(?:\s+|$)|[。！？][”’」』）】]*\s*""")
ABBREVIATION = re.compile(r"\b(?:et al|figs?|eqs?|refs?|vs|(?:[a-z]\.)+[a-z])\.$", re.IGNORECASE)
THEMES = (
    ("科研自动化与实验 Agent", r"research agents?|self-driving laborator|scientific|experiments?|科研|实验",
     "这些方法如何把一次性演示变成可复查的实验流程？"),
    ("Agent 评测与可靠性", r"benchmark|evaluat|reliab|robust|assess|failure|评测|失败|可靠",
     "用哪些相同任务和失败口径，能复核这些方法的实际差别？"),
    ("多 Agent 协作", r"multi[- ]agent|multiagent|cooperat|collaborat|coordination|多智能体|协作",
     "替换协作协议后，收益来自分工、通信还是额外的计算？"),
    ("Agent 工具调用与编程", r"tool[- ]use|tool call|coding|code agents?|software|工具调用|编程",
     "哪些工具调用真正提高成功率，哪些主要增加成本？"),
    ("Agent 记忆与知识检索", r"memor|retriev|knowledge ground|知识|记忆|检索",
     "缓存的历史、外部证据和任务状态分别对结果贡献多少？"),
    ("视觉与具身 Agent", r"visual|vision|robot|embodied|navigation|视觉|具身|导航",
     "任务环境变化后，哪些视觉和行动策略仍然有效？"),
)


def date_value(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value, flags=re.ASCII):
        raise ValueError("Expected a date in YYYY-MM-DD format")
    return date.fromisoformat(value)


def flat_text(value):
    return " ".join(value.split()) if isinstance(value, str) else ""


def source_urls(url, pdf_url=None):
    if isinstance(url, str) and url.startswith(("http://arxiv.org/", "http://export.arxiv.org/")):
        url = "https://" + url.split("://", 1)[1]
    public_url(url, "daily source url")
    if not pdf_url and urlsplit(url).hostname in ARXIV_HOSTS:
        match = ARXIV_PAPER.fullmatch(urlsplit(url).path)
        if match:
            pdf_url = "https://arxiv.org/pdf/" + match[1]
    if pdf_url:
        public_url(pdf_url, "daily source pdf_url")
    return url, pdf_url


def candidate(title, url, pdf_url, published, abstract):
    title = flat_text(title)
    abstract = flat_text(abstract)
    if not title:
        raise ValueError("Missing daily source title")
    publication_time(published, "daily source published_at")
    url, pdf_url = source_urls(url, pdf_url)
    return {"title": title, "url": url, "pdf_url": pdf_url, "published_at": published, "abstract": abstract}


def atom_candidate(entry):
    announce = entry.findtext("{http://arxiv.org/schemas/atom}announce_type")
    if announce and announce != "new":
        return None
    published = entry.findtext(f"{{{ATOM}}}published")
    link = next((node.get("href") for node in entry.findall(f"{{{ATOM}}}link")
                 if node.get("rel", "alternate") == "alternate"), None)
    url = urlsplit(link or entry.findtext(f"{{{ATOM}}}id") or "")
    paper = ARXIV_PAPER.fullmatch(url.path)
    if not published or url.hostname not in ARXIV_HOSTS or not paper:
        return None
    title = entry.findtext(f"{{{ATOM}}}title") or ""
    abstract = (entry.findtext(f"{{{ATOM}}}summary") or "").split("Abstract:", 1)[-1]
    if not (AGENT.search(title) or AGENT.search(abstract)):
        return None
    return candidate(title, "https://arxiv.org/abs/" + paper[1], None, published, abstract)


def stream_atom_candidates(document):
    parser = ET.XMLPullParser(events=("start", "end"))
    papers = {}
    size = 0
    depth = 0
    try:
        while chunk := document.read1(16 * 1024):
            size += len(chunk)
            if size > MAX_ATOM_BYTES:
                raise ValueError("arXiv Atom feed exceeded the size limit")
            parser.feed(chunk)
            for event, element in parser.read_events():
                if event == "start":
                    if depth == 0 and element.tag != f"{{{ATOM}}}feed":
                        raise ValueError("Expected an arXiv Atom feed")
                    depth += 1
                else:
                    depth -= 1
                    if depth == 1 and element.tag == f"{{{ATOM}}}entry":
                        row = atom_candidate(element)
                        element.clear()
                        if row:
                            papers.setdefault(row["url"], row)
                            if len(papers) == MAX_ATOM_CANDIDATES:
                                return list(papers.values())
        parser.close()
    except SOURCE_ERRORS as error:
        if len(papers) < 5:
            raise
        print(f"arXiv interrupted ({type(error).__name__}); using {len(papers)} complete entries", file=sys.stderr)
    return list(papers.values())


def fixture_candidates(path):
    with path.open("rb") as document:
        if document.peek(256).lstrip().startswith(b"<"):
            return stream_atom_candidates(document)
        data = json.load(document)
    if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
        raise ValueError("Expected a fixture array of candidate objects")
    return [
        candidate(row.get("title"), row.get("url"), row.get("pdf_url"), row.get("published_at"), row.get("abstract"))
        for row in data
    ]


def fetch_arxiv():
    def deadline(_signal, _frame):
        raise TimeoutError("arXiv request exceeded the response deadline")

    previous = signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, REQUEST_SECONDS)
    try:
        request = Request(ARXIV_ATOM, headers={
            "Accept": "application/atom+xml",
            "Accept-Encoding": "gzip",
            "User-Agent": "AgentHot/1.0 (+https://harzva.online/agent-hot/)",
        })
        with urlopen(request, timeout=REQUEST_SECONDS) as response:
            if response.headers.get("Content-Encoding", "").lower() == "gzip":
                with GzipFile(fileobj=response) as document:
                    return stream_atom_candidates(document)
            return stream_atom_candidates(response)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def curated_candidates(feed):
    curated = sorted(feed["items"], key=lambda item: not item.get("featured", False))
    rows = []
    for item in curated:
        source = next((source for source in item["sources"] if source["type"] == "paper"), item["sources"][0])
        rows.append(candidate(item["title"], source["url"], source.get("pdf_url"), item["published_at"], item["summary"]))
    return rows


def choose_topic(rows, last_reviewed=None):
    choices = []
    for name, pattern, question in THEMES:
        matcher = re.compile(pattern, re.IGNORECASE)
        matches = [row for row in rows if matcher.search(row["title"] + " " + row["abstract"])]
        if matches:
            choices.append((name, question, matcher, matches))
    if choices and last_reviewed is not None:
        return min(choices, key=lambda choice: (last_reviewed.get(choice[0], ""), -len(choice[3])))
    if choices:
        return max(choices, key=lambda choice: len(choice[3]))
    return "Agent 研究方法", "怎样用同一组任务、指标和证据比较这些方法？", AGENT, rows


def sentences(text):
    start = 0
    for boundary in SENTENCE_END.finditer(text):
        if boundary.end() < len(text) and ABBREVIATION.search(text, start, boundary.start() + 1):
            continue
        yield text[start:boundary.end()].strip()
        start = boundary.end()
    if start < len(text):
        yield text[start:]


def fresh_excerpt(row, matcher):
    abstract = row["abstract"] or row["title"]
    if len(abstract) <= EXCERPT_CHARS:
        return abstract

    first_sentence = ""
    for sentence in sentences(abstract):
        if len(sentence) > EXCERPT_CHARS:
            continue
        if matcher.search(sentence):
            return sentence
        if not first_sentence:
            first_sentence = sentence
    if first_sentence:
        return first_sentence

    opening = shorten(abstract, width=EXCERPT_CHARS, placeholder="…")
    return row["title"] if opening == "…" else opening


def create_edition(day, now, feed, papers, history):
    cutoff = datetime.combine(day - timedelta(days=1), datetime.min.time(), tzinfo=SHANGHAI)
    prior = [item for edition in history if edition["date"] < day.isoformat() and edition["mode"] == "fresh"
             for item in edition["items"]]
    known = {item["url"] for edition in history if edition["date"] != day.isoformat() and edition["mode"] == "fresh"
             for item in edition["items"]}
    last = max((publication_time(item["published_at"], "previous daily source") for item in prior), default=None)
    fresh = []
    for row in papers:
        published = publication_time(row["published_at"], "daily source")
        if cutoff <= published <= now and (last is None or published > last) and row["url"] not in known and (
            AGENT.search(row["title"]) or AGENT.search(row["abstract"])
        ):
            fresh.append(row)
            known.add(row["url"])
    fresh.sort(key=lambda row: publication_time(row["published_at"], "daily source"), reverse=True)

    mode = "fresh" if fresh else "review"
    last_reviewed = {}
    for previous in history:
        if previous["mode"] == "review" and previous["date"] < day.isoformat():
            theme_name = previous["title"].removeprefix("每日回顾｜")
            last_reviewed[theme_name] = max(previous["date"], last_reviewed.get(theme_name, ""))
    theme, question, matcher, selected = choose_topic(
        fresh if fresh else curated_candidates(feed), None if fresh else last_reviewed,
    )
    items = [
        {key: row[key] for key in ("title", "url", "pdf_url", "published_at")} | {
            "excerpt": fresh_excerpt(row, matcher) if fresh else row["abstract"],
        }
        for row in selected[:5]
    ]
    if fresh:
        dates = sorted({publication_time(item["published_at"], "daily source").astimezone(SHANGHAI).date().isoformat()
                        for item in items})
        summary = (f"从 arXiv cs.AI 近期首次公告选出 {len(items)} 条相关研究。来源公布日"
                   f"为 {'、'.join(dates)}，按标题或摘要里的线索归类。")
        title = f"每日专题｜{theme}"
    else:
        summary = f"本期从 AgentHot 已核精选回顾 {len(items)} 条资料。来源日期保留在每条资料中。"
        title = f"每日回顾｜{theme}"
    return {"date": day.isoformat(), "title": title, "summary": summary, "mode": mode, "question": question, "items": items}


def edition_markdown(edition):
    lines = [
        "# " + markdown_inline(edition["title"]), "",
        f"- 日期：{edition['date']}", f"- 模式：{'新近公开研究' if edition['mode'] == 'fresh' else '精选回顾'}",
        "", markdown_inline(edition["summary"]), "", "## 研究问题", "",
        markdown_inline(edition["question"]), "", "## 资料与证据", "",
    ]
    for item in edition["items"]:
        lines.extend([
            f"### {markdown_inline(item['title'])}", "",
            markdown_inline(item["excerpt"]), "", f"- 来源日期：{item['published_at']}",
            f"- [原文](<{item['url']}>)",
        ])
        if item["pdf_url"]:
            lines.append(f"- [公开 PDF](<{item['pdf_url']}>)")
        lines.append("")
    return "\n".join(lines) + "\n"


def edition_rss(history):
    ET.register_namespace("atom", ATOM)
    root = ET.Element("rss", version="2.0")
    channel = ET.SubElement(root, "channel")
    ET.SubElement(channel, "title").text = "AgentHot 每日专题"
    ET.SubElement(channel, "link").text = BASE_URL + "?view=daily"
    ET.SubElement(channel, "description").text = "按日整理 Agent 研究与可核对的原始来源。"
    ET.SubElement(channel, "language").text = "zh-CN"
    ET.SubElement(channel, f"{{{ATOM}}}link", rel="self", href=BASE_URL + "daily/rss.xml", type="application/rss+xml")
    for edition in history:
        item = ET.SubElement(channel, "item")
        url = BASE_URL + "?view=daily&day=" + edition["date"]
        ET.SubElement(item, "title").text = edition["title"]
        ET.SubElement(item, "link").text = url
        ET.SubElement(item, "guid", isPermaLink="true").text = url
        day = datetime.combine(date_value(edition["date"]), datetime.min.time(), tzinfo=SHANGHAI)
        ET.SubElement(item, "pubDate").text = format_datetime(day.astimezone(timezone.utc), usegmt=True)
        ET.SubElement(item, "description").text = html_escape(edition["summary"])
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8") + "\n"


def atomic_write(path, value):
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if path.is_file() and path.read_bytes() == value.encode("utf-8"):
        return
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".write-", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            os.fchmod(stream.fileno(), 0o644)
            stream.write(value.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def existing_editions(out):
    editions = []
    for path in sorted(out.glob("*.json")):
        if not DATE_FILE.fullmatch(path.name):
            continue
        edition = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(edition, dict) or edition.get("date") != path.stem
                or edition.get("mode") not in {"fresh", "review"} or not edition.get("items")):
            raise ValueError(f"Invalid existing edition: {path.name}")
        editions.append(edition)
    return editions


def run(feed_path, out, day, now, fixture, promote_review=False):
    out.mkdir(parents=True, exist_ok=True)
    with (out / ".publish.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Daily publication already running")
            return
        history = existing_editions(out)
        existing = next((row for row in history if row["date"] == day.isoformat()), None)
        original = existing
        if existing is None or (promote_review and existing["mode"] == "review"):
            feed = json.loads(feed_path.read_text(encoding="utf-8"))
            validate(feed)
            if fixture:
                candidates = fixture_candidates(fixture)
            else:
                try:
                    candidates = fetch_arxiv()
                except SOURCE_ERRORS as error:
                    print(f"arXiv unavailable ({type(error).__name__}); using curated review", file=sys.stderr)
                    candidates = []
            proposed = create_edition(day, now, feed, candidates, history)
            if existing is None or proposed["mode"] == "fresh":
                if existing is not None:
                    history.remove(existing)
                existing = proposed
                history.append(existing)
        atomic_write(out / f"{day}.md", edition_markdown(existing))
        if existing is not original:
            atomic_write(out / f"{day}.json", existing)

        history.sort(key=lambda row: row["date"], reverse=True)
        atomic_write(out / "latest.json", history[0])
        atomic_write(out / "rss.xml", edition_rss(history))
        atomic_write(out / "index.json", {"schema_version": 1, "latest": history[0]["date"], "editions": [
            {key: edition[key] for key in ("date", "title", "mode")} | {"count": len(edition["items"])}
            for edition in history
        ]})
        print(f"AgentHot {day} · {existing['mode']} · {len(existing['items'])} items")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feed", type=Path, required=True, help="Validated static feed.json")
    parser.add_argument("--out", type=Path, required=True, help="Daily publication directory")
    parser.add_argument("--date", help="Edition date, defaulting to today in Asia/Shanghai")
    parser.add_argument("--fixture", type=Path, help="Offline Atom or JSON candidate fixture")
    parser.add_argument("--promote-review", action="store_true", help="Promote an existing review if fresh sources are available")
    args = parser.parse_args()
    now = datetime.now(SHANGHAI)
    try:
        day = date_value(args.date) if args.date else now.date()
        if args.date:
            now = datetime.combine(day, datetime.max.time(), tzinfo=SHANGHAI)
        run(args.feed, args.out, day, now, args.fixture, args.promote_review)
    except (OSError, ValueError, ET.ParseError) as error:
        parser.exit(1, f"Daily build failed: {error}\n")


if __name__ == "__main__":
    main()
