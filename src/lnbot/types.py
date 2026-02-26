from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal, TypeVar

T = TypeVar("T")

InvoiceStatus = Literal["pending", "settled", "expired"]
PaymentStatus = Literal["pending", "processing", "settled", "failed"]
TransactionType = Literal["credit", "debit"]


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
    primary_key: str
    secondary_key: str
    name: str
    address: str
    recovery_passphrase: str


# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ApiKeyResponse:
    id: str
    name: str
    hint: str
    created_at: str | None = None
    last_used_at: str | None = None


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
    tx_number: int | None = None
    created_at: str | None = None
    settled_at: str | None = None
    expires_at: str | None = None


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PaymentResponse:
    number: int
    status: PaymentStatus
    amount: int
    max_fee: int
    address: str
    actual_fee: int | None = None
    reference: str | None = None
    tx_number: int | None = None
    failure_reason: str | None = None
    created_at: str | None = None
    settled_at: str | None = None


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
# SSE
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InvoiceEvent:
    event: Literal["settled", "expired"]
    data: InvoiceResponse


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
