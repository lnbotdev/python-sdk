from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator, Iterator
from importlib.metadata import version as _pkg_version
from typing import Any

import httpx

from .errors import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    LnBotError,
    NotFoundError,
    UnauthorizedError,
    _extract_message,
)
from .types import (
    AddressResponse,
    ApiKeyResponse,
    BackupPasskeyBeginResponse,
    CreateWalletResponse,
    CreateWebhookResponse,
    InvoiceEvent,
    InvoiceResponse,
    PaymentResponse,
    RecoveryBackupResponse,
    RecoveryRestoreResponse,
    RestorePasskeyBeginResponse,
    RestorePasskeyCompleteResponse,
    RotateApiKeyResponse,
    TransactionResponse,
    TransferAddressResponse,
    WalletResponse,
    WebhookResponse,
    parse,
    to_camel,
)

_DEFAULT_BASE_URL = "https://api.ln.bot"

try:
    _VERSION = _pkg_version("lnbot")
except Exception:
    _VERSION = "0.0.0"

_USER_AGENT = f"lnbot-python/{_VERSION}"


def _qs(params: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in params.items() if v is not None}


def _raise_for_status(response: httpx.Response) -> None:
    if response.is_success:
        return
    body = response.text
    match response.status_code:
        case 400:
            raise BadRequestError(body)
        case 401:
            raise UnauthorizedError(body)
        case 403:
            raise ForbiddenError(body)
        case 404:
            raise NotFoundError(body)
        case 409:
            raise ConflictError(body)
        case _:
            msg = _extract_message(body, response.reason_phrase or "Error")
            raise LnBotError(msg, response.status_code, body)


def _headers(api_key: str | None) -> dict[str, str]:
    h: dict[str, str] = {"Accept": "application/json", "User-Agent": _USER_AGENT}
    if api_key:
        h["Authorization"] = f"Bearer {api_key}"
    return h


# ---------------------------------------------------------------------------
# Sync resource classes
# ---------------------------------------------------------------------------

class WalletsResource:
    """Wallet creation and management."""

    def __init__(self, client: LnBot) -> None:
        self._c = client

    def create(self, *, name: str | None = None) -> CreateWalletResponse:
        """Create a new wallet. No authentication required."""
        body = to_camel({"name": name}) if name else None
        return parse(CreateWalletResponse, self._c._post("/v1/wallets", body))

    def current(self) -> WalletResponse:
        """Get the current wallet's info and balance."""
        return parse(WalletResponse, self._c._get("/v1/wallets/current"))

    def update(self, *, name: str) -> WalletResponse:
        """Update the current wallet's name."""
        return parse(WalletResponse, self._c._patch("/v1/wallets/current", {"name": name}))


class KeysResource:
    """API key listing and rotation."""

    def __init__(self, client: LnBot) -> None:
        self._c = client

    def list(self) -> list[ApiKeyResponse]:
        """List API keys (metadata only, keys are not returned)."""
        return [parse(ApiKeyResponse, item) for item in self._c._get("/v1/keys")]

    def rotate(self, slot: int) -> RotateApiKeyResponse:
        """Rotate an API key. *slot* 0 = primary, 1 = secondary."""
        return parse(RotateApiKeyResponse, self._c._post(f"/v1/keys/{slot}/rotate"))


class InvoicesResource:
    """BOLT11 invoice creation and retrieval."""

    def __init__(self, client: LnBot) -> None:
        self._c = client

    def create(self, *, amount: int, reference: str | None = None, memo: str | None = None) -> InvoiceResponse:
        """Create a new BOLT11 invoice for *amount* sats."""
        return parse(InvoiceResponse, self._c._post("/v1/invoices", to_camel({"amount": amount, "reference": reference, "memo": memo})))

    def list(self, *, limit: int | None = None, after: int | None = None) -> list[InvoiceResponse]:
        """List invoices, optionally paginated."""
        return [parse(InvoiceResponse, item) for item in self._c._get("/v1/invoices", params=_qs({"limit": limit, "after": after}))]

    def get(self, number: int) -> InvoiceResponse:
        """Get a single invoice by its number."""
        return parse(InvoiceResponse, self._c._get(f"/v1/invoices/{number}"))

    def watch(self, number: int, *, timeout: int | None = None) -> Iterator[InvoiceEvent]:
        """Stream SSE events until the invoice is settled or expires."""
        params = _qs({"timeout": timeout})
        headers = {"Accept": "text/event-stream", "User-Agent": _USER_AGENT}
        if self._c._api_key:
            headers["Authorization"] = f"Bearer {self._c._api_key}"
        with self._c._http.stream("GET", f"{self._c._base_url}/v1/invoices/{number}/events", params=params, headers=headers) as resp:
            _raise_for_status(resp)
            event_type = ""
            for line in resp.iter_lines():
                if line.startswith("event:"):
                    event_type = line[6:].strip()
                elif line.startswith("data:"):
                    raw = line[5:].strip()
                    if raw and event_type:
                        try:
                            data = parse(InvoiceResponse, json.loads(raw))
                            yield InvoiceEvent(event=event_type, data=data)  # type: ignore[arg-type]
                        except (json.JSONDecodeError, TypeError):
                            pass
                        event_type = ""


class PaymentsResource:
    """Send sats to Lightning addresses or BOLT11 invoices."""

    def __init__(self, client: LnBot) -> None:
        self._c = client

    def create(self, *, target: str, amount: int | None = None, idempotency_key: str | None = None, max_fee: int | None = None, reference: str | None = None) -> PaymentResponse:
        """Send a payment to *target* (Lightning address or BOLT11 invoice)."""
        body = to_camel({"target": target, "amount": amount, "idempotency_key": idempotency_key, "max_fee": max_fee, "reference": reference})
        return parse(PaymentResponse, self._c._post("/v1/payments", body))

    def list(self, *, limit: int | None = None, after: int | None = None) -> list[PaymentResponse]:
        """List payments, optionally paginated."""
        return [parse(PaymentResponse, item) for item in self._c._get("/v1/payments", params=_qs({"limit": limit, "after": after}))]

    def get(self, number: int) -> PaymentResponse:
        """Get a single payment by its number."""
        return parse(PaymentResponse, self._c._get(f"/v1/payments/{number}"))


class AddressesResource:
    """Lightning address management."""

    def __init__(self, client: LnBot) -> None:
        self._c = client

    def create(self, *, address: str | None = None) -> AddressResponse:
        """Create a Lightning address (random if *address* is omitted)."""
        body = to_camel({"address": address}) if address else None
        return parse(AddressResponse, self._c._post("/v1/addresses", body))

    def list(self) -> list[AddressResponse]:
        """List all Lightning addresses for this wallet."""
        return [parse(AddressResponse, item) for item in self._c._get("/v1/addresses")]

    def delete(self, address: str) -> None:
        """Delete a Lightning address."""
        self._c._delete(f"/v1/addresses/{address}")

    def transfer(self, address: str, *, target_wallet_key: str) -> TransferAddressResponse:
        """Transfer an address to another wallet."""
        body = to_camel({"target_wallet_key": target_wallet_key})
        return parse(TransferAddressResponse, self._c._post(f"/v1/addresses/{address}/transfer", body))


class TransactionsResource:
    """Transaction history."""

    def __init__(self, client: LnBot) -> None:
        self._c = client

    def list(self, *, limit: int | None = None, after: int | None = None) -> list[TransactionResponse]:
        """List credit and debit transactions, optionally paginated."""
        return [parse(TransactionResponse, item) for item in self._c._get("/v1/transactions", params=_qs({"limit": limit, "after": after}))]


class WebhooksResource:
    """Webhook registration and management."""

    def __init__(self, client: LnBot) -> None:
        self._c = client

    def create(self, *, url: str) -> CreateWebhookResponse:
        """Register a webhook endpoint (max 10 per wallet)."""
        return parse(CreateWebhookResponse, self._c._post("/v1/webhooks", {"url": url}))

    def list(self) -> list[WebhookResponse]:
        """List all registered webhooks."""
        return [parse(WebhookResponse, item) for item in self._c._get("/v1/webhooks")]

    def delete(self, webhook_id: str) -> None:
        """Delete a webhook by its ID."""
        self._c._delete(f"/v1/webhooks/{webhook_id}")


class BackupResource:
    """Wallet backup via recovery passphrase or passkey."""

    def __init__(self, client: LnBot) -> None:
        self._c = client

    def recovery(self) -> RecoveryBackupResponse:
        """Generate a 12-word BIP-39 recovery passphrase."""
        return parse(RecoveryBackupResponse, self._c._post("/v1/backup/recovery"))

    def passkey_begin(self) -> BackupPasskeyBeginResponse:
        """Start WebAuthn passkey registration for backup."""
        return parse(BackupPasskeyBeginResponse, self._c._post("/v1/backup/passkey/begin"))

    def passkey_complete(self, *, session_id: str, attestation: dict[str, Any]) -> None:
        """Complete passkey backup with the authenticator attestation."""
        self._c._post("/v1/backup/passkey/complete", to_camel({"session_id": session_id, "attestation": attestation}))


class RestoreResource:
    """Wallet restoration via recovery passphrase or passkey."""

    def __init__(self, client: LnBot) -> None:
        self._c = client

    def recovery(self, *, passphrase: str) -> RecoveryRestoreResponse:
        """Restore wallet access using a 12-word recovery passphrase."""
        return parse(RecoveryRestoreResponse, self._c._post("/v1/restore/recovery", {"passphrase": passphrase}))

    def passkey_begin(self) -> RestorePasskeyBeginResponse:
        """Start WebAuthn passkey assertion for restore."""
        return parse(RestorePasskeyBeginResponse, self._c._post("/v1/restore/passkey/begin"))

    def passkey_complete(self, *, session_id: str, assertion: dict[str, Any]) -> RestorePasskeyCompleteResponse:
        """Complete passkey restore with the authenticator assertion."""
        return parse(RestorePasskeyCompleteResponse, self._c._post("/v1/restore/passkey/complete", to_camel({"session_id": session_id, "assertion": assertion})))


# ---------------------------------------------------------------------------
# Sync client
# ---------------------------------------------------------------------------

class LnBot:
    """Synchronous LnBot API client.

    >>> with LnBot(api_key="key_...") as ln:
    ...     wallet = ln.wallets.current()
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: float | httpx.Timeout = 30.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("LNBOT_API_KEY")
        self._base_url = base_url.rstrip("/")
        self._http = http_client or httpx.Client(timeout=timeout)

        self.wallets = WalletsResource(self)
        self.keys = KeysResource(self)
        self.invoices = InvoicesResource(self)
        self.payments = PaymentsResource(self)
        self.addresses = AddressesResource(self)
        self.transactions = TransactionsResource(self)
        self.webhooks = WebhooksResource(self)
        self.backup = BackupResource(self)
        self.restore = RestoreResource(self)

    def _get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        resp = self._http.get(f"{self._base_url}{path}", headers=_headers(self._api_key), params=params)
        _raise_for_status(resp)
        return resp.json()

    def _post(self, path: str, body: Any = None) -> Any:
        resp = self._http.post(f"{self._base_url}{path}", headers=_headers(self._api_key), json=body)
        _raise_for_status(resp)
        if resp.status_code == 204:
            return None
        ct = resp.headers.get("content-type", "")
        return resp.json() if "application/json" in ct else resp.text

    def _patch(self, path: str, body: Any = None) -> Any:
        resp = self._http.patch(f"{self._base_url}{path}", headers=_headers(self._api_key), json=body)
        _raise_for_status(resp)
        ct = resp.headers.get("content-type", "")
        return resp.json() if "application/json" in ct else resp.text

    def _delete(self, path: str) -> None:
        resp = self._http.delete(f"{self._base_url}{path}", headers=_headers(self._api_key))
        _raise_for_status(resp)

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._http.close()

    def __enter__(self) -> LnBot:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Async resource classes
# ---------------------------------------------------------------------------

class AsyncWalletsResource:
    """Wallet creation and management (async)."""

    def __init__(self, client: AsyncLnBot) -> None:
        self._c = client

    async def create(self, *, name: str | None = None) -> CreateWalletResponse:
        """Create a new wallet. No authentication required."""
        body = to_camel({"name": name}) if name else None
        return parse(CreateWalletResponse, await self._c._post("/v1/wallets", body))

    async def current(self) -> WalletResponse:
        """Get the current wallet's info and balance."""
        return parse(WalletResponse, await self._c._get("/v1/wallets/current"))

    async def update(self, *, name: str) -> WalletResponse:
        """Update the current wallet's name."""
        return parse(WalletResponse, await self._c._patch("/v1/wallets/current", {"name": name}))


class AsyncKeysResource:
    """API key listing and rotation (async)."""

    def __init__(self, client: AsyncLnBot) -> None:
        self._c = client

    async def list(self) -> list[ApiKeyResponse]:
        """List API keys (metadata only, keys are not returned)."""
        return [parse(ApiKeyResponse, item) for item in await self._c._get("/v1/keys")]

    async def rotate(self, slot: int) -> RotateApiKeyResponse:
        """Rotate an API key. *slot* 0 = primary, 1 = secondary."""
        return parse(RotateApiKeyResponse, await self._c._post(f"/v1/keys/{slot}/rotate"))


class AsyncInvoicesResource:
    """BOLT11 invoice creation and retrieval (async)."""

    def __init__(self, client: AsyncLnBot) -> None:
        self._c = client

    async def create(self, *, amount: int, reference: str | None = None, memo: str | None = None) -> InvoiceResponse:
        """Create a new BOLT11 invoice for *amount* sats."""
        return parse(InvoiceResponse, await self._c._post("/v1/invoices", to_camel({"amount": amount, "reference": reference, "memo": memo})))

    async def list(self, *, limit: int | None = None, after: int | None = None) -> list[InvoiceResponse]:
        """List invoices, optionally paginated."""
        return [parse(InvoiceResponse, item) for item in await self._c._get("/v1/invoices", params=_qs({"limit": limit, "after": after}))]

    async def get(self, number: int) -> InvoiceResponse:
        """Get a single invoice by its number."""
        return parse(InvoiceResponse, await self._c._get(f"/v1/invoices/{number}"))

    async def watch(self, number: int, *, timeout: int | None = None) -> AsyncIterator[InvoiceEvent]:
        """Stream SSE events until the invoice is settled or expires."""
        params = _qs({"timeout": timeout})
        headers = {"Accept": "text/event-stream", "User-Agent": _USER_AGENT}
        if self._c._api_key:
            headers["Authorization"] = f"Bearer {self._c._api_key}"
        async with self._c._http.stream("GET", f"{self._c._base_url}/v1/invoices/{number}/events", params=params, headers=headers) as resp:
            _raise_for_status(resp)
            event_type = ""
            async for line in resp.aiter_lines():
                if line.startswith("event:"):
                    event_type = line[6:].strip()
                elif line.startswith("data:"):
                    raw = line[5:].strip()
                    if raw and event_type:
                        try:
                            data = parse(InvoiceResponse, json.loads(raw))
                            yield InvoiceEvent(event=event_type, data=data)  # type: ignore[arg-type]
                        except (json.JSONDecodeError, TypeError):
                            pass
                        event_type = ""


class AsyncPaymentsResource:
    """Send sats to Lightning addresses or BOLT11 invoices (async)."""

    def __init__(self, client: AsyncLnBot) -> None:
        self._c = client

    async def create(self, *, target: str, amount: int | None = None, idempotency_key: str | None = None, max_fee: int | None = None, reference: str | None = None) -> PaymentResponse:
        """Send a payment to *target* (Lightning address or BOLT11 invoice)."""
        body = to_camel({"target": target, "amount": amount, "idempotency_key": idempotency_key, "max_fee": max_fee, "reference": reference})
        return parse(PaymentResponse, await self._c._post("/v1/payments", body))

    async def list(self, *, limit: int | None = None, after: int | None = None) -> list[PaymentResponse]:
        """List payments, optionally paginated."""
        return [parse(PaymentResponse, item) for item in await self._c._get("/v1/payments", params=_qs({"limit": limit, "after": after}))]

    async def get(self, number: int) -> PaymentResponse:
        """Get a single payment by its number."""
        return parse(PaymentResponse, await self._c._get(f"/v1/payments/{number}"))


class AsyncAddressesResource:
    """Lightning address management (async)."""

    def __init__(self, client: AsyncLnBot) -> None:
        self._c = client

    async def create(self, *, address: str | None = None) -> AddressResponse:
        """Create a Lightning address (random if *address* is omitted)."""
        body = to_camel({"address": address}) if address else None
        return parse(AddressResponse, await self._c._post("/v1/addresses", body))

    async def list(self) -> list[AddressResponse]:
        """List all Lightning addresses for this wallet."""
        return [parse(AddressResponse, item) for item in await self._c._get("/v1/addresses")]

    async def delete(self, address: str) -> None:
        """Delete a Lightning address."""
        await self._c._delete(f"/v1/addresses/{address}")

    async def transfer(self, address: str, *, target_wallet_key: str) -> TransferAddressResponse:
        """Transfer an address to another wallet."""
        body = to_camel({"target_wallet_key": target_wallet_key})
        return parse(TransferAddressResponse, await self._c._post(f"/v1/addresses/{address}/transfer", body))


class AsyncTransactionsResource:
    """Transaction history (async)."""

    def __init__(self, client: AsyncLnBot) -> None:
        self._c = client

    async def list(self, *, limit: int | None = None, after: int | None = None) -> list[TransactionResponse]:
        """List credit and debit transactions, optionally paginated."""
        return [parse(TransactionResponse, item) for item in await self._c._get("/v1/transactions", params=_qs({"limit": limit, "after": after}))]


class AsyncWebhooksResource:
    """Webhook registration and management (async)."""

    def __init__(self, client: AsyncLnBot) -> None:
        self._c = client

    async def create(self, *, url: str) -> CreateWebhookResponse:
        """Register a webhook endpoint (max 10 per wallet)."""
        return parse(CreateWebhookResponse, await self._c._post("/v1/webhooks", {"url": url}))

    async def list(self) -> list[WebhookResponse]:
        """List all registered webhooks."""
        return [parse(WebhookResponse, item) for item in await self._c._get("/v1/webhooks")]

    async def delete(self, webhook_id: str) -> None:
        """Delete a webhook by its ID."""
        await self._c._delete(f"/v1/webhooks/{webhook_id}")


class AsyncBackupResource:
    """Wallet backup via recovery passphrase or passkey (async)."""

    def __init__(self, client: AsyncLnBot) -> None:
        self._c = client

    async def recovery(self) -> RecoveryBackupResponse:
        """Generate a 12-word BIP-39 recovery passphrase."""
        return parse(RecoveryBackupResponse, await self._c._post("/v1/backup/recovery"))

    async def passkey_begin(self) -> BackupPasskeyBeginResponse:
        """Start WebAuthn passkey registration for backup."""
        return parse(BackupPasskeyBeginResponse, await self._c._post("/v1/backup/passkey/begin"))

    async def passkey_complete(self, *, session_id: str, attestation: dict[str, Any]) -> None:
        """Complete passkey backup with the authenticator attestation."""
        await self._c._post("/v1/backup/passkey/complete", to_camel({"session_id": session_id, "attestation": attestation}))


class AsyncRestoreResource:
    """Wallet restoration via recovery passphrase or passkey (async)."""

    def __init__(self, client: AsyncLnBot) -> None:
        self._c = client

    async def recovery(self, *, passphrase: str) -> RecoveryRestoreResponse:
        """Restore wallet access using a 12-word recovery passphrase."""
        return parse(RecoveryRestoreResponse, await self._c._post("/v1/restore/recovery", {"passphrase": passphrase}))

    async def passkey_begin(self) -> RestorePasskeyBeginResponse:
        """Start WebAuthn passkey assertion for restore."""
        return parse(RestorePasskeyBeginResponse, await self._c._post("/v1/restore/passkey/begin"))

    async def passkey_complete(self, *, session_id: str, assertion: dict[str, Any]) -> RestorePasskeyCompleteResponse:
        """Complete passkey restore with the authenticator assertion."""
        return parse(RestorePasskeyCompleteResponse, await self._c._post("/v1/restore/passkey/complete", to_camel({"session_id": session_id, "assertion": assertion})))


# ---------------------------------------------------------------------------
# Async client
# ---------------------------------------------------------------------------

class AsyncLnBot:
    """Asynchronous LnBot API client.

    >>> async with AsyncLnBot(api_key="key_...") as ln:
    ...     wallet = await ln.wallets.current()
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: float | httpx.Timeout = 30.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("LNBOT_API_KEY")
        self._base_url = base_url.rstrip("/")
        self._http = http_client or httpx.AsyncClient(timeout=timeout)

        self.wallets = AsyncWalletsResource(self)
        self.keys = AsyncKeysResource(self)
        self.invoices = AsyncInvoicesResource(self)
        self.payments = AsyncPaymentsResource(self)
        self.addresses = AsyncAddressesResource(self)
        self.transactions = AsyncTransactionsResource(self)
        self.webhooks = AsyncWebhooksResource(self)
        self.backup = AsyncBackupResource(self)
        self.restore = AsyncRestoreResource(self)

    async def _get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        resp = await self._http.get(f"{self._base_url}{path}", headers=_headers(self._api_key), params=params)
        _raise_for_status(resp)
        return resp.json()

    async def _post(self, path: str, body: Any = None) -> Any:
        resp = await self._http.post(f"{self._base_url}{path}", headers=_headers(self._api_key), json=body)
        _raise_for_status(resp)
        if resp.status_code == 204:
            return None
        ct = resp.headers.get("content-type", "")
        return resp.json() if "application/json" in ct else resp.text

    async def _patch(self, path: str, body: Any = None) -> Any:
        resp = await self._http.patch(f"{self._base_url}{path}", headers=_headers(self._api_key), json=body)
        _raise_for_status(resp)
        ct = resp.headers.get("content-type", "")
        return resp.json() if "application/json" in ct else resp.text

    async def _delete(self, path: str) -> None:
        resp = await self._http.delete(f"{self._base_url}{path}", headers=_headers(self._api_key))
        _raise_for_status(resp)

    async def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        await self._http.aclose()

    async def __aenter__(self) -> AsyncLnBot:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
