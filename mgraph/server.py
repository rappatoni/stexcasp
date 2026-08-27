from __future__ import annotations

import json
import threading
import urllib.parse
import webbrowser
from collections.abc import Callable, Collection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .api import DefinitionFragment, FlamsError


def serve_html(
    html: str,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    open_browser: bool = True,
    definition_loader: Callable[[str], DefinitionFragment] | None = None,
    allowed_definition_uris: Collection[str] = (),
) -> None:
    payload = html.encode("utf-8")
    allowed_definitions = frozenset(allowed_definition_uris)

    class Handler(BaseHTTPRequestHandler):
        def _send(
            self, status: int, body: bytes, content_type: str
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "private, max-age=3600")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _definition(self, uri: str) -> None:
            if definition_loader is None or uri not in allowed_definitions:
                self.send_error(404)
                return
            try:
                fragment = definition_loader(uri)
            except FlamsError as error:
                body = json.dumps({"error": str(error)}).encode("utf-8")
                self._send(502, body, "application/json; charset=utf-8")
                return
            body = json.dumps(
                {
                    "uri": fragment.uri,
                    "css": fragment.css,
                    "html": fragment.html,
                },
                ensure_ascii=False,
            ).encode("utf-8")
            self._send(200, body, "application/json; charset=utf-8")

        def do_GET(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlsplit(self.path)
            if parsed.path == "/api/definition":
                uri = urllib.parse.parse_qs(parsed.query).get("uri", [""])[0]
                self._definition(uri)
                return
            if parsed.path not in ("/", "/index.html"):
                self.send_error(404)
                return
            self._send(200, payload, "text/html; charset=utf-8")

        def do_HEAD(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlsplit(self.path)
            if parsed.path not in ("/", "/index.html"):
                self.send_error(404)
                return
            self._send(200, payload, "text/html; charset=utf-8")

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    actual_host, actual_port = server.server_address[:2]
    display_host = "127.0.0.1" if actual_host in ("0.0.0.0", "::") else actual_host
    url = f"http://{display_host}:{actual_port}/"
    print(f"Serving graph at {url}")
    print("Press Ctrl-C to stop.")
    if open_browser:
        threading.Timer(0.2, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
