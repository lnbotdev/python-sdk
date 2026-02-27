"""Tests for all resource classes: correct paths, methods, request bodies, and response parsing."""

from __future__ import annotations

from conftest import create_client


# ---------------------------------------------------------------------------
# Wallets
# ---------------------------------------------------------------------------


class TestWallets:
    def test_create(self):
        ln, cap = create_client(json_body={
            "walletId": "wal_abc", "primaryKey": "pk_1", "secondaryKey": "sk_1",
            "name": "Test", "address": "test@ln.bot", "recoveryPassphrase": "word1 word2",
        })
        creds = ln.wallets.create(name="Test")
        assert cap.method == "POST"
        assert cap.path == "/v1/wallets"
        assert creds.wallet_id == "wal_abc"
        assert creds.primary_key == "pk_1"
        assert cap.json_body["name"] == "Test"

    def test_current(self):
        ln, cap = create_client(json_body={"walletId": "wal_1", "name": "My Wallet", "balance": 1000, "onHold": 50, "available": 950})
        w = ln.wallets.current()
        assert cap.method == "GET"
        assert cap.path == "/v1/wallets/current"
        assert w.name == "My Wallet"
        assert w.available == 950

    def test_update(self):
        ln, cap = create_client(json_body={"walletId": "wal_1", "name": "Renamed", "balance": 0, "onHold": 0, "available": 0})
        w = ln.wallets.update(name="Renamed")
        assert cap.method == "PATCH"
        assert cap.path == "/v1/wallets/current"
        assert w.name == "Renamed"


# ---------------------------------------------------------------------------
# Keys
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
# Invoices
# ---------------------------------------------------------------------------


class TestInvoices:
    def test_create(self):
        ln, cap = create_client(json_body={"number": 1, "status": "pending", "amount": 100, "bolt11": "lnbc1..."})
        inv = ln.invoices.create(amount=100, memo="test")
        assert cap.method == "POST"
        assert cap.path == "/v1/invoices"
        assert inv.number == 1
        assert inv.bolt11 == "lnbc1..."
        assert cap.json_body["memo"] == "test"

    def test_list(self):
        ln, cap = create_client(json_body=[
            {"number": 1, "status": "settled", "amount": 100, "bolt11": "lnbc1..."},
            {"number": 2, "status": "pending", "amount": 200, "bolt11": "lnbc2..."},
        ])
        invs = ln.invoices.list(limit=10, after=0)
        assert cap.method == "GET"
        assert cap.path == "/v1/invoices"
        assert "limit=10" in cap.query
        assert "after=0" in cap.query
        assert len(invs) == 2
        assert invs[0].amount == 100

    def test_list_no_params(self):
        ln, cap = create_client(json_body=[])
        ln.invoices.list()
        assert cap.query == ""

    def test_get_by_number(self):
        ln, cap = create_client(json_body={"number": 42, "status": "settled", "amount": 500, "bolt11": "lnbc42..."})
        inv = ln.invoices.get(42)
        assert cap.path == "/v1/invoices/42"
        assert inv.number == 42

    def test_get_by_hash(self):
        ln, cap = create_client(json_body={"number": 1, "status": "settled", "amount": 100, "bolt11": "lnbc1..."})
        ln.invoices.get("abc123")
        assert cap.path == "/v1/invoices/abc123"

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
# Payments
# ---------------------------------------------------------------------------


class TestPayments:
    def test_create(self):
        ln, cap = create_client(json_body={
            "number": 1, "status": "pending", "amount": 50, "maxFee": 10,
            "serviceFee": 0, "address": "user@ln.bot",
        })
        p = ln.payments.create(target="user@ln.bot", amount=50)
        assert cap.method == "POST"
        assert cap.path == "/v1/payments"
        assert p.number == 1
        assert p.address == "user@ln.bot"

    def test_list(self):
        ln, cap = create_client(json_body=[
            {"number": 1, "status": "settled", "amount": 50, "maxFee": 10, "serviceFee": 0, "address": "user@ln.bot"},
        ])
        ps = ln.payments.list(limit=5)
        assert cap.path == "/v1/payments"
        assert "limit=5" in cap.query
        assert len(ps) == 1

    def test_get_by_number(self):
        ln, cap = create_client(json_body={
            "number": 7, "status": "settled", "amount": 100, "maxFee": 10, "serviceFee": 0, "address": "bob@ln.bot",
        })
        p = ln.payments.get(7)
        assert cap.path == "/v1/payments/7"
        assert p.number == 7

    def test_get_by_hash(self):
        ln, cap = create_client(json_body={
            "number": 1, "status": "settled", "amount": 100, "maxFee": 10, "serviceFee": 0, "address": "a@b.com",
        })
        ln.payments.get("hash456")
        assert cap.path == "/v1/payments/hash456"


# ---------------------------------------------------------------------------
# Addresses
# ---------------------------------------------------------------------------


class TestAddresses:
    def test_create(self):
        ln, cap = create_client(json_body={"address": "user@ln.bot", "generated": False, "cost": 0})
        a = ln.addresses.create(address="user@ln.bot")
        assert cap.method == "POST"
        assert cap.path == "/v1/addresses"
        assert a.address == "user@ln.bot"

    def test_list(self):
        ln, cap = create_client(json_body=[
            {"address": "a@ln.bot", "generated": True, "cost": 0},
            {"address": "b@ln.bot", "generated": False, "cost": 100},
        ])
        addrs = ln.addresses.list()
        assert cap.path == "/v1/addresses"
        assert len(addrs) == 2
        assert addrs[0].generated is True

    def test_delete(self):
        ln, cap = create_client(status=200, json_body=None, content_type="text/plain")
        ln.addresses.delete("user@ln.bot")
        assert cap.method == "DELETE"
        assert "/v1/addresses/user@ln.bot" in cap.path

    def test_transfer(self):
        ln, cap = create_client(json_body={"address": "user@ln.bot", "transferredTo": "wal_target"})
        tr = ln.addresses.transfer("user@ln.bot", target_wallet_key="pk_target")
        assert cap.method == "POST"
        assert "/v1/addresses/user@ln.bot/transfer" in cap.path
        assert tr.transferred_to == "wal_target"
        assert cap.json_body["targetWalletKey"] == "pk_target"


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------


class TestTransactions:
    def test_list(self):
        ln, cap = create_client(json_body=[
            {"number": 1, "type": "credit", "amount": 100, "balanceAfter": 100, "networkFee": 0, "serviceFee": 0},
        ])
        txs = ln.transactions.list(limit=20, after=0)
        assert cap.path == "/v1/transactions"
        assert "limit=20" in cap.query
        assert "after=0" in cap.query
        assert len(txs) == 1
        assert txs[0].type == "credit"

    def test_list_no_params(self):
        ln, cap = create_client(json_body=[])
        ln.transactions.list()
        assert cap.query == ""


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------


class TestWebhooks:
    def test_create(self):
        ln, cap = create_client(json_body={"id": "wh_1", "url": "https://example.com/hook", "secret": "sec_abc"})
        wh = ln.webhooks.create(url="https://example.com/hook")
        assert cap.method == "POST"
        assert cap.path == "/v1/webhooks"
        assert wh.secret == "sec_abc"

    def test_list(self):
        ln, cap = create_client(json_body=[{"id": "wh_1", "url": "https://example.com/hook", "active": True}])
        whs = ln.webhooks.list()
        assert cap.path == "/v1/webhooks"
        assert len(whs) == 1
        assert whs[0].active is True

    def test_delete(self):
        ln, cap = create_client(status=200, json_body=None, content_type="text/plain")
        ln.webhooks.delete("wh_1")
        assert cap.method == "DELETE"
        assert cap.path == "/v1/webhooks/wh_1"


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
# L402
# ---------------------------------------------------------------------------


class TestL402:
    def test_create_challenge(self):
        ln, cap = create_client(json_body={
            "macaroon": "mac_abc", "invoice": "lnbc1...", "paymentHash": "hash_1",
            "expiresAt": "2024-01-01T00:00:00Z", "wwwAuthenticate": "L402 mac:inv",
        })
        ch = ln.l402.create_challenge(amount=100, caveats=["service=api"])
        assert cap.method == "POST"
        assert cap.path == "/v1/l402/challenges"
        assert ch.macaroon == "mac_abc"
        assert ch.www_authenticate == "L402 mac:inv"

    def test_verify(self):
        ln, cap = create_client(json_body={"valid": True, "paymentHash": "hash_1", "caveats": ["service=api"]})
        resp = ln.l402.verify(authorization="L402 token:preimage")
        assert cap.path == "/v1/l402/verify"
        assert resp.valid is True

    def test_pay(self):
        ln, cap = create_client(json_body={
            "authorization": "L402 token:preimage", "paymentHash": "hash_1",
            "preimage": "pre_1", "amount": 100, "fee": 1, "paymentNumber": 1, "status": "settled",
        })
        resp = ln.l402.pay(www_authenticate="L402 mac:inv", max_fee=10)
        assert cap.path == "/v1/l402/pay"
        assert resp.status == "settled"
        assert resp.amount == 100
