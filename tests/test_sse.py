"""Tests for SSE streaming: invoices.watch, payments.watch, events.stream."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from lnbot import LnBot
from lnbot.errors import ForbiddenError, UnauthorizedError
from conftest import create_async_sse_client, create_sse_client


# ---------------------------------------------------------------------------
# Invoice Watch
# ---------------------------------------------------------------------------


class TestInvoiceWatch:
    def test_yields_events(self):
        sse = 'event: settled\ndata: {"number":1,"status":"settled","amount":100,"bolt11":"lnbc1..."}\n\n'
        ln, _ = create_sse_client(sse)
        events = list(ln.wallet("wal_1").invoices.watch(1))
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
        events = list(ln.wallet("wal_1").invoices.watch(1))
        assert len(events) == 2
        assert events[0].event == "pending"
        assert events[1].event == "settled"

    def test_skips_comment_lines(self):
        sse = (
            ': keepalive\n\n'
            'event: settled\ndata: {"number":1,"status":"settled","amount":100,"bolt11":"lnbc1..."}\n\n'
        )
        ln, _ = create_sse_client(sse)
        events = list(ln.wallet("wal_1").invoices.watch(1))
        assert len(events) == 1

    def test_empty_stream(self):
        ln, _ = create_sse_client("")
        events = list(ln.wallet("wal_1").invoices.watch(1))
        assert len(events) == 0

    def test_builds_correct_path(self):
        ln, cap = create_sse_client("")
        list(ln.wallet("wal_1").invoices.watch(42, timeout=120))
        assert cap.path == "/v1/wallets/wal_1/invoices/42/events"
        assert "timeout=120" in cap.query

    def test_omits_timeout_when_none(self):
        ln, cap = create_sse_client("")
        list(ln.wallet("wal_1").invoices.watch(1))
        assert "timeout" not in str(cap.url)

    def test_sends_sse_accept_header(self):
        ln, cap = create_sse_client("")
        list(ln.wallet("wal_1").invoices.watch(1))
        assert cap.headers["accept"] == "text/event-stream"

    def test_sends_authorization(self):
        ln, cap = create_sse_client("")
        list(ln.wallet("wal_1").invoices.watch(1))
        assert cap.headers["authorization"] == "Bearer key_test"

    def test_watch_by_hash(self):
        ln, cap = create_sse_client("")
        list(ln.wallet("wal_1").invoices.watch("abc123"))
        assert cap.path == "/v1/wallets/wal_1/invoices/abc123/events"

    def test_http_error(self):
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
            list(ln.wallet("wal_1").invoices.watch(1))


# ---------------------------------------------------------------------------
# Payment Watch
# ---------------------------------------------------------------------------


class TestPaymentWatch:
    def test_yields_events(self):
        sse = 'event: settled\ndata: {"number":1,"status":"settled","amount":50,"max_fee":10,"service_fee":0,"address":"user@ln.bot"}\n\n'
        ln, _ = create_sse_client(sse)
        events = list(ln.wallet("wal_1").payments.watch(1))
        assert len(events) == 1
        assert events[0].event == "settled"
        assert events[0].data.amount == 50
        assert events[0].data.max_fee == 10

    def test_camel_case_payload_still_decodes(self):
        sse = 'event: settled\ndata: {"number":1,"status":"settled","amount":50,"maxFee":10,"serviceFee":1,"actualFee":3,"address":"user@ln.bot","txNumber":4,"failureReason":null,"createdAt":"2026-10-24T14:50:01Z","settledAt":"2026-10-24T14:50:14Z"}\n\n'
        ln, _ = create_sse_client(sse)
        events = list(ln.wallet("wal_1").payments.watch(1))
        assert len(events) == 1
        p = events[0].data
        assert (p.max_fee, p.service_fee, p.actual_fee, p.tx_number) == (10, 1, 3, 4)
        assert p.created_at == "2026-10-24T14:50:01Z"
        assert p.settled_at == "2026-10-24T14:50:14Z"

    def test_builds_correct_path(self):
        ln, cap = create_sse_client("")
        list(ln.wallet("wal_1").payments.watch(7, timeout=60))
        assert cap.path == "/v1/wallets/wal_1/payments/7/events"
        assert "timeout=60" in cap.query

    def test_watch_by_hash(self):
        ln, cap = create_sse_client("")
        list(ln.wallet("wal_1").payments.watch("hash123"))
        assert cap.path == "/v1/wallets/wal_1/payments/hash123/events"


# ---------------------------------------------------------------------------
# Events Stream
# ---------------------------------------------------------------------------


class TestEventsStream:
    def test_yields_events(self):
        sse = 'data: {"event":"invoice.settled","created_at":"2024-01-01T00:00:00Z","data":{"number":1}}\n'
        ln, _ = create_sse_client(sse)
        events = list(ln.wallet("wal_1").events.stream())
        assert len(events) == 1
        assert events[0].event == "invoice.settled"
        assert events[0].created_at == "2024-01-01T00:00:00Z"
        assert events[0].data["number"] == 1

    def test_camel_case_envelope_still_decodes(self):
        sse = 'data: {"event":"payment.settled","createdAt":"2026-10-24T14:50:14.123+00:00","data":{"number":1,"maxFee":5,"actualFee":3,"txNumber":4}}\n'
        ln, _ = create_sse_client(sse)
        events = list(ln.wallet("wal_1").events.stream())
        assert len(events) == 1
        assert events[0].created_at == "2026-10-24T14:50:14.123+00:00"
        assert events[0].data == {"number": 1, "max_fee": 5, "actual_fee": 3, "tx_number": 4}

    def test_multiple_events(self):
        sse = (
            'data: {"event":"invoice.settled","created_at":"2024-01-01T00:00:00Z","data":{"number":1}}\n'
            'data: {"event":"payment.settled","created_at":"2024-01-01T00:00:00Z","data":{"number":2}}\n'
        )
        ln, _ = create_sse_client(sse)
        events = list(ln.wallet("wal_1").events.stream())
        assert len(events) == 2
        assert events[0].event == "invoice.settled"
        assert events[1].event == "payment.settled"

    def test_skips_non_data_lines(self):
        sse = (
            ': keepalive\n'
            'event: ignored\n'
            'data: {"event":"payment.settled","created_at":"2024-01-01T00:00:00Z","data":{"number":1}}\n'
        )
        ln, _ = create_sse_client(sse)
        events = list(ln.wallet("wal_1").events.stream())
        assert len(events) == 1
        assert events[0].event == "payment.settled"

    def test_builds_correct_path(self):
        ln, cap = create_sse_client("")
        list(ln.wallet("wal_1").events.stream())
        assert cap.path.endswith("/v1/wallets/wal_1/events")

    def test_empty_stream(self):
        ln, _ = create_sse_client("")
        events = list(ln.wallet("wal_1").events.stream())
        assert len(events) == 0

    def test_sends_sse_headers(self):
        ln, cap = create_sse_client("")
        list(ln.wallet("wal_1").events.stream())
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
            list(ln.wallet("wal_1").events.stream())


# ---------------------------------------------------------------------------
# Wire format: the API sends event payloads in snake_case
# ---------------------------------------------------------------------------

PAYMENT_SETTLED = '{"number":1,"status":"settled","amount":20,"max_fee":5,"service_fee":1,"actual_fee":3,"address":"bub@bub.gg","reference":null,"preimage":"ab12...","tx_number":4,"failure_reason":null,"created_at":"2026-10-24T14:50:01Z","settled_at":"2026-10-24T14:50:14Z"}'
PAYMENT_FAILED = '{"number":2,"status":"failed","amount":20,"max_fee":5,"service_fee":1,"actual_fee":null,"address":"bub@bub.gg","reference":null,"preimage":null,"tx_number":null,"failure_reason":"No route found","created_at":"2026-10-24T14:50:01Z","settled_at":null}'
PAYMENT_PENDING = '{"number":3,"status":"pending","amount":20,"max_fee":5,"service_fee":1,"actual_fee":null,"address":"bub@bub.gg","reference":null,"preimage":null,"tx_number":null,"failure_reason":null,"created_at":"2026-10-24T14:50:01Z","settled_at":null}'
INVOICE_SETTLED = '{"number":7,"status":"settled","amount":1000,"bolt11":"lnbc10u1p...","reference":null,"memo":null,"preimage":"cd34...","tx_number":4,"created_at":"2026-10-24T14:40:00Z","settled_at":"2026-10-24T14:41:30Z","expires_at":"2026-10-24T15:40:00Z"}'
INVOICE_PENDING = '{"number":8,"status":"pending","amount":1000,"bolt11":"lnbc10u1p...","reference":null,"memo":null,"preimage":null,"tx_number":null,"created_at":"2026-10-24T14:40:00Z","settled_at":null,"expires_at":"2026-10-24T15:40:00Z"}'

WALLET_PAYMENT_SETTLED = '{"event":"payment.settled","created_at":"2026-10-24T14:50:14.123+00:00","data":' + PAYMENT_SETTLED + '}'
WALLET_PAYMENT_CREATED = '{"event":"payment.created","created_at":"2026-10-24T14:50:01.456+00:00","data":{"number":1,"status":"pending","amount":20,"max_fee":5,"service_fee":1,"address":"bub@bub.gg","reference":null,"created_at":"2026-10-24T14:50:01Z"}}'
WALLET_INVOICE_CREATED = '{"event":"invoice.created","created_at":"2026-10-24T14:40:00.789+00:00","data":{"number":7,"status":"pending","amount":1000,"bolt11":"lnbc10u1p...","reference":null,"memo":null,"created_at":"2026-10-24T14:40:00Z","expires_at":"2026-10-24T15:40:00Z"}}'
WALLET_INVOICE_SETTLED = '{"event":"invoice.settled","created_at":"2026-10-24T14:41:30.5+00:00","data":' + INVOICE_SETTLED + '}'


def _events(sse: str, use_async: bool, call):
    """Collect the events *call* yields for a wallet handle, with the sync or the async client."""
    if use_async:
        aln, _ = create_async_sse_client(sse)

        async def run():
            return [e async for e in call(aln.wallet("wal_1"))]

        return asyncio.run(run())
    ln, _ = create_sse_client(sse)
    return list(call(ln.wallet("wal_1")))


def _watch_payment(w):
    return w.payments.watch(1)


def _watch_invoice(w):
    return w.invoices.watch(7)


def _stream(w):
    return w.events.stream()


@pytest.mark.parametrize("use_async", [False, True], ids=["sync", "async"])
class TestWirePayloads:
    def test_payment_settled_decodes_fees_and_timestamps(self, use_async):
        events = _events(f":keepalive\n\nevent: settled\ndata: {PAYMENT_SETTLED}\n\n", use_async, _watch_payment)
        assert len(events) == 1
        assert events[0].event == "settled"
        p = events[0].data
        assert (p.number, p.status, p.amount, p.address) == (1, "settled", 20, "bub@bub.gg")
        assert p.max_fee == 5
        assert p.service_fee == 1
        assert p.actual_fee == 3
        assert p.tx_number == 4
        assert p.preimage == "ab12..."
        assert p.failure_reason is None
        assert p.created_at == "2026-10-24T14:50:01Z"
        assert p.settled_at == "2026-10-24T14:50:14Z"

    def test_payment_failed_decodes_failure_reason(self, use_async):
        events = _events(f"event: failed\ndata: {PAYMENT_FAILED}\n\n", use_async, _watch_payment)
        assert len(events) == 1
        assert events[0].event == "failed"
        p = events[0].data
        assert p.status == "failed"
        assert p.failure_reason == "No route found"
        assert p.actual_fee is None
        assert p.settled_at is None

    def test_payment_timeout_carries_current_state(self, use_async):
        events = _events(f"event: timeout\ndata: {PAYMENT_PENDING}\n\n", use_async, _watch_payment)
        assert len(events) == 1
        assert events[0].event == "timeout"
        p = events[0].data
        assert p.status == "pending"
        assert (p.max_fee, p.service_fee) == (5, 1)
        assert p.created_at == "2026-10-24T14:50:01Z"

    def test_invoice_settled_decodes_tx_number_and_timestamps(self, use_async):
        events = _events(f"event: settled\ndata: {INVOICE_SETTLED}\n\n", use_async, _watch_invoice)
        assert len(events) == 1
        assert events[0].event == "settled"
        inv = events[0].data
        assert (inv.number, inv.status, inv.amount, inv.bolt11) == (7, "settled", 1000, "lnbc10u1p...")
        assert inv.preimage == "cd34..."
        assert inv.tx_number == 4
        assert inv.created_at == "2026-10-24T14:40:00Z"
        assert inv.settled_at == "2026-10-24T14:41:30Z"
        assert inv.expires_at == "2026-10-24T15:40:00Z"

    def test_invoice_timeout_carries_current_state(self, use_async):
        events = _events(f"event: timeout\ndata: {INVOICE_PENDING}\n\n", use_async, _watch_invoice)
        assert len(events) == 1
        assert events[0].event == "timeout"
        assert events[0].data.status == "pending"
        assert events[0].data.expires_at == "2026-10-24T15:40:00Z"

    def test_wallet_envelope_decodes_created_at_and_nested_data(self, use_async):
        events = _events(f":keepalive\n\ndata: {WALLET_PAYMENT_SETTLED}\n\n", use_async, _stream)
        assert len(events) == 1
        e = events[0]
        assert e.event == "payment.settled"
        assert e.created_at == "2026-10-24T14:50:14.123+00:00"
        assert e.data["max_fee"] == 5
        assert e.data["service_fee"] == 1
        assert e.data["actual_fee"] == 3
        assert e.data["tx_number"] == 4
        assert e.data["failure_reason"] is None
        assert e.data["created_at"] == "2026-10-24T14:50:01Z"
        assert e.data["settled_at"] == "2026-10-24T14:50:14Z"

    def test_wallet_partial_payment_created(self, use_async):
        events = _events(f"data: {WALLET_PAYMENT_CREATED}\n\n", use_async, _stream)
        assert len(events) == 1
        e = events[0]
        assert e.event == "payment.created"
        assert e.created_at == "2026-10-24T14:50:01.456+00:00"
        assert e.data["status"] == "pending"
        assert (e.data["max_fee"], e.data["service_fee"]) == (5, 1)
        for missing in ("actual_fee", "preimage", "tx_number", "failure_reason", "settled_at"):
            assert e.data.get(missing) is None

    def test_wallet_invoice_events(self, use_async):
        sse = f"data: {WALLET_INVOICE_CREATED}\n\ndata: {WALLET_INVOICE_SETTLED}\n\n"
        events = _events(sse, use_async, _stream)
        assert [e.event for e in events] == ["invoice.created", "invoice.settled"]
        assert events[0].created_at == "2026-10-24T14:40:00.789+00:00"
        assert events[0].data["expires_at"] == "2026-10-24T15:40:00Z"
        assert events[1].created_at == "2026-10-24T14:41:30.5+00:00"
        assert events[1].data["tx_number"] == 4
        assert events[1].data["settled_at"] == "2026-10-24T14:41:30Z"

    def test_camel_case_payloads_still_decode(self, use_async):
        pay = 'event: settled\ndata: {"number":1,"status":"settled","amount":20,"maxFee":5,"serviceFee":1,"actualFee":3,"address":"bub@bub.gg","txNumber":4,"settledAt":"2026-10-24T14:50:14Z"}\n\n'
        p = _events(pay, use_async, _watch_payment)[0].data
        assert (p.max_fee, p.service_fee, p.actual_fee, p.tx_number) == (5, 1, 3, 4)
        assert p.settled_at == "2026-10-24T14:50:14Z"
        env = 'data: {"event":"payment.settled","createdAt":"2026-10-24T14:50:14.123+00:00","data":{"number":1,"actualFee":3}}\n\n'
        e = _events(env, use_async, _stream)[0]
        assert e.created_at == "2026-10-24T14:50:14.123+00:00"
        assert e.data == {"number": 1, "actual_fee": 3}

    def test_missing_fields_decode_to_none(self, use_async):
        events = _events('event: timeout\ndata: {"number":1,"status":"pending","amount":20}\n\n', use_async, _watch_payment)
        assert len(events) == 1
        p = events[0].data
        assert (p.number, p.status, p.amount) == (1, "pending", 20)
        assert p.max_fee is None
        assert p.service_fee is None
        assert p.address is None
        assert p.actual_fee is None

    @pytest.mark.parametrize("raw", ["{not json", "[1,2]"], ids=["invalid-json", "not-an-object"])
    def test_undecodable_watch_event_is_skipped(self, use_async, raw):
        body = f"event: settled\ndata: {raw}\n\nevent: settled\ndata: " + '{"number":1,"status":"settled","amount":20,"actual_fee":3}\n\n'
        events = _events(body, use_async, _watch_payment)
        assert len(events) == 1
        assert events[0].data.actual_fee == 3

    @pytest.mark.parametrize("raw", ["{not json", '"text"'], ids=["invalid-json", "not-an-object"])
    def test_undecodable_wallet_event_is_skipped(self, use_async, raw):
        body = f"data: {raw}\n\n" + 'data: {"event":"payment.settled","created_at":"2026-10-24T14:50:14Z","data":{"number":1}}\n\n'
        events = _events(body, use_async, _stream)
        assert len(events) == 1
        assert events[0].created_at == "2026-10-24T14:50:14Z"
