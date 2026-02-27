"""Shared test helpers for the LnBot SDK test suite."""

from __future__ import annotations

import json
from typing import Any

import httpx

from lnbot import LnBot


class CapturedRequest:
    """Stores details about the HTTP request that was made."""

    def __init__(self) -> None:
        self.method: str = ""
        self.url: httpx.URL = httpx.URL("")
        self.headers: httpx.Headers = httpx.Headers()
        self.content: bytes = b""

    @property
    def path(self) -> str:
        return self.url.raw_path.decode().split("?")[0]

    @property
    def query(self) -> str:
        return self.url.query.decode() if self.url.query else ""

    @property
    def json_body(self) -> Any:
        if self.content:
            return json.loads(self.content)
        return None


def create_client(
    status: int = 200,
    json_body: Any = None,
    *,
    content_type: str = "application/json",
) -> tuple[LnBot, CapturedRequest]:
    """Create an LnBot client backed by a mock transport."""
    captured = CapturedRequest()

    def handler(request: httpx.Request) -> httpx.Response:
        captured.method = request.method
        captured.url = request.url
        captured.headers = request.headers
        captured.content = request.content
        body = json.dumps(json_body).encode() if json_body is not None else b""
        return httpx.Response(status, content=body, headers={"content-type": content_type})

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    return LnBot(api_key="key_test", http_client=client), captured


def create_sse_client(sse_text: str) -> tuple[LnBot, CapturedRequest]:
    """Create an LnBot client that returns SSE content for streaming endpoints."""
    captured = CapturedRequest()

    def handler(request: httpx.Request) -> httpx.Response:
        captured.method = request.method
        captured.url = request.url
        captured.headers = request.headers
        captured.content = request.content
        return httpx.Response(
            200,
            content=sse_text.encode(),
            headers={"content-type": "text/event-stream"},
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    return LnBot(api_key="key_test", http_client=client), captured
