"""Tests for SSE streaming: invoices.watch, payments.watch, events.stream."""

from __future__ import annotations

import json

import httpx
import pytest

from lnbot import LnBot
from lnbot.errors import ForbiddenError, UnauthorizedError
from conftest import create_sse_client


# ---------------------------------------------------------------------------
# Invoice Watch
# ---------------------------------------------------------------------------


class TestInvoiceWatch:
    def test_yields_events(self):
        sse = 'event: settled\ndata: {"number":1,"status":"settled","amount":100,"bolt11":"lnbc1..."}\n\n'
        ln, _ = create_sse_client(sse)
        events = list(ln.invoices.watch(1))
        assert len(events) == 1
        assert events[0].event == "settled"
        assert events[0].data.number == 1
        assert events[0].data.amount == 100

    def test_multiple_events(self):
        sse = (
            'event: pending\ndata: {"number":1,"status":"pending","amount":50,"bolt11":"lnbc1..."}\n\n'
            'event: settled\ndata: {"number":1,"status":"settled","amount":50,"bolt11":"lnbc1..."}\n\n'
        )
        ln, _ = create_sse_client(sse)
        events = list(ln.invoices.watch(1))
        assert len(events) == 2
        assert events[0].event == "pending"
        assert events[1].event == "settled"

    def test_skips_comment_lines(self):
        sse = (
            ': keepalive\n\n'
            'event: settled\ndata: {"number":1,"status":"settled","amount":100,"bolt11":"lnbc1..."}\n\n'
        )
        ln, _ = create_sse_client(sse)
        events = list(ln.invoices.watch(1))
        assert len(events) == 1

    def test_empty_stream(self):
        ln, _ = create_sse_client("")
        events = list(ln.invoices.watch(1))
        assert len(events) == 0

    def test_builds_correct_path(self):
        ln, cap = create_sse_client("")
        list(ln.invoices.watch(42, timeout=120))
        assert cap.path == "/v1/invoices/42/events"
        assert "timeout=120" in cap.query

    def test_omits_timeout_when_none(self):
        ln, cap = create_sse_client("")
        list(ln.invoices.watch(1))
        assert "timeout" not in str(cap.url)

    def test_sends_sse_accept_header(self):
        ln, cap = create_sse_client("")
        list(ln.invoices.watch(1))
        assert cap.headers["accept"] == "text/event-stream"

    def test_sends_authorization(self):
        ln, cap = create_sse_client("")
        list(ln.invoices.watch(1))
        assert cap.headers["authorization"] == "Bearer key_test"

    def test_watch_by_hash(self):
        ln, cap = create_sse_client("")
        list(ln.invoices.watch("abc123"))
        assert cap.path == "/v1/invoices/abc123/events"

    def test_http_error(self):
        captured = None

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                401,
                content=json.dumps({"message": "unauthorized"}).encode(),
                headers={"content-type": "application/json"},
            )

        transport = httpx.MockTransport(handler)
        client = httpx.Client(transport=transport)
        ln = LnBot(api_key="bad_key", http_client=client)
        with pytest.raises(UnauthorizedError):
            list(ln.invoices.watch(1))


# ---------------------------------------------------------------------------
# Payment Watch
# ---------------------------------------------------------------------------


class TestPaymentWatch:
    def test_yields_events(self):
        sse = 'event: settled\ndata: {"number":1,"status":"settled","amount":50,"maxFee":10,"serviceFee":0,"address":"user@ln.bot"}\n\n'
        ln, _ = create_sse_client(sse)
        events = list(ln.payments.watch(1))
        assert len(events) == 1
        assert events[0].event == "settled"
        assert events[0].data.amount == 50

    def test_builds_correct_path(self):
        ln, cap = create_sse_client("")
        list(ln.payments.watch(7, timeout=60))
        assert cap.path == "/v1/payments/7/events"
        assert "timeout=60" in cap.query

    def test_watch_by_hash(self):
        ln, cap = create_sse_client("")
        list(ln.payments.watch("hash123"))
        assert cap.path == "/v1/payments/hash123/events"


# ---------------------------------------------------------------------------
# Events Stream
# ---------------------------------------------------------------------------


class TestEventsStream:
    def test_yields_events(self):
        sse = 'data: {"event":"invoice.settled","createdAt":"2024-01-01T00:00:00Z","data":{"number":1}}\n'
        ln, _ = create_sse_client(sse)
        events = list(ln.events.stream())
        assert len(events) == 1
        assert events[0].event == "invoice.settled"
        assert events[0].data["number"] == 1

    def test_multiple_events(self):
        sse = (
            'data: {"event":"invoice.settled","createdAt":"2024-01-01T00:00:00Z","data":{"number":1}}\n'
            'data: {"event":"payment.settled","createdAt":"2024-01-01T00:00:00Z","data":{"number":2}}\n'
        )
        ln, _ = create_sse_client(sse)
        events = list(ln.events.stream())
        assert len(events) == 2
        assert events[0].event == "invoice.settled"
        assert events[1].event == "payment.settled"

    def test_skips_non_data_lines(self):
        sse = (
            ': keepalive\n'
            'event: ignored\n'
            'data: {"event":"payment.settled","createdAt":"2024-01-01T00:00:00Z","data":{"number":1}}\n'
        )
        ln, _ = create_sse_client(sse)
        events = list(ln.events.stream())
        assert len(events) == 1
        assert events[0].event == "payment.settled"

    def test_builds_correct_path(self):
        ln, cap = create_sse_client("")
        list(ln.events.stream())
        assert cap.path.endswith("/v1/events")

    def test_empty_stream(self):
        ln, _ = create_sse_client("")
        events = list(ln.events.stream())
        assert len(events) == 0

    def test_sends_sse_headers(self):
        ln, cap = create_sse_client("")
        list(ln.events.stream())
        assert cap.headers["accept"] == "text/event-stream"

    def test_http_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                403,
                content=json.dumps({"message": "forbidden"}).encode(),
                headers={"content-type": "application/json"},
            )

        transport = httpx.MockTransport(handler)
        client = httpx.Client(transport=transport)
        ln = LnBot(api_key="key_test", http_client=client)
        with pytest.raises(ForbiddenError):
            list(ln.events.stream())
