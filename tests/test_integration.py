"""
Integration tests for the LnBot Python SDK.

These tests hit the live API with real sats. They validate every SDK method,
response shapes, error handling, balance bookkeeping, and edge cases.

Requires env vars:
  LNBOT_USER_KEY   — user key (uk_...) that owns the prefunded wallet
  LNBOT_WALLET_ID  — wallet ID (wal_...) of the prefunded wallet

Run: pytest tests/test_integration.py -v -x
"""

from __future__ import annotations

import os
import time
import threading

import pytest

from lnbot import (
    LnBot,
    BadRequestError,
    ConflictError,
    LnBotError,
    NotFoundError,
    UnauthorizedError,
)

USER_KEY = os.environ.get("LNBOT_USER_KEY")
WALLET_ID = os.environ.get("LNBOT_WALLET_ID")

pytestmark = pytest.mark.integration

skip_if_no_env = pytest.mark.skipif(
    not USER_KEY or not WALLET_ID,
    reason="LNBOT_USER_KEY and LNBOT_WALLET_ID env vars required",
)

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

_state: dict = {}


def _wait_for_payment(wallet, payment_number: int, max_wait: int = 30):
    """Poll until payment settles or fails."""
    for _ in range(max_wait * 2):
        p = wallet.payments.get(payment_number)
        if p.status in ("settled", "failed"):
            return p
        time.sleep(0.5)
    return wallet.payments.get(payment_number)


@pytest.fixture(scope="module", autouse=True)
def setup_and_teardown():
    """Setup: create client, record w1 balance, create w2 wallet + key."""
    if not USER_KEY or not WALLET_ID:
        yield
        return

    client = LnBot(api_key=USER_KEY)
    w1 = client.wallet(WALLET_ID)
    w1_info = w1.get()

    _state["client"] = client
    _state["w1"] = w1
    _state["w1_balance_before"] = w1_info.balance

    w2_info = client.wallets.create()
    _state["w2_info"] = w2_info

    w2_key = client.wallet(w2_info.wallet_id).key.create()
    _state["w2_key"] = w2_key
    _state["w2_client"] = LnBot(api_key=w2_key.key)

    yield

    # Cleanup: return funds
    try:
        w2 = client.wallet(w2_info.wallet_id)
        bal = w2.get()
        if bal.available > 0:
            inv = w1.invoices.create(amount=bal.available)
            p = w2.payments.create(target=inv.bolt11)
            _wait_for_payment(w2, p.number)
    except Exception:
        pass


# =========================================================================
# ACCOUNT
# =========================================================================


@skip_if_no_env
class TestAccount:
    def test_register_creates_new_account(self):
        no_auth = LnBot()
        account = no_auth.register()
        assert account.user_id.startswith("usr_")
        assert account.primary_key
        assert account.secondary_key
        assert len(account.recovery_passphrase.split()) == 12

    def test_me_returns_identity_with_user_key(self):
        me = _state["client"].me()
        assert me is not None

    def test_me_returns_identity_with_wallet_key(self):
        me = _state["w2_client"].me()
        assert me.wallet_id is not None
        assert me.wallet_id

    def test_me_rejects_invalid_key(self):
        bad = LnBot(api_key="uk_invalid")
        with pytest.raises(UnauthorizedError):
            bad.me()


# =========================================================================
# WALLETS
# =========================================================================


@skip_if_no_env
class TestWallets:
    def test_wallets_create_returns_wallet_with_address(self):
        w2_info = _state["w2_info"]
        assert w2_info.wallet_id.startswith("wal_")
        assert w2_info.name
        assert "@" in w2_info.address

    def test_wallets_list_includes_both_wallets(self):
        wallets = _state["client"].wallets.list()
        ids = [w.wallet_id for w in wallets]
        assert WALLET_ID in ids
        assert _state["w2_info"].wallet_id in ids
        item = next(w for w in wallets if w.wallet_id == _state["w2_info"].wallet_id)
        assert item.name
        assert item.created_at is not None

    def test_wallet_get_returns_full_balance_info(self):
        info = _state["w1"].get()
        assert info.wallet_id == WALLET_ID
        assert info.balance > 0
        assert info.available >= 0
        assert info.available <= info.balance

    def test_wallet_update_changes_name(self):
        name = f"test-{int(time.time() * 1000)}"
        updated = _state["w1"].update(name=name)
        assert updated.name == name
        assert updated.wallet_id == WALLET_ID
        fetched = _state["w1"].get()
        assert fetched.name == name

    def test_wallet_get_rejects_nonexistent(self):
        bad = _state["client"].wallet("wal_nonexistent")
        with pytest.raises(NotFoundError):
            bad.get()


# =========================================================================
# WALLET KEYS
# =========================================================================


@skip_if_no_env
class TestWalletKeys:
    def test_wallet_key_create_returned_wk_key(self):
        w2_key = _state["w2_key"]
        assert w2_key.key.startswith("wk_")
        assert w2_key.hint

    def test_wallet_key_create_rejects_duplicate(self):
        with pytest.raises(LnBotError):
            _state["client"].wallet(_state["w2_info"].wallet_id).key.create()

    def test_wallet_key_get_returns_metadata(self):
        info = _state["client"].wallet(_state["w2_info"].wallet_id).key.get()
        assert info.hint
        assert info.created_at is not None

    def test_wallet_key_rotate_returns_new_key(self):
        rotated = _state["client"].wallet(_state["w2_info"].wallet_id).key.rotate()
        assert rotated.key.startswith("wk_")
        assert rotated.key != _state["w2_key"].key
        _state["w2_key"] = rotated
        _state["w2_client"] = LnBot(api_key=rotated.key)

    def test_wallet_current_get_works_with_wallet_key(self):
        info = _state["w2_client"].wallet("current").get()
        assert info.wallet_id == _state["w2_info"].wallet_id


# =========================================================================
# ADDRESSES
# =========================================================================


@skip_if_no_env
class TestAddresses:
    def test_addresses_create_random(self):
        w2 = _state["client"].wallet(_state["w2_info"].wallet_id)
        addr = w2.addresses.create()
        _state["w2_address"] = addr
        assert "@" in addr.address
        assert addr.generated is True
        assert addr.cost == 0
        assert addr.created_at is not None

    def test_addresses_list_includes_created(self):
        w2 = _state["client"].wallet(_state["w2_info"].wallet_id)
        addresses = w2.addresses.list()
        assert len(addresses) >= 1
        found = next((a for a in addresses if a.address == _state["w2_address"].address), None)
        assert found is not None
        assert found.generated is True

    def test_addresses_transfer_rejects_generated(self):
        w2 = _state["client"].wallet(_state["w2_info"].wallet_id)
        extra = w2.addresses.create()

        try:
            w1_key = _state["w1"].key.create()
        except Exception:
            w1_key = _state["w1"].key.rotate()

        with pytest.raises(BadRequestError):
            w2.addresses.transfer(extra.address, target_wallet_key=w1_key.key)

        w2.addresses.delete(extra.address)
        _state["w1"].key.delete()


# =========================================================================
# INVOICES
# =========================================================================


@skip_if_no_env
class TestInvoices:
    def test_invoices_create_with_all_fields(self):
        w2 = _state["client"].wallet(_state["w2_info"].wallet_id)
        inv = w2.invoices.create(amount=2, memo="sdk-test", reference="ref-001")
        _state["w2_invoice"] = inv
        assert inv.number > 0
        assert inv.status == "pending"
        assert inv.bolt11.startswith("lnbc")
        assert inv.amount == 2
        assert inv.memo == "sdk-test"
        assert inv.reference == "ref-001"
        assert inv.preimage is None
        assert inv.tx_number is None
        assert inv.created_at is not None
        assert inv.settled_at is None
        assert inv.expires_at is not None

    def test_invoices_create_rejects_zero_amount(self):
        w2 = _state["client"].wallet(_state["w2_info"].wallet_id)
        with pytest.raises(BadRequestError):
            w2.invoices.create(amount=0)

    def test_invoices_list_with_pagination(self):
        w2 = _state["client"].wallet(_state["w2_info"].wallet_id)
        all_inv = w2.invoices.list(limit=10)
        assert len(all_inv) >= 1
        if len(all_inv) >= 2:
            page = w2.invoices.list(limit=1, after=all_inv[0].number)
            assert len(page) >= 1
            assert page[0].number < all_inv[0].number

    def test_invoices_get_by_number(self):
        w2 = _state["client"].wallet(_state["w2_info"].wallet_id)
        inv = w2.invoices.get(_state["w2_invoice"].number)
        assert inv.number == _state["w2_invoice"].number
        assert inv.amount == 2
        assert inv.reference == "ref-001"

    def test_invoices_get_rejects_nonexistent(self):
        w2 = _state["client"].wallet(_state["w2_info"].wallet_id)
        with pytest.raises(NotFoundError):
            w2.invoices.get(999999)

    def test_invoices_create_for_wallet_without_auth(self):
        no_auth = LnBot()
        inv = no_auth.invoices.create_for_wallet(wallet_id=_state["w2_info"].wallet_id, amount=5)
        assert inv.bolt11.startswith("lnbc")
        assert inv.amount == 5

    def test_invoices_create_for_address_without_auth(self):
        no_auth = LnBot()
        inv = no_auth.invoices.create_for_address(address=_state["w2_address"].address, amount=5)
        assert inv.bolt11.startswith("lnbc")
        assert inv.amount == 5

    def test_invoices_create_for_wallet_rejects_nonexistent(self):
        no_auth = LnBot()
        with pytest.raises(BadRequestError):
            no_auth.invoices.create_for_wallet(wallet_id="wal_nonexistent", amount=1)


# =========================================================================
# PAYMENTS + BALANCE BOOKKEEPING
# =========================================================================


@skip_if_no_env
class TestPayments:
    def test_payments_resolve_lightning_address(self):
        resolved = _state["w1"].payments.resolve(target=_state["w2_address"].address)
        assert resolved.type == "lightning_address"
        assert resolved.min is not None
        assert resolved.max is not None
        assert resolved.fixed is not None

    def test_payments_resolve_bolt11(self):
        resolved = _state["w1"].payments.resolve(target=_state["w2_invoice"].bolt11)
        assert resolved.type == "bolt11"
        assert resolved.amount == 2
        assert resolved.fixed is True

    def test_payments_create_pays_and_settles(self):
        payment = _state["w1"].payments.create(target=_state["w2_invoice"].bolt11)
        _state["w1_payment"] = payment
        assert payment.number > 0
        assert payment.amount == 2

        settled = _wait_for_payment(_state["w1"], payment.number)
        assert settled.status == "settled"
        assert settled.preimage is not None
        assert settled.tx_number is not None
        assert settled.settled_at is not None
        _state["w1_payment"] = settled

    def test_balances_updated_correctly(self):
        w1_after = _state["w1"].get()
        w2_after = _state["client"].wallet(_state["w2_info"].wallet_id).get()
        p = _state["w1_payment"]

        assert w1_after.balance < _state["w1_balance_before"]
        assert w1_after.balance == _state["w1_balance_before"] - p.amount - p.service_fee - (p.actual_fee or 0)
        assert w2_after.balance == 2

    def test_invoice_is_settled_on_wallet_2(self):
        w2 = _state["client"].wallet(_state["w2_info"].wallet_id)
        inv = w2.invoices.get(_state["w2_invoice"].number)
        assert inv.status == "settled"
        assert inv.settled_at is not None

    def test_payments_list_with_pagination(self):
        payments = _state["w1"].payments.list(limit=5)
        assert any(p.number == _state["w1_payment"].number for p in payments)
        if len(payments) >= 2:
            page = _state["w1"].payments.list(limit=1, after=payments[0].number)
            assert len(page) >= 1
            assert page[0].number < payments[0].number

    def test_payments_get_by_number(self):
        p = _state["w1"].payments.get(_state["w1_payment"].number)
        assert p.number == _state["w1_payment"].number
        assert p.status == "settled"
        assert p.amount == 2

    def test_payments_get_rejects_nonexistent(self):
        with pytest.raises(NotFoundError):
            _state["w1"].payments.get(999999)

    def test_payments_create_rejects_insufficient_balance(self):
        w2 = _state["client"].wallet(_state["w2_info"].wallet_id)
        inv = _state["w1"].invoices.create(amount=999999)
        with pytest.raises(BadRequestError):
            w2.payments.create(target=inv.bolt11)

    def test_payments_create_idempotency(self):
        w2 = _state["client"].wallet(_state["w2_info"].wallet_id)
        inv = _state["w1"].invoices.create(amount=1)
        idem_key = f"idem-{int(time.time() * 1000)}"

        p1 = w2.payments.create(target=inv.bolt11, idempotency_key=idem_key)
        _wait_for_payment(w2, p1.number)

        p2 = w2.payments.create(target=inv.bolt11, idempotency_key=idem_key)
        assert p2.number == p1.number


# =========================================================================
# TRANSACTIONS
# =========================================================================


@skip_if_no_env
class TestTransactions:
    def test_transactions_list_has_debit(self):
        txns = _state["w1"].transactions.list(limit=10)
        assert len(txns) > 0
        debit = next((t for t in txns if t.type == "debit"), None)
        assert debit is not None
        assert debit.amount > 0
        assert debit.created_at is not None

    def test_transactions_list_has_credit_on_w2(self):
        w2 = _state["client"].wallet(_state["w2_info"].wallet_id)
        txns = w2.transactions.list(limit=10)
        credit = next((t for t in txns if t.type == "credit"), None)
        assert credit is not None
        assert credit.amount == 2

    def test_transactions_list_pagination(self):
        txns = _state["w1"].transactions.list(limit=1)
        assert len(txns) == 1
        if txns:
            nxt = _state["w1"].transactions.list(limit=1, after=txns[0].number)
            if nxt:
                assert nxt[0].number < txns[0].number


# =========================================================================
# WEBHOOKS
# =========================================================================


@skip_if_no_env
class TestWebhooks:
    def test_webhooks_full_crud(self):
        w2 = _state["client"].wallet(_state["w2_info"].wallet_id)

        created = w2.webhooks.create(url="https://example.com/hook")
        assert created.id
        assert created.secret
        assert created.url == "https://example.com/hook"
        assert created.created_at is not None

        wh_list = w2.webhooks.list()
        found = next((wh for wh in wh_list if wh.id == created.id), None)
        assert found is not None
        assert found.url == "https://example.com/hook"

        w2.webhooks.delete(created.id)
        after = w2.webhooks.list()
        assert not any(wh.id == created.id for wh in after)

    def test_webhooks_delete_rejects_nonexistent(self):
        w2 = _state["client"].wallet(_state["w2_info"].wallet_id)
        with pytest.raises(NotFoundError):
            w2.webhooks.delete("nonexistent")


# =========================================================================
# L402
# =========================================================================


@skip_if_no_env
class TestL402:
    def test_l402_create_challenge_returns_all_fields(self):
        challenge = _state["w1"].l402.create_challenge(
            amount=1, description="test paywall", expiry_seconds=300, caveats=["service=test"],
        )
        assert challenge.macaroon
        assert challenge.invoice.startswith("lnbc")
        assert challenge.payment_hash
        assert "L402" in challenge.www_authenticate
        assert "macaroon=" in challenge.www_authenticate
        assert "invoice=" in challenge.www_authenticate

    def test_l402_verify_rejects_invalid_token(self):
        with pytest.raises(BadRequestError):
            _state["w1"].l402.verify(authorization="L402 invalid:invalid")

    def test_l402_full_flow(self):
        challenge = _state["w1"].l402.create_challenge(amount=1)

        w2 = _state["client"].wallet(_state["w2_info"].wallet_id)
        pay_result = w2.l402.pay(
            www_authenticate=challenge.www_authenticate, max_fee=1, wait=True, timeout=30,
        )
        assert pay_result.status == "settled"
        assert pay_result.authorization is not None
        assert "L402" in pay_result.authorization
        assert pay_result.preimage is not None
        assert pay_result.payment_hash == challenge.payment_hash
        assert pay_result.amount == 1

        verified = _state["w1"].l402.verify(authorization=pay_result.authorization)
        assert verified.valid is True
        assert verified.payment_hash == challenge.payment_hash
        assert verified.caveats is not None
        assert verified.error is None


# =========================================================================
# SSE: INVOICE WATCH
# =========================================================================


@skip_if_no_env
class TestSSEInvoiceWatch:
    def test_invoices_watch_yields_settlement_event(self):
        w2 = _state["client"].wallet(_state["w2_info"].wallet_id)
        inv = w2.invoices.create(amount=1, memo="watch-test")

        w2wk = _state["w2_client"].wallet(_state["w2_info"].wallet_id)
        events = []

        def watch():
            for evt in w2wk.invoices.watch(inv.number, timeout=60):
                events.append(evt)
                if evt.event in ("settled", "expired"):
                    break

        t = threading.Thread(target=watch)
        t.start()

        time.sleep(1.5)
        _state["w1"].payments.create(target=inv.bolt11)

        t.join(timeout=60)
        assert any(e.event == "settled" for e in events)


# =========================================================================
# SSE: PAYMENT WATCH
# =========================================================================


@skip_if_no_env
class TestSSEPaymentWatch:
    def test_payments_watch_yields_settlement_event(self):
        w2 = _state["client"].wallet(_state["w2_info"].wallet_id)
        inv = _state["w1"].invoices.create(amount=1)
        payment = w2.payments.create(target=inv.bolt11)

        w2wk = _state["w2_client"].wallet(_state["w2_info"].wallet_id)
        events = []
        for evt in w2wk.payments.watch(payment.number, timeout=30):
            events.append(evt)
            if evt.event in ("settled", "failed"):
                break

        assert any(e.event == "settled" for e in events)


# =========================================================================
# SSE: WALLET EVENT STREAM
# =========================================================================


@skip_if_no_env
class TestSSEEventsStream:
    def test_events_stream_receives_events(self):
        w2wk = _state["w2_client"].wallet(_state["w2_info"].wallet_id)
        w2 = _state["client"].wallet(_state["w2_info"].wallet_id)

        events = []

        def stream():
            for evt in w2wk.events.stream():
                events.append(evt)
                if len(events) >= 2:
                    break

        t = threading.Thread(target=stream)
        t.start()

        time.sleep(1.5)

        inv = w2.invoices.create(amount=1)
        _state["w1"].payments.create(target=inv.bolt11)

        t.join(timeout=15)

        assert len(events) >= 1
        assert any(e.event.startswith("invoice.") for e in events)


# =========================================================================
# BACKUP
# =========================================================================


@skip_if_no_env
class TestBackup:
    def test_backup_recovery_generates_passphrase(self):
        result = _state["client"].backup.recovery()
        assert result.passphrase
        assert len(result.passphrase.split()) == 12


# =========================================================================
# ERROR HANDLING
# =========================================================================


@skip_if_no_env
class TestErrorHandling:
    def test_rejects_unauthenticated_access(self):
        no_auth = LnBot()
        with pytest.raises(UnauthorizedError):
            no_auth.me()

    def test_rejects_wrong_wallet_id(self):
        bad = _state["client"].wallet("wal_nonexistent")
        with pytest.raises(NotFoundError):
            bad.invoices.list()

    def test_rejects_access_to_wallet_owned_by_another_user(self):
        other = LnBot().register()
        other_client = LnBot(api_key=other.primary_key)
        with pytest.raises(LnBotError):
            other_client.wallet(WALLET_ID).get()


# =========================================================================
# CLEANUP
# =========================================================================


@skip_if_no_env
class TestCleanup:
    def test_cleanup_return_funds(self):
        w2 = _state["client"].wallet(_state["w2_info"].wallet_id)
        bal = w2.get()
        if bal.available > 0:
            inv = _state["w1"].invoices.create(amount=bal.available)
            p = w2.payments.create(target=inv.bolt11)
            settled = _wait_for_payment(w2, p.number)
            assert settled.status == "settled"
        after = w2.get()
        assert after.balance == 0

    def test_cleanup_wallet1_balance_restored(self):
        w1_after = _state["w1"].get()
        assert w1_after.balance >= _state["w1_balance_before"] - 10

    def test_cleanup_addresses_delete(self):
        w2 = _state["client"].wallet(_state["w2_info"].wallet_id)
        w2.addresses.delete(_state["w2_address"].address)
        addresses = w2.addresses.list()
        assert not any(a.address == _state["w2_address"].address for a in addresses)

    def test_cleanup_addresses_delete_rejects_already_deleted(self):
        w2 = _state["client"].wallet(_state["w2_info"].wallet_id)
        with pytest.raises(NotFoundError):
            w2.addresses.delete(_state["w2_address"].address)

    def test_cleanup_wallet_key_delete_revokes(self):
        _state["client"].wallet(_state["w2_info"].wallet_id).key.delete()
        dead = LnBot(api_key=_state["w2_key"].key)
        with pytest.raises(LnBotError):
            dead.wallet("current").get()

    def test_cleanup_wallet_key_get_rejects_after_delete(self):
        with pytest.raises(NotFoundError):
            _state["client"].wallet(_state["w2_info"].wallet_id).key.get()
