#!/usr/bin/env python3
"""Serve CircleCity KML over HTTP for Google Earth NetworkLink refresh."""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
from urllib.parse import parse_qs, urlparse

DEFAULT_PORT = 8765
LINK_NAME = "CircleCity Network"


class KmlState:
    """In-memory KML served to Google Earth; disk is backup only."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.generation = 0
        self.root = None
        self.tree = None

    def set_tree(self, tree) -> None:
        with self._lock:
            self.tree = tree
            self.root = tree.getroot()
            self.generation += 1

    def bump(self) -> None:
        with self._lock:
            self.generation += 1

    def to_bytes(self) -> bytes:
        import xml.etree.ElementTree as ET

        from kml_sync import KML_NS

        with self._lock:
            if self.root is None:
                return b""
            ET.register_namespace("", KML_NS)
            ET.indent(self.tree, space="  ")
            return (
                b'<?xml version="1.0" encoding="UTF-8"?>\n'
                + ET.tostring(self.root, encoding="utf-8")
            )

    def generation_header(self) -> str:
        with self._lock:
            return str(self.generation)


def link_kml_bytes(host: str, port: int) -> bytes:
    base = f"http://{host}:{port}"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>{LINK_NAME}</name>
    <description>
      CircleCity live network. Google Earth refreshes main.kml on interval and
      pings /ping when the view stops — sync reads ~/.googleearth/myplaces.kml
      (where GE stores your edits, not the source file on disk).
    </description>
    <NetworkLink>
      <name>seismic_network</name>
      <open>1</open>
      <refreshVisibility>1</refreshVisibility>
      <flyToView>0</flyToView>
      <Link>
        <href>{base}/main.kml</href>
        <refreshMode>onInterval</refreshMode>
        <refreshInterval>3</refreshInterval>
        <viewRefreshMode>onStop</viewRefreshMode>
        <viewRefreshTime>1</viewRefreshTime>
        <viewFormat>?ping=1&amp;gen=[clientVersion]</viewFormat>
      </Link>
    </NetworkLink>
  </Document>
</kml>
""".encode(
        "utf-8"
    )


def make_handler(
    state: KmlState,
    host: str,
    port: int,
    on_ping: Callable[[dict[str, list[str]]], None] | None,
):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            return

        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("X-CircleCity-Generation", state.generation_header())
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            query = parse_qs(parsed.query)

            if path in ("/link.kml", "/"):
                self._send(
                    200,
                    link_kml_bytes(host, port),
                    "application/vnd.google-earth.kml+xml",
                )
                return

            if path == "/ping":
                if on_ping:
                    on_ping(query)
                self._send(204, b"", "text/plain")
                return

            if path == "/main.kml":
                if "ping" in query and on_ping:
                    on_ping(query)
                body = state.to_bytes()
                if not body:
                    self._send(500, b"missing KML state", "text/plain")
                    return
                self._send(200, body, "application/vnd.google-earth.kml+xml")
                return

            self._send(404, b"not found", "text/plain")

    return Handler


class KmlServer:
    def __init__(
        self,
        state: KmlState,
        host: str = "127.0.0.1",
        port: int = DEFAULT_PORT,
        on_ping: Callable[[dict[str, list[str]]], None] | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.state = state
        handler = make_handler(state, host, port, on_ping)
        self._httpd = ThreadingHTTPServer((host, port), handler)
        self._thread: threading.Thread | None = None

    @property
    def link_url(self) -> str:
        return f"http://{self.host}:{self.port}/link.kml"

    def start(self) -> None:
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._httpd.shutdown()
        if self._thread:
            self._thread.join(timeout=2)