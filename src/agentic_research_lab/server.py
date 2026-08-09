from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .paper_catalog import get_public_paper, load_public_catalog
from .proposals import build_proposal_bundle
from .store import DEFAULT_STORE, search_store, store_stats


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")


def make_handler(store_path: Path = DEFAULT_STORE) -> type[BaseHTTPRequestHandler]:
    catalog = load_public_catalog()
    html = files("agentic_research_lab").joinpath("web/index.html").read_bytes()

    class ResearchHandler(BaseHTTPRequestHandler):
        server_version = "AgenticResearchLab/0.2"

        def _send(self, body: bytes, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, value: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
            self._send(_json_bytes(value), "application/json; charset=utf-8", status)

        def do_GET(self) -> None:
            request = urlsplit(self.path)
            query = parse_qs(request.query)
            try:
                if request.path == "/":
                    self._send(html, "text/html; charset=utf-8")
                    return
                if request.path == "/api/stats":
                    local = store_stats(store_path) if store_path.is_file() else {}
                    self._json({"catalog": catalog["summary"], "local_store": local})
                    return
                if request.path == "/api/search":
                    term = query.get("q", [""])[0]
                    limit = min(max(int(query.get("limit", ["10"])[0]), 1), 50)
                    conference = query.get("conference", [None])[0] or None
                    hits = search_store(term, store_path, limit, conference)
                    self._json({"query": term, "hits": [hit.to_dict() for hit in hits]})
                    return
                if request.path == "/api/paper":
                    paper_id = query.get("id", [""])[0]
                    self._json(get_public_paper(catalog, paper_id))
                    return
                self._json({"error": "not-found"}, HTTPStatus.NOT_FOUND)
            except (KeyError, ValueError) as exc:
                self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

        def do_POST(self) -> None:
            if urlsplit(self.path).path != "/api/propose":
                self._json({"error": "not-found"}, HTTPStatus.NOT_FOUND)
                return
            try:
                length = min(int(self.headers.get("Content-Length", "0")), 64_000)
                payload = json.loads(self.rfile.read(length) or b"{}")
                subject = str(payload.get("subject", "")).strip()
                if not subject:
                    raise ValueError("subject is required")
                bundle = build_proposal_bundle(
                    subject,
                    catalog=catalog,
                    store_path=store_path,
                    top_k=min(int(payload.get("top_k", 8)), 20),
                    candidate_count=min(int(payload.get("candidates", 3)), 5),
                )
                self._json(bundle)
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

        def log_message(self, format: str, *args: object) -> None:
            return

    return ResearchHandler


def serve(host: str = "127.0.0.1", port: int = 8765, store_path: Path = DEFAULT_STORE) -> None:
    server = ThreadingHTTPServer((host, port), make_handler(store_path))
    print(f"AgenticResearchLab: http://{host}:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
