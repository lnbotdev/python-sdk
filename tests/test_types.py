"""Tests for data type conversion and parsing utilities."""

from __future__ import annotations

import pytest

from lnbot.types import (
    InvoiceResponse,
    PaymentResponse,
    ResolveTargetResponse,
    WalletResponse,
    _to_camel,
    _to_snake,
    from_camel,
    parse,
    parse_event_data,
    snake_keys,
    to_camel,
)


class TestToCamel:
    @pytest.mark.parametrize(
        "input_,expected",
        [
            ("wallet_id", "walletId"),
            ("name", "name"),
            ("on_hold", "onHold"),
            ("recovery_passphrase", "recoveryPassphrase"),
        ],
    )
    def test_converts(self, input_, expected):
        assert _to_camel(input_) == expected


class TestToSnake:
    @pytest.mark.parametrize(
        "input_,expected",
        [
            ("walletId", "wallet_id"),
            ("name", "name"),
            ("onHold", "on_hold"),
            ("recoveryPassphrase", "recovery_passphrase"),
        ],
    )
    def test_converts(self, input_, expected):
        assert _to_snake(input_) == expected


class TestToCamelDict:
    def test_converts_keys(self):
        result = to_camel({"wallet_id": "wal_1", "amount": 100})
        assert result == {"walletId": "wal_1", "amount": 100}

    def test_filters_none_values(self):
        result = to_camel({"amount": 100, "memo": None, "reference": None})
        assert result == {"amount": 100}
        assert "memo" not in result
        assert "reference" not in result


class TestFromCamel:
    def test_converts_keys(self):
        result = from_camel({"walletId": "wal_1", "onHold": 50})
        assert result == {"wallet_id": "wal_1", "on_hold": 50}


class TestParse:
    def test_parses_wallet(self):
        data = {"walletId": "wal_1", "name": "Test", "balance": 1000, "onHold": 50, "available": 950}
        w = parse(WalletResponse, data)
        assert w.wallet_id == "wal_1"
        assert w.name == "Test"
        assert w.balance == 1000
        assert w.on_hold == 50
        assert w.available == 950

    def test_ignores_unknown_fields(self):
        data = {"walletId": "wal_1", "name": "Test", "balance": 0, "onHold": 0, "available": 0, "extra": "ignored"}
        w = parse(WalletResponse, data)
        assert w.wallet_id == "wal_1"

    def test_parses_optional_fields(self):
        data = {"number": 1, "status": "settled", "amount": 100, "bolt11": "lnbc1...", "memo": "test"}
        inv = parse(InvoiceResponse, data)
        assert inv.memo == "test"
        assert inv.reference is None


class TestSnakeKeys:
    def test_snake_case_passes_through(self):
        data = {"max_fee": 5, "tx_number": 4, "created_at": "t"}
        assert snake_keys(data) == data

    def test_converts_camel_case_recursively(self):
        data = {"event": "payment.settled", "createdAt": "t", "data": {"maxFee": 5, "items": [{"txNumber": 4}]}}
        assert snake_keys(data) == {"event": "payment.settled", "created_at": "t", "data": {"max_fee": 5, "items": [{"tx_number": 4}]}}


class TestParseEventData:
    def test_parses_snake_case(self):
        inv = parse_event_data(InvoiceResponse, {"number": 1, "status": "settled", "amount": 100, "bolt11": "lnbc1...", "tx_number": 4, "settled_at": "t"})
        assert inv.tx_number == 4
        assert inv.settled_at == "t"

    def test_missing_required_fields_become_none(self):
        p = parse_event_data(PaymentResponse, {"number": 1, "status": "pending", "amount": 20})
        assert p.max_fee is None
        assert p.address is None

    def test_keeps_field_defaults(self):
        r = parse_event_data(ResolveTargetResponse, {"type": "bolt11"})
        assert r.internal is False
