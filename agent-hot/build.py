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


def write_pages(destination, data):
    edition = data["edition"]
    index = [
        "# AgentHot", "", f"> {markdown_inline(edition['description'])}", "",
        f"本期：{markdown_inline(edition['title'])}（{edition['published_at']}）", "",
        "## 入口", "", "- [首页](./)", "- [完整 JSON](feed.json)", "- [RSS](rss.xml)",
        "- [每日专题索引](daily/index.json)", "- [最新一期](daily/latest.json)", "- [每日专题 RSS](daily/rss.xml)",
        "- 按日期读取逐期文档，将索引中的日期用于 daily/YYYY-MM-DD.md 或 daily/YYYY-MM-DD.json。",
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
    (destination / "llms.txt").write_text("\n".join(index) + "\n", encoding="utf-8")


def read_feed():
    path = ROOT / "content" / "items.json"
    if path.is_symlink():
        raise ValueError("content/items.json must be a regular source file")
    return json.loads(path.read_text(encoding="utf-8"))


def build(out):
    if out.is_symlink():
        raise ValueError("Output must not be a symbolic link")
    out = out.resolve()
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError("Output must be a new or empty directory")
    data = read_feed()
    edition_time, item_times = validate(data)
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
        write_pages(staging, data)
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
