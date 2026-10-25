"""Tests for all resource classes: correct paths, methods, request bodies, and response parsing."""

from __future__ import annotations

import asyncio

from lnbot import PaymentStage
from conftest import create_async_client, create_client


# ---------------------------------------------------------------------------
# Wallets (account-level)
# ---------------------------------------------------------------------------


class TestWallets:
    def test_create(self):
        ln, cap = create_client(json_body={
            "walletId": "wal_abc", "name": "Test", "address": "test@ln.bot",
        })
        creds = ln.wallets.create()
        assert cap.method == "POST"
        assert cap.path == "/v1/wallets"
        assert creds.wallet_id == "wal_abc"
        assert creds.name == "Test"
        assert creds.address == "test@ln.bot"

    def test_list(self):
        ln, cap = create_client(json_body=[
            {"walletId": "wal_1", "name": "Wallet 1", "createdAt": "2024-01-01"},
            {"walletId": "wal_2", "name": "Wallet 2"},
        ])
        wallets = ln.wallets.list()
        assert cap.method == "GET"
        assert cap.path == "/v1/wallets"
        assert len(wallets) == 2
        assert wallets[0].wallet_id == "wal_1"
        assert wallets[0].created_at == "2024-01-01"


# ---------------------------------------------------------------------------
# Wallet Scope
# ---------------------------------------------------------------------------


class TestWalletScope:
    def test_get(self):
        ln, cap = create_client(json_body={"walletId": "wal_1", "name": "My Wallet", "balance": 1000, "onHold": 50, "available": 950})
        w = ln.wallet("wal_1").get()
        assert cap.method == "GET"
        assert cap.path == "/v1/wallets/wal_1"
        assert w.name == "My Wallet"
        assert w.available == 950

    def test_update(self):
        ln, cap = create_client(json_body={"walletId": "wal_1", "name": "Renamed", "balance": 0, "onHold": 0, "available": 0})
        w = ln.wallet("wal_1").update(name="Renamed")
        assert cap.method == "PATCH"
        assert cap.path == "/v1/wallets/wal_1"
        assert w.name == "Renamed"


# ---------------------------------------------------------------------------
# Wallet Key
# ---------------------------------------------------------------------------


class TestWalletKey:
    def test_create(self):
        ln, cap = create_client(json_body={"key": "wk_abc", "hint": "wk_***abc"})
        k = ln.wallet("wal_1").key.create()
        assert cap.method == "POST"
        assert cap.path == "/v1/wallets/wal_1/key"
        assert k.key == "wk_abc"

    def test_get(self):
        ln, cap = create_client(json_body={"hint": "wk_***abc", "createdAt": "2024-01-01"})
        info = ln.wallet("wal_1").key.get()
        assert cap.method == "GET"
        assert cap.path == "/v1/wallets/wal_1/key"
        assert info.hint == "wk_***abc"

    def test_delete(self):
        ln, cap = create_client(status=200, json_body=None, content_type="text/plain")
        ln.wallet("wal_1").key.delete()
        assert cap.method == "DELETE"
        assert cap.path == "/v1/wallets/wal_1/key"

    def test_rotate(self):
        ln, cap = create_client(json_body={"key": "wk_new", "hint": "wk_***new"})
        k = ln.wallet("wal_1").key.rotate()
        assert cap.method == "POST"
        assert cap.path == "/v1/wallets/wal_1/key/rotate"
        assert k.key == "wk_new"


# ---------------------------------------------------------------------------
# Keys (account-level)
# ---------------------------------------------------------------------------


class TestKeys:
    def test_rotate(self):
        ln, cap = create_client(json_body={"key": "pk_new", "name": "primary"})
        k = ln.keys.rotate(0)
        assert cap.method == "POST"
        assert cap.path == "/v1/keys/0/rotate"
        assert k.key == "pk_new"
        assert k.name == "primary"


# ---------------------------------------------------------------------------
# Invoices (wallet-scoped)
# ---------------------------------------------------------------------------


class TestInvoices:
    def test_create(self):
        ln, cap = create_client(json_body={"number": 1, "status": "pending", "amount": 100, "bolt11": "lnbc1..."})
        inv = ln.wallet("wal_1").invoices.create(amount=100, memo="test")
        assert cap.method == "POST"
        assert cap.path == "/v1/wallets/wal_1/invoices"
        assert inv.number == 1
        assert inv.bolt11 == "lnbc1..."
        assert cap.json_body["memo"] == "test"

    def test_list(self):
        ln, cap = create_client(json_body=[
            {"number": 1, "status": "settled", "amount": 100, "bolt11": "lnbc1..."},
            {"number": 2, "status": "pending", "amount": 200, "bolt11": "lnbc2..."},
        ])
        invs = ln.wallet("wal_1").invoices.list(limit=10, after=0)
        assert cap.method == "GET"
        assert cap.path == "/v1/wallets/wal_1/invoices"
        assert "limit=10" in cap.query
        assert "after=0" in cap.query
        assert len(invs) == 2

    def test_list_no_params(self):
        ln, cap = create_client(json_body=[])
        ln.wallet("wal_1").invoices.list()
        assert cap.query == ""

    def test_get_by_number(self):
        ln, cap = create_client(json_body={"number": 42, "status": "settled", "amount": 500, "bolt11": "lnbc42..."})
        inv = ln.wallet("wal_1").invoices.get(42)
        assert cap.path == "/v1/wallets/wal_1/invoices/42"
        assert inv.number == 42

    def test_get_by_hash(self):
        ln, cap = create_client(json_body={"number": 1, "status": "settled", "amount": 100, "bolt11": "lnbc1..."})
        ln.wallet("wal_1").invoices.get("abc123")
        assert cap.path == "/v1/wallets/wal_1/invoices/abc123"


# ---------------------------------------------------------------------------
# Public Invoices
# ---------------------------------------------------------------------------


class TestPublicInvoices:
    def test_create_for_wallet(self):
        ln, cap = create_client(json_body={"bolt11": "lnbc1...", "amount": 100})
        inv = ln.invoices.create_for_wallet(wallet_id="wal_abc", amount=100)
        assert cap.method == "POST"
        assert cap.path == "/v1/invoices/for-wallet"
        assert inv.bolt11 == "lnbc1..."
        assert cap.json_body["walletId"] == "wal_abc"

    def test_create_for_address(self):
        ln, cap = create_client(json_body={"bolt11": "lnbc1...", "amount": 200})
        inv = ln.invoices.create_for_address(address="user@ln.bot", amount=200)
        assert cap.path == "/v1/invoices/for-address"
        assert inv.amount == 200
        assert cap.json_body["address"] == "user@ln.bot"


# ---------------------------------------------------------------------------
# Payments (wallet-scoped)
# ---------------------------------------------------------------------------


RESOLVE_BOLT11 = {
    "type": "bolt11", "min": None, "max": None, "fixed": True, "amount": 250000,
    "internal": False, "networkFeeEstimate": 700, "serviceFee": 625, "maxFee": 805,
    "total": 251325, "maxSendable": None, "feeWarning": None,
}

RESOLVE_ADDRESS_NO_AMOUNT = {
    "type": "lightning_address", "min": 1, "max": 100000, "fixed": False, "amount": None,
    "internal": False, "networkFeeEstimate": None, "serviceFee": None, "maxFee": None,
    "total": None, "maxSendable": 49650, "feeWarning": None,
}


class TestPayments:
    def test_create(self):
        ln, cap = create_client(json_body={
            "number": 1, "status": "pending", "amount": 5000, "maxFee": 17, "serviceFee": 13,
            "actualFee": None, "address": "user@example.com", "reference": None, "preimage": None,
            "txNumber": None, "failureReason": None, "createdAt": "2026-10-01T00:00:00Z", "settledAt": None,
        })
        p = ln.wallet("wal_1").payments.create(target="user@example.com", amount=5000)
        assert cap.method == "POST"
        assert cap.path == "/v1/wallets/wal_1/payments"
        assert p.number == 1
        assert p.address == "user@example.com"
        assert p.max_fee == 17
        assert p.service_fee == 13
        assert p.actual_fee is None

    def test_create_omits_max_fee_by_default(self):
        ln, cap = create_client(json_body={
            "number": 1, "status": "pending", "amount": 5000, "maxFee": 17, "serviceFee": 13, "address": "user@example.com",
        })
        ln.wallet("wal_1").payments.create(target="user@example.com", amount=5000)
        assert cap.json_body == {"target": "user@example.com", "amount": 5000}

    def test_create_sends_max_fee(self):
        ln, cap = create_client(json_body={
            "number": 1, "status": "pending", "amount": 5000, "maxFee": 17, "serviceFee": 13, "address": "user@example.com",
        })
        ln.wallet("wal_1").payments.create(target="user@example.com", amount=5000, max_fee=100)
        assert cap.json_body["maxFee"] == 100

    def test_list(self):
        ln, cap = create_client(json_body=[
            {"number": 1, "status": "settled", "amount": 50, "maxFee": 10, "serviceFee": 0, "address": "user@ln.bot"},
        ])
        ps = ln.wallet("wal_1").payments.list(limit=5)
        assert cap.path == "/v1/wallets/wal_1/payments"
        assert "limit=5" in cap.query
        assert len(ps) == 1

    def test_get_by_number(self):
        ln, cap = create_client(json_body={
            "number": 7, "status": "settled", "amount": 100, "maxFee": 10, "serviceFee": 0, "address": "bob@ln.bot",
        })
        p = ln.wallet("wal_1").payments.get(7)
        assert cap.path == "/v1/wallets/wal_1/payments/7"
        assert p.number == 7

    def test_get_by_hash(self):
        ln, cap = create_client(json_body={
            "number": 1, "status": "settled", "amount": 100, "maxFee": 10, "serviceFee": 0, "address": "a@b.com",
        })
        ln.wallet("wal_1").payments.get("hash456")
        assert cap.path == "/v1/wallets/wal_1/payments/hash456"

    def test_resolve(self):
        ln, cap = create_client(json_body=RESOLVE_ADDRESS_NO_AMOUNT)
        r = ln.wallet("wal_1").payments.resolve(target="user@ln.bot")
        assert cap.method == "GET"
        assert cap.path == "/v1/wallets/wal_1/payments/resolve"
        assert "target=user%40ln.bot" in cap.query
        assert r.type == "lightning_address"

    def test_resolve_omits_amount_by_default(self):
        ln, cap = create_client(json_body=RESOLVE_ADDRESS_NO_AMOUNT)
        ln.wallet("wal_1").payments.resolve(target="user@example.com")
        assert cap.query == "target=user%40example.com"

    def test_resolve_sends_amount(self):
        ln, cap = create_client(json_body=RESOLVE_BOLT11)
        ln.wallet("wal_1").payments.resolve(target="user@example.com", amount=250000)
        assert cap.path == "/v1/wallets/wal_1/payments/resolve"
        assert "target=user%40example.com" in cap.query
        assert "amount=250000" in cap.query

    def test_resolve_parses_all_fields(self):
        ln, _ = create_client(json_body=RESOLVE_BOLT11)
        r = ln.wallet("wal_1").payments.resolve(target="lnbc2500u1...")
        assert r.type == "bolt11"
        assert r.min is None
        assert r.max is None
        assert r.fixed is True
        assert r.amount == 250000
        assert r.internal is False
        assert r.network_fee_estimate == 700
        assert r.service_fee == 625
        assert r.max_fee == 805
        assert r.total == 251325
        assert r.max_sendable is None
        assert r.fee_warning is None

    def test_resolve_address_without_amount_returns_max_sendable(self):
        ln, cap = create_client(json_body=RESOLVE_ADDRESS_NO_AMOUNT)
        r = ln.wallet("wal_1").payments.resolve(target="user@example.com")
        assert "amount" not in cap.query
        assert r.type == "lightning_address"
        assert r.min == 1
        assert r.max == 100000
        assert r.amount is None
        assert r.max_sendable == 49650
        assert r.network_fee_estimate is None
        assert r.service_fee is None
        assert r.max_fee is None
        assert r.total is None

    def test_resolve_parses_internal_and_fee_warning(self):
        ln, _ = create_client(json_body={
            "type": "lightning_address", "min": 1, "max": 100000, "fixed": False, "amount": 1000,
            "internal": True, "networkFeeEstimate": 0, "serviceFee": 0, "maxFee": None,
            "total": 1000, "maxSendable": None, "feeWarning": "Network fee is unusually high.",
        })
        r = ln.wallet("wal_1").payments.resolve(target="bob@ln.bot", amount=1000)
        assert r.internal is True
        assert r.network_fee_estimate == 0
        assert r.service_fee == 0
        assert r.total == 1000
        assert r.fee_warning == "Network fee is unusually high."

    def test_resolve_parses_legacy_response(self):
        ln, _ = create_client(json_body={"type": "lightning_address", "min": 1, "max": 100000, "fixed": False})
        r = ln.wallet("wal_1").payments.resolve(target="user@ln.bot")
        assert r.internal is False
        assert r.max_sendable is None


class TestAsyncPayments:
    def test_resolve_omits_amount_by_default(self):
        ln, cap = create_async_client(json_body=RESOLVE_ADDRESS_NO_AMOUNT)
        r = asyncio.run(ln.wallet("wal_1").payments.resolve(target="user@example.com"))
        assert cap.method == "GET"
        assert cap.path == "/v1/wallets/wal_1/payments/resolve"
        assert cap.query == "target=user%40example.com"
        assert r.max_sendable == 49650

    def test_resolve_sends_amount(self):
        ln, cap = create_async_client(json_body=RESOLVE_BOLT11)
        r = asyncio.run(ln.wallet("wal_1").payments.resolve(target="user@example.com", amount=250000))
        assert "target=user%40example.com" in cap.query
        assert "amount=250000" in cap.query
        assert r.network_fee_estimate == 700
        assert r.total == 251325

    def test_create_omits_max_fee_by_default(self):
        ln, cap = create_async_client(json_body={
            "number": 1, "status": "pending", "amount": 5000, "maxFee": 17, "serviceFee": 13, "address": "user@example.com",
        })
        asyncio.run(ln.wallet("wal_1").payments.create(target="user@example.com", amount=5000))
        assert cap.json_body == {"target": "user@example.com", "amount": 5000}


# ---------------------------------------------------------------------------
# Payment stages: stage, statusDetail, retryUntil
# ---------------------------------------------------------------------------

PAYMENT_RETRYING = {
    "number": 4, "status": "pending", "amount": 1000, "maxFee": 20, "serviceFee": 3, "actualFee": None,
    "address": "lnbc10u1p...", "reference": None, "preimage": None, "txNumber": None, "failureReason": None,
    "createdAt": "2026-10-25T14:33:53+00:00", "settledAt": None, "stage": "retrying",
    "statusDetail": "Not sent yet; retrying for a few minutes. If it still can't be sent, it fails and the funds are released.",
    "retryUntil": "2026-10-25T14:43:53+00:00",
}

PAYMENT_WITHOUT_STAGE = {
    "number": 3, "status": "settled", "amount": 500, "maxFee": 20, "serviceFee": 1, "actualFee": 2,
    "address": "x4k7m2@ln.bot", "reference": None, "preimage": "9f2c...", "txNumber": 12, "failureReason": None,
    "createdAt": "2026-10-25T14:30:00+00:00", "settledAt": "2026-10-25T14:30:01+00:00",
}

PAYMENT_UNKNOWN_STAGE = {
    "number": 5, "status": "processing", "amount": 1000, "maxFee": 20, "serviceFee": 3, "actualFee": None,
    "address": "x4k7m2@ln.bot", "reference": None, "preimage": None, "txNumber": None, "failureReason": None,
    "createdAt": "2026-10-25T14:35:00+00:00", "settledAt": None, "stage": "teleporting",
    "statusDetail": "Moving through a new kind of route.", "retryUntil": None,
}


class TestPaymentStages:
    def test_get_retrying(self):
        ln, cap = create_client(json_body=PAYMENT_RETRYING)
        p = ln.wallet("wal_1").payments.get(4)
        assert cap.path == "/v1/wallets/wal_1/payments/4"
        assert p.status == "pending"
        assert p.stage == PaymentStage.RETRYING
        assert p.status_detail == PAYMENT_RETRYING["statusDetail"]
        assert p.retry_until == "2026-10-25T14:43:53+00:00"

    def test_create_returns_stage(self):
        ln, _ = create_client(json_body=PAYMENT_RETRYING)
        p = ln.wallet("wal_1").payments.create(target="lnbc10u1p...")
        assert p.stage == "retrying"
        assert p.retry_until == "2026-10-25T14:43:53+00:00"

    def test_list_returns_stage(self):
        ln, _ = create_client(json_body=[PAYMENT_RETRYING, PAYMENT_UNKNOWN_STAGE, PAYMENT_WITHOUT_STAGE])
        ps = ln.wallet("wal_1").payments.list()
        assert [p.stage for p in ps] == ["retrying", "teleporting", None]

    def test_without_new_fields(self):
        ln, _ = create_client(json_body=PAYMENT_WITHOUT_STAGE)
        p = ln.wallet("wal_1").payments.get(3)
        assert (p.number, p.status, p.actual_fee, p.tx_number) == (3, "settled", 2, 12)
        assert p.stage is None
        assert p.status_detail is None
        assert p.retry_until is None

    def test_unknown_stage(self):
        ln, _ = create_client(json_body=PAYMENT_UNKNOWN_STAGE)
        p = ln.wallet("wal_1").payments.get(5)
        assert p.stage == "teleporting"
        assert p.status == "processing"
        assert p.status_detail == "Moving through a new kind of route."
        assert p.retry_until is None

    def test_async_get(self):
        ln, _ = create_async_client(json_body=PAYMENT_UNKNOWN_STAGE)
        p = asyncio.run(ln.wallet("wal_1").payments.get(5))
        assert (p.stage, p.status) == ("teleporting", "processing")

    def test_known_stages(self):
        assert [PaymentStage.QUEUED, PaymentStage.RETRYING, PaymentStage.SENDING, PaymentStage.IN_FLIGHT,
                PaymentStage.CONFIRMING, PaymentStage.ON_HOLD, PaymentStage.SETTLED, PaymentStage.FAILED] == [
            "queued", "retrying", "sending", "in_flight", "confirming", "on_hold", "settled", "failed",
        ]


# ---------------------------------------------------------------------------
# Addresses (wallet-scoped)
# ---------------------------------------------------------------------------


class TestAddresses:
    def test_create(self):
        ln, cap = create_client(json_body={"address": "user@ln.bot", "generated": False, "cost": 0})
        a = ln.wallet("wal_1").addresses.create(address="user@ln.bot")
        assert cap.method == "POST"
        assert cap.path == "/v1/wallets/wal_1/addresses"
        assert a.address == "user@ln.bot"

    def test_list(self):
        ln, cap = create_client(json_body=[
            {"address": "a@ln.bot", "generated": True, "cost": 0},
            {"address": "b@ln.bot", "generated": False, "cost": 100},
        ])
        addrs = ln.wallet("wal_1").addresses.list()
        assert cap.path == "/v1/wallets/wal_1/addresses"
        assert len(addrs) == 2
        assert addrs[0].generated is True

    def test_delete(self):
        ln, cap = create_client(status=200, json_body=None, content_type="text/plain")
        ln.wallet("wal_1").addresses.delete("user@ln.bot")
        assert cap.method == "DELETE"
        assert "/v1/wallets/wal_1/addresses/user@ln.bot" in cap.path

    def test_transfer(self):
        ln, cap = create_client(json_body={"address": "user@ln.bot", "transferredTo": "wal_target"})
        tr = ln.wallet("wal_1").addresses.transfer("user@ln.bot", target_wallet_key="pk_target")
        assert cap.method == "POST"
        assert "/v1/wallets/wal_1/addresses/user@ln.bot/transfer" in cap.path
        assert tr.transferred_to == "wal_target"
        assert cap.json_body["targetWalletKey"] == "pk_target"


# ---------------------------------------------------------------------------
# Transactions (wallet-scoped)
# ---------------------------------------------------------------------------


class TestTransactions:
    def test_list(self):
        ln, cap = create_client(json_body=[
            {"number": 1, "type": "credit", "amount": 100, "balanceAfter": 100, "networkFee": 0, "serviceFee": 0},
        ])
        txs = ln.wallet("wal_1").transactions.list(limit=20, after=0)
        assert cap.path == "/v1/wallets/wal_1/transactions"
        assert "limit=20" in cap.query
        assert "after=0" in cap.query
        assert len(txs) == 1
        assert txs[0].type == "credit"

    def test_list_no_params(self):
        ln, cap = create_client(json_body=[])
        ln.wallet("wal_1").transactions.list()
        assert cap.query == ""


# ---------------------------------------------------------------------------
# Webhooks (wallet-scoped)
# ---------------------------------------------------------------------------


class TestWebhooks:
    def test_create(self):
        ln, cap = create_client(json_body={"id": "wh_1", "url": "https://example.com/hook", "secret": "sec_abc"})
        wh = ln.wallet("wal_1").webhooks.create(url="https://example.com/hook")
        assert cap.method == "POST"
        assert cap.path == "/v1/wallets/wal_1/webhooks"
        assert wh.secret == "sec_abc"

    def test_list(self):
        ln, cap = create_client(json_body=[{"id": "wh_1", "url": "https://example.com/hook", "active": True}])
        whs = ln.wallet("wal_1").webhooks.list()
        assert cap.path == "/v1/wallets/wal_1/webhooks"
        assert len(whs) == 1
        assert whs[0].active is True

    def test_delete(self):
        ln, cap = create_client(status=200, json_body=None, content_type="text/plain")
        ln.wallet("wal_1").webhooks.delete("wh_1")
        assert cap.method == "DELETE"
        assert cap.path == "/v1/wallets/wal_1/webhooks/wh_1"


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------


class TestBackup:
    def test_recovery(self):
        ln, cap = create_client(json_body={"passphrase": "word1 word2 word3"})
        r = ln.backup.recovery()
        assert cap.method == "POST"
        assert cap.path == "/v1/backup/recovery"
        assert r.passphrase == "word1 word2 word3"

    def test_passkey_begin(self):
        ln, cap = create_client(json_body={"sessionId": "sess_1", "options": {"challenge": "abc"}})
        ch = ln.backup.passkey_begin()
        assert cap.path == "/v1/backup/passkey/begin"
        assert ch.session_id == "sess_1"

    def test_passkey_complete(self):
        ln, cap = create_client(status=204, json_body=None)
        ln.backup.passkey_complete(session_id="sess_1", attestation={"id": "cred_1"})
        assert cap.method == "POST"
        assert cap.path == "/v1/backup/passkey/complete"
        assert cap.json_body["sessionId"] == "sess_1"


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------


class TestRestore:
    def test_recovery(self):
        ln, cap = create_client(json_body={
            "walletId": "wal_1", "name": "Restored", "primaryKey": "pk_1", "secondaryKey": "sk_1",
        })
        w = ln.restore.recovery(passphrase="word1 word2 word3")
        assert cap.method == "POST"
        assert cap.path == "/v1/restore/recovery"
        assert w.wallet_id == "wal_1"

    def test_passkey_begin(self):
        ln, cap = create_client(json_body={"sessionId": "sess_2", "options": {"challenge": "xyz"}})
        ch = ln.restore.passkey_begin()
        assert cap.path == "/v1/restore/passkey/begin"
        assert ch.session_id == "sess_2"

    def test_passkey_complete(self):
        ln, cap = create_client(json_body={
            "walletId": "wal_1", "name": "Restored", "primaryKey": "pk_1", "secondaryKey": "sk_1",
        })
        w = ln.restore.passkey_complete(session_id="sess_2", assertion={"id": "cred_1"})
        assert cap.method == "POST"
        assert cap.path == "/v1/restore/passkey/complete"
        assert w.primary_key == "pk_1"


# ---------------------------------------------------------------------------
# L402 (wallet-scoped)
# ---------------------------------------------------------------------------


class TestL402:
    def test_create_challenge(self):
        ln, cap = create_client(json_body={
            "macaroon": "mac_abc", "invoice": "lnbc1...", "paymentHash": "hash_1",
            "expiresAt": "2024-01-01T00:00:00Z", "wwwAuthenticate": "L402 mac:inv",
        })
        ch = ln.wallet("wal_1").l402.create_challenge(amount=100, caveats=["service=api"])
        assert cap.method == "POST"
        assert cap.path == "/v1/wallets/wal_1/l402/challenges"
        assert ch.macaroon == "mac_abc"
        assert ch.www_authenticate == "L402 mac:inv"

    def test_verify(self):
        ln, cap = create_client(json_body={"valid": True, "paymentHash": "hash_1", "caveats": ["service=api"]})
        resp = ln.wallet("wal_1").l402.verify(authorization="L402 token:preimage")
        assert cap.path == "/v1/wallets/wal_1/l402/verify"
        assert resp.valid is True

    def test_pay(self):
        ln, cap = create_client(json_body={
            "authorization": "L402 token:preimage", "paymentHash": "hash_1",
            "preimage": "pre_1", "amount": 100, "fee": 1, "paymentNumber": 1, "status": "settled",
        })
        resp = ln.wallet("wal_1").l402.pay(www_authenticate="L402 mac:inv")
        assert cap.path == "/v1/wallets/wal_1/l402/pay"
        assert resp.status == "settled"
        assert resp.amount == 100
        assert resp.fee == 1
        assert "maxFee" not in cap.json_body

    def test_pay_sends_max_fee(self):
        ln, cap = create_client(json_body={
            "authorization": None, "paymentHash": "hash_1", "preimage": None,
            "amount": 100, "fee": None, "paymentNumber": 1, "status": "pending",
        })
        resp = ln.wallet("wal_1").l402.pay(www_authenticate="L402 mac:inv", max_fee=50, wait=False)
        assert cap.json_body["maxFee"] == 50
        assert resp.fee is None
