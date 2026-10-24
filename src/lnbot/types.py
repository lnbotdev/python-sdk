from __future__ import annotations

import re
from dataclasses import MISSING, dataclass
from typing import Any, Literal, TypeVar

T = TypeVar("T")

InvoiceStatus = Literal["pending", "settled", "expired"]
PaymentStatus = Literal["pending", "processing", "settled", "failed"]
TransactionType = Literal["credit", "debit"]


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RegisterResponse:
    user_id: str
    primary_key: str
    secondary_key: str
    recovery_passphrase: str


@dataclass(frozen=True)
class MeResponse:
    wallet_id: str | None = None


# ---------------------------------------------------------------------------
# Wallet
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WalletResponse:
    wallet_id: str
    name: str
    balance: int
    on_hold: int
    available: int


@dataclass(frozen=True)
class CreateWalletResponse:
    wallet_id: str
    name: str
    address: str


@dataclass(frozen=True)
class WalletListItem:
    wallet_id: str
    name: str
    created_at: str | None = None


# ---------------------------------------------------------------------------
# Wallet Key
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WalletKeyResponse:
    key: str
    hint: str


@dataclass(frozen=True)
class WalletKeyInfoResponse:
    hint: str
    created_at: str | None = None
    last_used_at: str | None = None


# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RotateApiKeyResponse:
    key: str
    name: str


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InvoiceResponse:
    number: int
    status: InvoiceStatus
    amount: int
    bolt11: str
    reference: str | None = None
    memo: str | None = None
    preimage: str | None = None
    tx_number: int | None = None
    created_at: str | None = None
    settled_at: str | None = None
    expires_at: str | None = None


# ---------------------------------------------------------------------------
# Invoices (unauthenticated)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AddressInvoiceResponse:
    bolt11: str
    amount: int
    expires_at: str | None = None


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PaymentResponse:
    """A payment. On success the wallet is debited ``amount + actual_fee + service_fee``."""

    number: int
    status: PaymentStatus
    amount: int
    max_fee: int
    """Network fee reserved for this payment in sats (fee estimate plus a buffer). The unused part is released at settlement."""
    service_fee: int
    """Service fee in sats: 0.25%, minimum 1 sat. 0 for internal transfers."""
    address: str
    actual_fee: int | None = None
    """Network fee actually charged in sats (Spark's fee plus Lightning routing). None until settled."""
    reference: str | None = None
    preimage: str | None = None
    tx_number: int | None = None
    failure_reason: str | None = None
    created_at: str | None = None
    settled_at: str | None = None


@dataclass(frozen=True)
class ResolveTargetResponse:
    """A resolved payment target and what paying it would cost. Nothing is sent or held."""

    type: str
    """Target type: ``"lightning_address"``, ``"lnurl"`` or ``"bolt11"``."""
    min: int | None = None
    """Minimum accepted amount in sats. None for BOLT11 invoices."""
    max: int | None = None
    """Maximum accepted amount in sats. None for BOLT11 invoices."""
    fixed: bool | None = None
    """True if the recipient expects a fixed amount."""
    amount: int | None = None
    """The amount priced: the invoice amount for BOLT11, otherwise the amount passed. None when no amount."""
    internal: bool = False
    """True if the recipient is a wallet on ln.bot: a free internal transfer."""
    network_fee_estimate: int | None = None
    """Estimated network fee in sats (Spark's 0.25% plus routing). None without an amount or if no estimate is available. 0 if internal."""
    service_fee: int | None = None
    """Service fee in sats: 0.25%, minimum 1 sat. 0 if internal. None without an amount."""
    max_fee: int | None = None
    """Network fee that would be held with the default ``max_fee``. None without an amount, or when ``fee_warning`` is set."""
    total: int | None = None
    """``amount + network_fee_estimate + service_fee``. None without an amount."""
    max_sendable: int | None = None
    """For a Lightning address or LNURL resolved without an amount: the most this wallet can send there now, after fees. 0 if it can't cover the recipient's minimum. None otherwise."""
    fee_warning: str | None = None
    """Set when sending without ``max_fee`` would be rejected because the fee is unusually high."""


# ---------------------------------------------------------------------------
# Addresses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AddressResponse:
    address: str
    generated: bool
    cost: int
    created_at: str | None = None


@dataclass(frozen=True)
class TransferAddressResponse:
    address: str
    transferred_to: str


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TransactionResponse:
    number: int
    type: TransactionType
    amount: int
    balance_after: int
    network_fee: int
    service_fee: int
    payment_hash: str | None = None
    preimage: str | None = None
    reference: str | None = None
    note: str | None = None
    created_at: str | None = None


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CreateWebhookResponse:
    id: str
    url: str
    secret: str
    created_at: str | None = None


@dataclass(frozen=True)
class WebhookResponse:
    id: str
    url: str
    active: bool
    created_at: str | None = None


# ---------------------------------------------------------------------------
# Backup / Restore
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RecoveryBackupResponse:
    passphrase: str


@dataclass(frozen=True)
class RecoveryRestoreResponse:
    wallet_id: str
    name: str
    primary_key: str
    secondary_key: str


@dataclass(frozen=True)
class BackupPasskeyBeginResponse:
    session_id: str
    options: dict[str, Any]


@dataclass(frozen=True)
class RestorePasskeyBeginResponse:
    session_id: str
    options: dict[str, Any]


@dataclass(frozen=True)
class RestorePasskeyCompleteResponse:
    wallet_id: str
    name: str
    primary_key: str
    secondary_key: str


# ---------------------------------------------------------------------------
# L402
# ---------------------------------------------------------------------------

L402PaymentStatus = Literal["pending", "processing", "settled", "failed"]


@dataclass(frozen=True)
class L402ChallengeResponse:
    macaroon: str
    invoice: str
    payment_hash: str
    expires_at: str
    www_authenticate: str


@dataclass(frozen=True)
class VerifyL402Response:
    valid: bool
    payment_hash: str | None = None
    caveats: list[str] | None = None
    error: str | None = None


@dataclass(frozen=True)
class L402PayResponse:
    payment_hash: str
    amount: int
    payment_number: int
    status: L402PaymentStatus
    authorization: str | None = None
    preimage: str | None = None
    fee: int | None = None
    """Network fee actually charged in sats (Spark's fee plus Lightning routing). None until settled."""


# ---------------------------------------------------------------------------
# SSE
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InvoiceEvent:
    """An event from ``invoices.watch()``.

    ``event`` is ``"settled"`` or ``"expired"``, or ``"timeout"`` when the wait ran out: ``data`` is the
    current state; read again or watch again.
    """

    event: Literal["settled", "expired", "timeout"]
    data: InvoiceResponse


@dataclass(frozen=True)
class PaymentEvent:
    """An event from ``payments.watch()``.

    ``event`` is ``"settled"`` or ``"failed"``, or ``"timeout"`` when the wait ran out: ``data`` is the
    current state; read again or watch again.
    """

    event: Literal["settled", "failed", "timeout"]
    data: PaymentResponse


WalletEventType = Literal[
    "invoice.created",
    "invoice.settled",
    "payment.created",
    "payment.settled",
    "payment.failed",
]


@dataclass(frozen=True)
class WalletEvent:
    """An event from ``events.stream()``.

    ``data`` is the invoice or payment as a dict with snake_case keys, named like the fields of
    ``InvoiceResponse`` and ``PaymentResponse``. Keys a partial payload leaves out (for example
    ``actual_fee`` on ``payment.created``) are absent.
    """

    event: WalletEventType
    created_at: str
    data: dict[str, Any]


# ---------------------------------------------------------------------------
# JSON key mapping (snake_case <-> camelCase)
# ---------------------------------------------------------------------------

def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def _to_snake(name: str) -> str:
    return re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name).lower()


def to_camel(data: dict[str, Any]) -> dict[str, Any]:
    return {_to_camel(k): v for k, v in data.items() if v is not None}


def from_camel(data: dict[str, Any]) -> dict[str, Any]:
    return {_to_snake(k): v for k, v in data.items()}


def parse(cls: type[T], data: dict[str, Any]) -> T:
    mapped = from_camel(data)
    fields = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    return cls(**{k: v for k, v in mapped.items() if k in fields})


# ---------------------------------------------------------------------------
# SSE payload decoding
# ---------------------------------------------------------------------------

def snake_keys(value: Any) -> Any:
    """Convert object keys to snake_case, recursively.

    Event payloads use snake_case on the wire. Keys already in snake_case pass through unchanged and
    camelCase keys are converted, so both spellings decode the same way.
    """
    if isinstance(value, dict):
        return {_to_snake(k): snake_keys(v) for k, v in value.items()}
    if isinstance(value, list):
        return [snake_keys(v) for v in value]
    return value


def parse_event_data(cls: type[T], data: dict[str, Any]) -> T:
    """Decode an SSE payload into *cls*. Fields missing from the payload become None instead of raising."""
    mapped = snake_keys(data)
    fields = cls.__dataclass_fields__  # type: ignore[attr-defined]
    kwargs = {k: v for k, v in mapped.items() if k in fields}
    for name, f in fields.items():
        if name not in kwargs and f.default is MISSING and f.default_factory is MISSING:
            kwargs[name] = None
    return cls(**kwargs)
