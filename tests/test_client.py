"""Tests for the LnBot client core: construction, headers, HTTP methods, error mapping."""

from __future__ import annotations

import pytest

import httpx

from lnbot import LnBot
from lnbot.errors import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    LnBotError,
    NotFoundError,
    UnauthorizedError,
)
from conftest import create_client


class TestClientConstruction:
    def test_default_base_url(self):
        transport = httpx.MockTransport(lambda r: httpx.Response(200))
        client = httpx.Client(transport=transport)
        ln = LnBot(api_key="k", http_client=client)
        assert ln._base_url == "https://api.ln.bot"

    def test_custom_base_url(self):
        transport = httpx.MockTransport(lambda r: httpx.Response(200))
        client = httpx.Client(transport=transport)
        ln = LnBot(api_key="k", base_url="https://custom.api.com/", http_client=client)
        assert ln._base_url == "https://custom.api.com"

    def test_trailing_slash_stripped(self):
        transport = httpx.MockTransport(lambda r: httpx.Response(200))
        client = httpx.Client(transport=transport)
        ln = LnBot(api_key="k", base_url="https://api.example.com///", http_client=client)
        assert not ln._base_url.endswith("/")

    def test_all_resources_initialized(self):
        transport = httpx.MockTransport(lambda r: httpx.Response(200))
        client = httpx.Client(transport=transport)
        ln = LnBot(api_key="k", http_client=client)
        assert ln.wallets is not None
        assert ln.keys is not None
        assert ln.invoices is not None
        assert ln.payments is not None
        assert ln.addresses is not None
        assert ln.transactions is not None
        assert ln.webhooks is not None
        assert ln.events is not None
        assert ln.backup is not None
        assert ln.restore is not None
        assert ln.l402 is not None

    def test_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("LNBOT_API_KEY", "env_key")
        transport = httpx.MockTransport(lambda r: httpx.Response(200))
        client = httpx.Client(transport=transport)
        ln = LnBot(http_client=client)
        assert ln._api_key == "env_key"

    def test_explicit_key_overrides_env(self, monkeypatch):
        monkeypatch.setenv("LNBOT_API_KEY", "env_key")
        transport = httpx.MockTransport(lambda r: httpx.Response(200))
        client = httpx.Client(transport=transport)
        ln = LnBot(api_key="explicit_key", http_client=client)
        assert ln._api_key == "explicit_key"

    def test_context_manager(self):
        transport = httpx.MockTransport(lambda r: httpx.Response(200))
        client = httpx.Client(transport=transport)
        with LnBot(api_key="k", http_client=client) as ln:
            assert ln is not None


class TestHeaders:
    def test_sends_authorization(self):
        ln, cap = create_client(json_body={"walletId": "w", "name": "n", "balance": 0, "onHold": 0, "available": 0})
        ln.wallets.current()
        assert cap.headers["authorization"] == "Bearer key_test"

    def test_omits_auth_when_no_key(self):
        from conftest import CapturedRequest
        import json

        captured = CapturedRequest()

        def handler(request: httpx.Request) -> httpx.Response:
            captured.method = request.method
            captured.url = request.url
            captured.headers = request.headers
            captured.content = request.content
            body = json.dumps({"walletId": "w", "name": "n", "balance": 0, "onHold": 0, "available": 0})
            return httpx.Response(200, content=body.encode(), headers={"content-type": "application/json"})

        transport = httpx.MockTransport(handler)
        client = httpx.Client(transport=transport)
        ln = LnBot(http_client=client)
        ln.wallets.current()
        assert "authorization" not in captured.headers

    def test_sends_accept_json(self):
        ln, cap = create_client(json_body={"walletId": "w", "name": "n", "balance": 0, "onHold": 0, "available": 0})
        ln.wallets.current()
        assert cap.headers["accept"] == "application/json"

    def test_sends_user_agent(self):
        ln, cap = create_client(json_body={"walletId": "w", "name": "n", "balance": 0, "onHold": 0, "available": 0})
        ln.wallets.current()
        assert cap.headers["user-agent"].startswith("lnbot-python/")

    def test_sends_content_type_for_post(self):
        ln, cap = create_client(json_body={"number": 1, "status": "pending", "amount": 100, "bolt11": "lnbc1..."})
        ln.invoices.create(amount=100)
        assert "application/json" in cap.headers["content-type"]


class TestHTTPMethods:
    def test_get(self):
        ln, cap = create_client(json_body={"walletId": "w", "name": "n", "balance": 0, "onHold": 0, "available": 0})
        ln.wallets.current()
        assert cap.method == "GET"

    def test_post(self):
        ln, cap = create_client(json_body={"number": 1, "status": "pending", "amount": 100, "bolt11": "lnbc1..."})
        ln.invoices.create(amount=100)
        assert cap.method == "POST"

    def test_patch(self):
        ln, cap = create_client(json_body={"walletId": "w", "name": "Renamed", "balance": 0, "onHold": 0, "available": 0})
        ln.wallets.update(name="Renamed")
        assert cap.method == "PATCH"

    def test_delete(self):
        ln, cap = create_client(status=200, json_body=None, content_type="text/plain")
        ln.webhooks.delete("wh_1")
        assert cap.method == "DELETE"


class TestRequestBody:
    def test_serializes_json(self):
        ln, cap = create_client(json_body={"number": 1, "status": "pending", "amount": 100, "bolt11": "lnbc1..."})
        ln.invoices.create(amount=100, memo="test memo")
        body = cap.json_body
        assert body["amount"] == 100
        assert body["memo"] == "test memo"

    def test_omits_none_values(self):
        ln, cap = create_client(json_body={"number": 1, "status": "pending", "amount": 100, "bolt11": "lnbc1..."})
        ln.invoices.create(amount=100)
        body = cap.json_body
        assert "memo" not in body
        assert "reference" not in body

    def test_converts_to_camel_case(self):
        ln, cap = create_client(json_body={
            "number": 1, "status": "pending", "amount": 50, "maxFee": 10, "serviceFee": 0, "address": "user@ln.bot",
        })
        ln.payments.create(target="user@ln.bot", idempotency_key="idem_1")
        body = cap.json_body
        assert "idempotencyKey" in body
        assert "idempotency_key" not in body


class TestResponseParsing:
    def test_parses_json_to_dataclass(self):
        ln, _ = create_client(json_body={"walletId": "wal_123", "name": "My Wallet", "balance": 1000, "onHold": 50, "available": 950})
        w = ln.wallets.current()
        assert w.wallet_id == "wal_123"
        assert w.name == "My Wallet"
        assert w.balance == 1000
        assert w.available == 950

    def test_converts_camel_to_snake(self):
        ln, _ = create_client(json_body={"walletId": "wal_1", "name": "n", "balance": 0, "onHold": 50, "available": 0})
        w = ln.wallets.current()
        assert w.on_hold == 50


class TestErrorMapping:
    @pytest.mark.parametrize(
        "status,exc_class",
        [
            (400, BadRequestError),
            (401, UnauthorizedError),
            (403, ForbiddenError),
            (404, NotFoundError),
            (409, ConflictError),
        ],
    )
    def test_raises_typed_error(self, status, exc_class):
        ln, _ = create_client(status=status, json_body={"message": "test error"})
        with pytest.raises(exc_class) as exc_info:
            ln.wallets.current()
        assert exc_info.value.status == status
        assert isinstance(exc_info.value, LnBotError)

    def test_unknown_status_raises_lnbot_error(self):
        ln, _ = create_client(status=500, json_body={"message": "server error"})
        with pytest.raises(LnBotError) as exc_info:
            ln.wallets.current()
        assert exc_info.value.status == 500

    def test_extracts_message_from_error(self):
        ln, _ = create_client(status=400, json_body={"message": "invalid amount"})
        with pytest.raises(BadRequestError, match="invalid amount"):
            ln.wallets.current()

    def test_extracts_error_field(self):
        ln, _ = create_client(status=400, json_body={"error": "bad input"})
        with pytest.raises(BadRequestError, match="bad input"):
            ln.wallets.current()
