#!/usr/bin/env python3
"""Build the public AgentHot site and feeds from its checked-in edition."""

import argparse
from datetime import datetime, timezone
from email.utils import format_datetime
from html import escape as html_escape
import ipaddress
import json
from pathlib import Path
import re
import tempfile
import unicodedata
from urllib.parse import parse_qsl, urlsplit
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parent
BASE_URL = "https://harzva.online/agent-hot/"
STATIC_FILES = ("index.html", "styles.css", "app.js")
SOURCE_TYPES = {"paper": "论文原文", "report": "官方报告", "repo": "代码仓库"}
COMMUNITY_STATUS = {"planned": "待复现", "reported": "公开运行记录", "reviewed": "独立复核"}
RUN_OUTCOME = {
    "reproduced": "已复现", "partial": "部分复现", "not_reproduced": "未复现", None: "未评估",
}
GIT_REVISION = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z", re.IGNORECASE | re.ASCII)
ATOM = "http://www.w3.org/2005/Atom"
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
DATE = re.compile(
    r"\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d))?\Z",
    re.ASCII,
)
DNS_NAME = re.compile(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{0,62}\Z", re.ASCII)
PRIVATE_SUFFIXES = (
    ".localhost", ".local", ".localdomain", ".internal", ".lan", ".home", ".home.arpa",
    ".onion", ".invalid", ".test", ".example", ".corp", ".private", ".mesh.harzva.online",
    ".ts.net",
)
SENSITIVE_PARAMETERS = {
    "accesskey", "accesskeyid", "accesstoken", "apikey", "auth", "authorization", "cookie",
    "credential", "key", "ossaccesskeyid", "password", "secret", "sig", "signature", "token",
}
EMBEDDED_URL = re.compile(r"""(?i)\b(?:https?|file|smb|nfs|ssh|ftp)://[^\s<>"'\])]+""")
INVALID_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]")


def expect_fields(value, required, optional, label):
    if not isinstance(value, dict) or required - value.keys() or value.keys() - required - optional:
        raise ValueError(f"{label} has missing or unexpected fields")


def public_url(value, label):
    error = f"{label} must be a public HTTPS URL without credentials"
    if not isinstance(value, str) or any(char.isspace() or char in '<>"\\' or ord(char) < 32 for char in value):
        raise ValueError(error)
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").rstrip(".").lower()
        port = parsed.port
    except ValueError:
        raise ValueError(error) from None
    if parsed.scheme != "https" or parsed.username is not None or parsed.password is not None or port == 0:
        raise ValueError(error)
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if not DNS_NAME.fullmatch(host) or ("." + host).endswith(PRIVATE_SUFFIXES):
            raise ValueError(error) from None
    else:
        if not address.is_global or address.is_multicast:
            raise ValueError(error)
    parameters = (parsed.query + "&" + parsed.fragment).replace(";", "&")
    for key, _ in parse_qsl(parameters, keep_blank_values=True):
        normalized = re.sub(r"[^a-z0-9]", "", key.lower())
        if normalized in SENSITIVE_PARAMETERS or normalized.startswith(("xamz", "xgoog")):
            raise ValueError(error)
    return (host, port or 443, parsed.path.rstrip("/"), parsed.query, parsed.fragment)


def text(value, label):
    if not isinstance(value, str) or not value.strip() or INVALID_XML.search(value):
        raise ValueError(f"{label} must be non-empty text")
    for match in EMBEDDED_URL.finditer(value):
        public_url(match.group().rstrip(".,;:!?，。；：！？）】"), label)


def section(value, label):
    if isinstance(value, list) and value:
        for index, line in enumerate(value, 1):
            text(line, f"{label}[{index}]")
    else:
        text(value, label)


def publication_time(value, label):
    if not isinstance(value, str) or not DATE.fullmatch(value):
        raise ValueError(f"{label} must be YYYY-MM-DD or an ISO timestamp with timezone")
    try:
        if len(value) == 10:
            return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
        timestamp = value[:-1] + "+00:00" if value.endswith("Z") else value
        return datetime.fromisoformat(timestamp).astimezone(timezone.utc)
    except (OverflowError, ValueError):
        raise ValueError(f"{label} is not a valid date") from None


def valid_slug(value, label):
    if not isinstance(value, str) or not SLUG.fullmatch(value):
        raise ValueError(f"{label} must use lowercase letters, digits, and hyphens")


def validate(data):
    expect_fields(data, {"schema_version", "edition", "items"}, set(), "feed")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ValueError("schema_version must be 1")
    edition = data["edition"]
    expect_fields(edition, {"slug", "title", "description", "published_at"}, set(), "edition")
    valid_slug(edition["slug"], "edition.slug")
    for field in ("title", "description"):
        text(edition[field], f"edition.{field}")
    edition_time = publication_time(edition["published_at"], "edition.published_at")

    items = data["items"]
    if not isinstance(items, list) or not items:
        raise ValueError("items must be a non-empty array")
    ids = set()
    titles = set()
    item_times = {}
    for index, item in enumerate(items, 1):
        label = f"items[{index}]"
        expect_fields(item, {
            "id", "title", "stage", "summary", "evidence", "reproduce", "published_at", "sources",
        }, {"featured"}, label)
        valid_slug(item["id"], f"{label}.id")
        for field in ("title", "stage", "summary"):
            text(item[field], f"{label}.{field}")
        for field in ("evidence", "reproduce"):
            section(item[field], f"{label}.{field}")
        if "featured" in item and type(item["featured"]) is not bool:
            raise ValueError(f"{label}.featured must be a boolean")
        key = " ".join(unicodedata.normalize("NFKC", item["title"]).casefold().split())
        if item["id"] in ids or key in titles:
            raise ValueError(f"{label} duplicates an item ID or title")
        ids.add(item["id"])
        titles.add(key)
        item_times[item["id"]] = publication_time(item["published_at"], f"{label}.published_at")
        if not isinstance(item["sources"], list) or not item["sources"]:
            raise ValueError(f"{label}.sources must be a non-empty array")
        links = set()
        for source_index, source in enumerate(item["sources"], 1):
            source_label = f"{label}.sources[{source_index}]"
            expect_fields(source, {"type", "title", "url"}, {"pdf_url"}, source_label)
            if not isinstance(source["type"], str) or source["type"] not in SOURCE_TYPES:
                raise ValueError(f"{source_label}.type must be paper, report, or repo")
            text(source["title"], f"{source_label}.title")
            url = public_url(source["url"], f"{source_label}.url")
            if url in links:
                raise ValueError(f"{source_label}.url duplicates a source")
            links.add(url)
            if "pdf_url" in source:
                public_url(source["pdf_url"], f"{source_label}.pdf_url")
    return edition_time, item_times


def validate_community_links(links, label):
    if not isinstance(links, list) or not links:
        raise ValueError(f"{label} must be a non-empty array")
    result = set()
    for index, link in enumerate(links, 1):
        entry = f"{label}[{index}]"
        expect_fields(link, {"title", "url"}, set(), entry)
        text(link["title"], f"{entry}.title")
        url = public_url(link["url"], f"{entry}.url")
        if url in result:
            raise ValueError(f"{entry}.url duplicates a link")
        result.add(url)
    return result


def account_key(value):
    return unicodedata.normalize("NFKC", value).strip().removeprefix("@").casefold()


def validate_community_run(note, label):
    run = note["run"]
    expect_fields(run, {"author", "revision", "environment", "method", "observed", "outcome", "evidence"}, set(), label)
    for field in ("author", "revision", "environment", "method", "observed"):
        text(run[field], f"{label}.{field}")
    if not GIT_REVISION.fullmatch(run["revision"]):
        raise ValueError(f"{label}.revision must be a full Git commit SHA")
    if run["outcome"] is not None and (not isinstance(run["outcome"], str) or run["outcome"] not in RUN_OUTCOME):
        raise ValueError(f"{label}.outcome must be reproduced, partial, not_reproduced, or null")
    author = account_key(run["author"])
    if not author:
        raise ValueError(f"{label}.author must identify the contributor")
    return author, validate_community_links(run["evidence"], f"{label}.evidence")


def validate_community(data, item_ids):
    expect_fields(data, {"schema_version", "notes"}, set(), "community")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ValueError("community.schema_version must be 1")
    if not isinstance(data["notes"], list):
        raise ValueError("community.notes must be an array")
    seen = set()
    common_fields = {"id", "item_id", "title", "published_at", "status", "scope", "steps", "expected", "sources"}
    for index, note in enumerate(data["notes"], 1):
        label = f"community.notes[{index}]"
        expect_fields(note, common_fields, {"run", "review"}, label)
        for key in ("id", "item_id"):
            valid_slug(note[key], f"{label}.{key}")
        if len(note["id"]) > 100:
            raise ValueError(f"{label}.id must be at most 100 characters")
        if note["item_id"] not in item_ids:
            raise ValueError(f"{label}.item_id must refer to an existing selected item")
        if not note["id"].startswith(note["item_id"] + "-"):
            raise ValueError(f"{label}.id must start with item_id followed by a hyphen")
        if note["id"] in seen:
            raise ValueError(f"{label} duplicates a note ID")
        seen.add(note["id"])
        status = note["status"]
        if not isinstance(status, str) or status not in COMMUNITY_STATUS:
            raise ValueError(f"{label}.status must be planned, reported, or reviewed")
        for field in ("title", "scope", "expected"):
            text(note[field], f"{label}.{field}")
        publication_time(note["published_at"], f"{label}.published_at")
        if not isinstance(note["steps"], list) or not note["steps"]:
            raise ValueError(f"{label}.steps must be a non-empty array of text")
        for step, line in enumerate(note["steps"], 1):
            text(line, f"{label}.steps[{step}]")
        sources = validate_community_links(note["sources"], f"{label}.sources")
        if status == "planned":
            if "run" in note or "review" in note:
                raise ValueError(f"{label} must not contain run or review fields while planned")
            continue
        if "run" not in note:
            raise ValueError(f"{label}.run is required after execution is reported")
        author, evidence = validate_community_run(note, f"{label}.run")
        evidence = evidence - sources
        if not evidence:
            raise ValueError(f"{label}.run.evidence must include run output distinct from the input materials")
        if status == "reported":
            if "review" in note:
                raise ValueError(f"{label}.review requires reviewed status")
            continue
        review_label = f"{label}.review"
        review = note.get("review")
        expect_fields(review, {"reviewer", "revision", "url", "evidence_url", "summary"}, set(), review_label)
        for field in ("reviewer", "revision", "summary"):
            text(review[field], f"{review_label}.{field}")
        reviewer = account_key(review["reviewer"])
        if not reviewer or author == reviewer:
            raise ValueError(f"{review_label}.reviewer must be distinct from the run author")
        if review["revision"].lower() != note["run"]["revision"].lower():
            raise ValueError(f"{review_label}.revision does not match the recorded run")
        public_url(review["url"], f"{review_label}.url")
        if public_url(review["evidence_url"], f"{review_label}.evidence_url") not in evidence:
            raise ValueError(f"{review_label}.evidence_url must match published run output")


def item_url(item):
    return BASE_URL + "?item=" + item["id"]


def write_rss(destination, data, edition_time, item_times):
    ET.register_namespace("atom", ATOM)
    root = ET.Element("rss", version="2.0")
    channel = ET.SubElement(root, "channel")
    ET.SubElement(channel, "title").text = "AgentHot"
    ET.SubElement(channel, "link").text = BASE_URL
    ET.SubElement(channel, "description").text = data["edition"]["description"]
    ET.SubElement(channel, "language").text = "zh-CN"
    ET.SubElement(channel, "lastBuildDate").text = format_datetime(edition_time, usegmt=True)
    ET.SubElement(channel, f"{{{ATOM}}}link", rel="self", href=BASE_URL + "rss.xml", type="application/rss+xml")
    for item in sorted(data["items"], key=lambda row: item_times[row["id"]], reverse=True):
        element = ET.SubElement(channel, "item")
        url = item_url(item)
        ET.SubElement(element, "title").text = item["title"]
        ET.SubElement(element, "link").text = url
        ET.SubElement(element, "guid", isPermaLink="true").text = url
        ET.SubElement(element, "pubDate").text = format_datetime(item_times[item["id"]], usegmt=True)
        ET.SubElement(element, "category").text = item["stage"]
        ET.SubElement(element, "description").text = html_escape(item["summary"])
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(destination, encoding="utf-8", xml_declaration=True)


def markdown_inline(value):
    text = " ".join(value.split())
    return re.sub(r"([\\\[\]*_\x60])", r"\\\1", html_escape(text, quote=False))


def markdown_section(value):
    if isinstance(value, list):
        return [f"- {markdown_inline(line)}" for line in value]
    return [markdown_inline(value)]


def write_pages(destination, data, community):
    edition = data["edition"]
    index = [
        "# AgentHot", "", f"> {markdown_inline(edition['description'])}", "",
        f"本期：{markdown_inline(edition['title'])}（{edition['published_at']}）", "",
        "## 入口", "", "- [首页](./)", "- [完整 JSON](feed.json)", "- [RSS](rss.xml)",
        "- [每日专题索引](daily/index.json)", "- [最新一期](daily/latest.json)", "- [每日专题 RSS](daily/rss.xml)",
        "- 按日期读取逐期文档，将索引中的日期用于 daily/YYYY-MM-DD.md 或 daily/YYYY-MM-DD.json。",
        "- [实验笔记 JSON](community/index.json)",
        "", "## 本期条目", "",
    ]
    item_dir = destination / "items"
    item_dir.mkdir()
    for item in data["items"]:
        title = markdown_inline(item["title"])
        link = f"items/{item['id']}.md"
        index.append(f"- [{title}]({link}): {markdown_inline(item['summary'])}")
        page = [
            f"# {title}", "", f"- **阶段** {markdown_inline(item['stage'])}",
            f"- **日期** {item['published_at']}", f"- [网页详情](<{item_url(item)}>)",
            "", "## 摘要", "", markdown_inline(item["summary"]),
            "", "## 证据", "", *markdown_section(item["evidence"]),
            "", "## 如何复现或核对", "", *markdown_section(item["reproduce"]),
            "", "## 公开来源", "",
        ]
        for source in item["sources"]:
            label = SOURCE_TYPES[source["type"]]
            page.append(f"- [{label} · {markdown_inline(source['title'])}](<{source['url']}>)")
            if "pdf_url" in source:
                page.append(f"  · [公开 PDF](<{source['pdf_url']}>)")
        (destination / link).write_text("\n".join(page) + "\n", encoding="utf-8")
    index.extend(("", "## 实验笔记", ""))
    for note in community["notes"]:
        status = COMMUNITY_STATUS[note["status"]]
        index.append(f"- [{markdown_inline(note['title'])}](community/{note['id']}.md) · {status}")
    (destination / "llms.txt").write_text("\n".join(index) + "\n", encoding="utf-8")


def write_community(destination, community):
    directory = destination / "community"
    directory.mkdir()
    (directory / "index.json").write_text(
        json.dumps(community, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    for note in community["notes"]:
        note_id = note["id"]
        item_id = note["item_id"]
        page = [
            f"# {markdown_inline(note['title'])}", "", f"- **状态** {COMMUNITY_STATUS[note['status']]}",
            f"- **笔记 ID** {note_id}", f"- **精选 ID** [{item_id}](../items/{item_id}.md)",
            f"- **日期** {note['published_at']}",
            f"- [网页详情](<{BASE_URL}?view=community&note={note_id}>)", "- [实验笔记 JSON](index.json)",
            "", "## 核查范围与材料", "", markdown_inline(note["scope"]),
            "", "## 计划步骤", "", *markdown_section(note["steps"]),
            "", "## 预期产物", "", markdown_inline(note["expected"]),
            "", "## 公开来源", "",
        ]
        page.extend(f"- [{markdown_inline(link['title'])}](<{link['url']}>)" for link in note["sources"])
        if note["status"] == "planned":
            page.extend(("", "## 实际结果", "", "实验结果未评估。尚无实验运行记录。"))
        else:
            run = note["run"]
            page.extend((
                "", "## 实际运行", "", f"- **记录作者** {markdown_inline(run['author'])}",
                f"- **提交版本** {run['revision']}", f"- **结果** {RUN_OUTCOME[run['outcome']]}",
                "", "### 运行环境", "", markdown_inline(run["environment"]),
                "", "### 实际执行方法", "", markdown_inline(run["method"]),
                "", "### 实际观察", "", markdown_inline(run["observed"]),
                "", "### 运行证据", "",
            ))
            page.extend(f"- [{markdown_inline(link['title'])}](<{link['url']}>)" for link in run["evidence"])
        if note["status"] == "reviewed":
            review = note["review"]
            page.extend((
                "", "## 独立复核", "", f"- **复核者** {markdown_inline(review['reviewer'])}",
                f"- **复核版本** {review['revision']}", f"- [复核记录](<{review['url']}>)",
                f"- [对应运行证据](<{review['evidence_url']}>)", "", markdown_inline(review["summary"]),
            ))
        (directory / f"{note_id}.md").write_text("\n".join(page) + "\n", encoding="utf-8")


def read_feed():
    path = ROOT / "content" / "items.json"
    if path.is_symlink():
        raise ValueError("content/items.json must be a regular source file")
    return json.loads(path.read_text(encoding="utf-8"))


def read_community():
    path = ROOT / "content" / "community.json"
    if path.is_symlink() or not path.is_file():
        raise ValueError("content/community.json must be a regular source file")
    return json.loads(path.read_text(encoding="utf-8"))


def build(out):
    if out.is_symlink():
        raise ValueError("Output must not be a symbolic link")
    out = out.resolve()
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError("Output must be a new or empty directory")
    data = read_feed()
    edition_time, item_times = validate(data)
    community = read_community()
    validate_community(community, item_times)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".agent-hot-", dir=out.parent) as scratch:
        staging = Path(scratch) / "site"
        staging.mkdir()
        for filename in STATIC_FILES:
            asset = ROOT / filename
            if asset.is_symlink() or not asset.is_file() or not asset.stat().st_size:
                raise ValueError(f"Missing or invalid static file: {filename}")
            source = asset.read_bytes()
            text(source.decode("utf-8"), filename)
            (staging / filename).write_bytes(source)
        (staging / "feed.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )
        write_rss(staging / "rss.xml", data, edition_time, item_times)
        write_community(staging, community)
        write_pages(staging, data, community)
        staging.replace(out)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path, help="New or empty output directory")
    args = parser.parse_args()
    try:
        data = build(args.out)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Build failed: {error}\n")
    print(f"Built AgentHot edition {data['edition']['slug']} with {len(data['items'])} items")


if __name__ == "__main__":
    main()
