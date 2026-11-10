#!/usr/bin/env python3
"""
Chaptarr Smart Reverse Proxy & Metadata Enricher.
Intercepts book search queries from clients (e.g. nzb360), routes searches
to the Goodreads provider, sanitizes HTML descriptions, and normalizes cover URLs.
"""

import gzip
import html
import json
import os
import re
import socketserver
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ProxyConfig:
    upstream_host: str = os.getenv("CHAPTARR_HOST", "chaptarr")
    upstream_port: int = int(os.getenv("CHAPTARR_PORT", "8789"))
    listen_port: int = int(os.getenv("LISTEN_PORT", "8787"))

    @property
    def upstream_base_url(self) -> str:
        return f"http://{self.upstream_host}:{self.upstream_port}"


class HtmlSanitizer:
    """Value-level text sanitizer for stripping HTML tags and normalizing whitespace."""

    _BREAK_PATTERN = re.compile(r"<(br\s*/?|/p|/div)>", flags=re.IGNORECASE)
    _TAG_PATTERN = re.compile(r"<[^>]+>")
    _SPACE_PATTERN = re.compile(r"[ \t]+")
    _NEWLINE_PATTERN = re.compile(r"\n\s*\n+")

    @classmethod
    def clean(cls, text: Any) -> Any:
        if not text or not isinstance(text, str):
            return text
        cleaned = cls._BREAK_PATTERN.sub("\n", text)
        cleaned = cls._TAG_PATTERN.sub("", cleaned)
        cleaned = html.unescape(cleaned)
        cleaned = cls._SPACE_PATTERN.sub(" ", cleaned)
        return cls._NEWLINE_PATTERN.sub("\n\n", cleaned).strip()


class BookMetadataEnricher:
    """Domain service that enriches Chaptarr search results with covers and clean text."""

    def __init__(self, public_base_url: str) -> None:
        self._public_base_url = public_base_url.rstrip("/")

    def enrich_payload(self, data: Any) -> Any:
        if not isinstance(data, list):
            return data

        for item in data:
            if not isinstance(item, dict):
                continue
            self._enrich_item(item)
        return data

    def _enrich_item(self, item: Dict[str, Any]) -> None:
        author = item.get("author")
        if isinstance(author, dict) and "overview" in author:
            author["overview"] = HtmlSanitizer.clean(author["overview"])

        book = item.get("book") if "book" in item else item
        if not isinstance(book, dict) or "title" not in book:
            return

        if "overview" in book:
            book["overview"] = HtmlSanitizer.clean(book["overview"])
        if "overview" in item:
            item["overview"] = HtmlSanitizer.clean(item["overview"])

        cover = self._resolve_cover_url(book)
        if cover:
            book["remotePoster"] = cover
            book["remoteCover"] = cover
            book["images"] = [
                {"coverType": "poster", "url": cover, "extension": ".jpg"},
                {"coverType": "cover", "url": cover, "extension": ".jpg"},
            ]
            item["remotePoster"] = cover
            item["remoteCover"] = cover

    def _resolve_cover_url(self, book: Dict[str, Any]) -> Optional[str]:
        editions: List[Dict[str, Any]] = book.get("editions") or []
        for ed in editions:
            if "overview" in ed:
                ed["overview"] = HtmlSanitizer.clean(ed["overview"])
            for img in ed.get("images") or []:
                url = img.get("url")
                if url and url.startswith("http"):
                    return url

        for img in book.get("images") or []:
            url = img.get("url")
            if url and url.startswith("http"):
                return url

        rel = book.get("remoteCover") or (
            book["images"][0]["url"] if book.get("images") else None
        )
        if rel and rel.startswith("/"):
            return f"{self._public_base_url}{rel}"

        return None


class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True


CONFIG = ProxyConfig()


class ProxyHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write(
            f"{self.address_string()} - - [{self.log_date_time_string()}] {fmt % args}\n"
        )

    def _get_public_base_url(self) -> str:
        host_header = self.headers.get("Host") or f"localhost:{CONFIG.listen_port}"
        return f"http://{host_header}"

    def proxy_request(self, method: str) -> None:
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)

        is_search = (
            parsed.path in ("/api/v1/search", "/api/v1/book/lookup") and method == "GET"
        )
        if parsed.path == "/api/v1/search" and method == "GET":
            qs["provider"] = ["goodreads"]
            new_query = urllib.parse.urlencode(qs, doseq=True)
            upstream_url = f"{CONFIG.upstream_base_url}{parsed.path}?{new_query}"
        else:
            upstream_url = f"{CONFIG.upstream_base_url}{self.path}"

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else None

        req_headers = {
            k: v
            for k, v in self.headers.items()
            if k.lower() not in ("content-length", "host")
        }
        if is_search:
            req_headers.pop("Accept-Encoding", None)
            req_headers.pop("accept-encoding", None)

        if body is not None:
            req_headers["Content-Length"] = str(len(body))

        req = urllib.request.Request(
            upstream_url, data=body, headers=req_headers, method=method
        )

        try:
            with urllib.request.urlopen(req, timeout=35) as resp:
                status = resp.status
                headers = dict(resp.headers)
                raw = resp.read()

                if is_search and status == 200:
                    raw = self._transform_search_response(raw, headers)

                self.send_response(status)
                for k, v in headers.items():
                    if k.lower() not in ("content-length", "transfer-encoding"):
                        self.send_header(k, v)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            for k, v in e.headers.items():
                if k.lower() not in ("content-length", "transfer-encoding"):
                    self.send_header(k, v)
            err_body = e.read()
            self.send_header("Content-Length", str(len(err_body)))
            self.end_headers()
            self.wfile.write(err_body)
        except Exception as e:
            self.send_response(502)
            msg = str(e).encode("utf-8")
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)

    def _transform_search_response(self, raw: bytes, headers: Dict[str, str]) -> bytes:
        try:
            is_gzipped = (
                headers.get("Content-Encoding", "").lower() == "gzip"
                or headers.get("content-encoding", "").lower() == "gzip"
                or (len(raw) >= 2 and raw[0] == 0x1F and raw[1] == 0x8B)
            )
            uncompressed = gzip.decompress(raw) if is_gzipped else raw
            data = json.loads(uncompressed.decode("utf-8"))

            enricher = BookMetadataEnricher(self._get_public_base_url())
            enriched = enricher.enrich_payload(data)
            modified_json = json.dumps(enriched).encode("utf-8")

            client_accepts_gzip = (
                "gzip" in self.headers.get("Accept-Encoding", "").lower()
            )
            if client_accepts_gzip:
                headers["Content-Encoding"] = "gzip"
                return gzip.compress(modified_json)
            else:
                headers.pop("Content-Encoding", None)
                headers.pop("content-encoding", None)
                return modified_json
        except Exception as err:
            sys.stderr.write(f"Enrichment error: {err}\n")
            return raw

    def do_GET(self) -> None:
        self.proxy_request("GET")

    def do_POST(self) -> None:
        self.proxy_request("POST")

    def do_PUT(self) -> None:
        self.proxy_request("PUT")

    def do_DELETE(self) -> None:
        self.proxy_request("DELETE")

    def do_OPTIONS(self) -> None:
        self.proxy_request("OPTIONS")

    def do_HEAD(self) -> None:
        self.proxy_request("HEAD")

    def do_PATCH(self) -> None:
        self.proxy_request("PATCH")


if __name__ == "__main__":
    print(
        f"Starting Chaptarr Proxy on port {CONFIG.listen_port} -> {CONFIG.upstream_base_url}..."
    )
    server = ThreadingHTTPServer(("0.0.0.0", CONFIG.listen_port), ProxyHandler)
    server.serve_forever()
