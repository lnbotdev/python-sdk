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
    """Network fee actually charged in sats (0.25% plus Lightning routing). None until settled."""
    reference: str | None = None
    preimage: str | None = None
    tx_number: int | None = None
    failure_reason: str | None = None
    created_at: str | None = None
    settled_at: str | None = None
    stage: str | None = None
    """Where the payment is, more precisely than ``status``: one of the ``PaymentStage`` values. More may be
    added, so for a stage you don't know, go by ``status``. None from an API that doesn't send it."""
    status_detail: str | None = None
    """A sentence to show the user as is: what is happening while in progress, the ``failure_reason`` once
    failed. None once settled."""
    retry_until: str | None = None
    """Only with stage ``"retrying"``: until when it is retried (ISO 8601). If it still can't be sent by then,
    it fails within about a minute and the funds are released. None otherwise."""


class PaymentStage:
    """Known values of ``PaymentResponse.stage``.

    ``stage`` is a plain string: more values may be added, so for one you don't know, go by ``status``.
    A payment can go from ``processing`` back to ``pending`` (``retrying``): treat both as in progress.
    """

    QUEUED = "queued"
    """With status ``pending``: waiting to be sent."""
    RETRYING = "retrying"
    """With status ``pending``: not sent yet, retried until ``retry_until``, then failed with the funds released."""
    SENDING = "sending"
    """With status ``pending`` or ``processing``: being sent (or transferred to another ln.bot wallet)."""
    IN_FLIGHT = "in_flight"
    """With status ``processing``: sent; the Lightning network is completing it, usually within seconds."""
    CONFIRMING = "confirming"
    """With status ``processing``: checking with the Lightning network whether it went out. The funds stay on hold."""
    ON_HOLD = "on_hold"
    """With status ``processing``: interrupted by an earlier version of the service and held until reviewed."""
    SETTLED = "settled"
    """With status ``settled``."""
    FAILED = "failed"
    """With status ``failed``: ``status_detail`` is the failure reason."""


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
    """Estimated network fee in sats (0.25% plus Lightning routing). None without an amount or if no estimate is available. 0 if internal."""
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
    """Network fee actually charged in sats (0.25% plus Lightning routing). None until settled."""


# ---------------------------------------------------------------------------
# Service status
# ---------------------------------------------------------------------------

class ServiceState:
    """Known values of a service status, overall and per component.

    Statuses are plain strings: more values may be added, so never fail on one you don't know.
    """

    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    OUTAGE = "outage"
    UNKNOWN = "unknown"
    """Not measured for 5 minutes: the numbers are as old as ``updated_at``."""


class NoticeLevel:
    """Known values of ``StatusNotice.level``. More may be added."""

    INFO = "info"
    """No effect on the status."""
    WARNING = "warning"
    """The overall status is at least ``degraded``."""
    OUTAGE = "outage"
    """The overall status is ``outage``."""


@dataclass(frozen=True)
class StatusNotice:
    """A message from the operators."""

    level: str
    """``"info"``, ``"warning"`` or ``"outage"`` (see ``NoticeLevel``). More may be added."""
    message: str
    """Up to 500 characters, to show as is."""
    since: str | None = None
    """When it was posted (ISO 8601)."""
    until: str | None = None
    """When it was taken down (ISO 8601). Always None from ``status()``; None in ``status_history()`` while it is still up."""


@dataclass(frozen=True)
class SendingComponent:
    """Lightning payments out."""

    status: str
    """See ``ServiceState``."""
    in_progress: int
    """Payments being sent now."""
    by_stage: dict[str, int]
    """Those payments by stage (``"queued"``, ``"retrying"``, ``"in_flight"`` and so on; see ``PaymentStage``).
    Stages with none are left out, so it can be empty. More stages may appear."""
    sent_last_hour: int
    """Payments sent in the last hour."""
    failed_last_hour: int
    """Payments that failed in the last hour, for any reason."""
    service_failures_last_hour: int
    """Of those, the ones the service caused. The rest were the invoice's or the route's fault."""
    longest_wait_seconds: float | None = None
    """How long the oldest payment in progress has waited. None when there is none."""
    median_seconds: float | None = None
    """Request-to-settlement time over the last hour, median. None when nothing was sent."""
    p95_seconds: float | None = None
    """Request-to-settlement time over the last hour, 95th percentile. None when nothing was sent."""


@dataclass(frozen=True)
class ReceivingComponent:
    """Lightning payments in."""

    status: str
    """See ``ServiceState``."""
    credited_last_hour: int
    """Incoming payments credited in the last hour."""
    credit_backlog: int | None = None
    """Incoming payments waiting to be credited now. None when it could not be read."""


@dataclass(frozen=True)
class NodeComponent:
    """The Lightning node the service runs on."""

    status: str
    """See ``ServiceState``."""
    latency_ms: int | None = None
    """How long the node took to answer, in milliseconds. None when it didn't answer."""


@dataclass(frozen=True)
class WebhooksComponent:
    """Webhook delivery."""

    status: str
    """See ``ServiceState``."""
    backlog: int | None = None
    """Deliveries waiting to go out. None when it could not be read."""


@dataclass(frozen=True)
class StatusComponents:
    """Each part of the service."""

    sending: SendingComponent
    receiving: ReceivingComponent
    node: NodeComponent
    webhooks: WebhooksComponent


@dataclass(frozen=True)
class ServiceStatusResponse:
    """The service right now, from ``status()``. Measured about once a minute."""

    status: str
    """Overall: ``"operational"``, ``"degraded"``, ``"outage"`` or ``"unknown"`` (see ``ServiceState``). More may be added."""
    components: StatusComponents
    updated_at: str | None = None
    """When it was measured (ISO 8601). None if it never was."""
    notice: StatusNotice | None = None
    """A message from the operators, or None."""


@dataclass(frozen=True)
class UptimeShare:
    """Percent of the measured time a part was in each state. Each is None when nothing was measured."""

    operational: float | None = None
    degraded: float | None = None
    outage: float | None = None


@dataclass(frozen=True)
class StatusUptime:
    """Uptime over the whole range, overall and per part."""

    overall: UptimeShare
    sending: UptimeShare
    receiving: UptimeShare
    node: UptimeShare
    webhooks: UptimeShare


@dataclass(frozen=True)
class SettleTimeCount:
    """One entry of the settlement-time histogram."""

    count: int
    """Payments that settled within ``up_to_seconds`` (and above the previous entry's bound)."""
    up_to_seconds: float | None = None
    """The bound in seconds: 1, 2, 3, 5, 10, 20, 30, 60, 120, 300 or 600. None for the last entry, which holds anything slower."""


@dataclass(frozen=True)
class StatusSummary:
    """The whole range at once."""

    samples: int
    """Measurements in the range, about one a minute."""
    uptime: StatusUptime
    sent: int
    failed: int
    """Failed for any reason."""
    service_failures: int
    """Of those, the ones the service caused."""
    credited: int
    """Incoming payments credited."""
    settle_times: list[SettleTimeCount]
    median_seconds: float | None = None
    """Request-to-settlement time, median; approximate (from ``settle_times``). None when nothing was sent."""
    p95_seconds: float | None = None
    """Request-to-settlement time, 95th percentile; approximate. None when nothing was sent."""
    avg_latency_ms: float | None = None
    """The node's average response time, in milliseconds."""
    max_latency_ms: int | None = None
    """The node's slowest response, in milliseconds."""


@dataclass(frozen=True)
class StatusBucketState:
    """How many of a bucket's measurements found ln.bot as a whole degraded or in an outage; the rest found it operational."""

    degraded: int
    outage: int


@dataclass(frozen=True)
class StatusBucketSending:
    """Lightning payments out, during one bucket."""

    degraded: int
    outage: int
    sent: int
    failed: int
    service_failures: int
    median_seconds: float | None = None
    p95_seconds: float | None = None
    max_in_progress: int | None = None
    """Most payments in progress at once."""
    max_wait_seconds: float | None = None
    """Longest wait of a payment in progress."""


@dataclass(frozen=True)
class StatusBucketReceiving:
    """Lightning payments in, during one bucket."""

    degraded: int
    outage: int
    credited: int
    max_backlog: int | None = None
    """Most incoming payments waiting to be credited at once."""


@dataclass(frozen=True)
class StatusBucketNode:
    """The Lightning node, during one bucket."""

    degraded: int
    outage: int
    avg_latency_ms: float | None = None
    max_latency_ms: int | None = None


@dataclass(frozen=True)
class StatusBucketWebhooks:
    """Webhook delivery, during one bucket."""

    degraded: int
    outage: int
    max_backlog: int | None = None
    """Most deliveries waiting at once."""


@dataclass(frozen=True)
class StatusBucket:
    """One bucket of ``ServiceStatusHistoryResponse.buckets``.

    ``samples`` is how many measurements it holds, about one a minute. ``0`` means it wasn't measured: its
    percentiles and gauges are None, and it is no data, neither up nor down. ``degraded`` and ``outage``
    count measurements, so a part's uptime in the bucket is ``(samples - degraded - outage) / samples``.
    """

    at: str
    """Start of the bucket (ISO 8601, aligned to UTC)."""
    samples: int
    overall: StatusBucketState
    sending: StatusBucketSending
    receiving: StatusBucketReceiving
    node: StatusBucketNode
    webhooks: StatusBucketWebhooks


@dataclass(frozen=True)
class ServiceStatusHistoryResponse:
    """The service over time, from ``status_history()``."""

    range: str
    """``"24h"``, ``"7d"``, ``"30d"`` or ``"90d"``."""
    bucket_seconds: int
    """How long each bucket is: 300 (24h), 3600 (7d), 21600 (30d) or 86400 (90d)."""
    from_: str
    """Start of the first bucket (ISO 8601). ``from`` in the JSON."""
    to: str
    """End of the range: now (ISO 8601)."""
    summary: StatusSummary
    buckets: list[StatusBucket]
    """Oldest first. Don't assume how many: the last one is still filling, so there is one more than a full range."""
    notices: list[StatusNotice]
    """The operators' notices that were up during the range, oldest first."""


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


# ---------------------------------------------------------------------------
# Service status decoding (nested responses)
# ---------------------------------------------------------------------------

def _build(cls: type[T], data: dict[str, Any], **nested: Any) -> T:
    """Like ``parse()``, with the nested fields passed in already built."""
    mapped = from_camel(data)
    fields = cls.__dataclass_fields__  # type: ignore[attr-defined]
    kwargs = {k: v for k, v in mapped.items() if k in fields}
    kwargs.update(nested)
    return cls(**kwargs)


def parse_service_status(data: dict[str, Any]) -> ServiceStatusResponse:
    """Decode ``GET /v1/status``. Unknown keys are dropped at every level; string values are kept as sent."""
    c = data["components"]
    notice = data.get("notice")
    return _build(
        ServiceStatusResponse,
        data,
        notice=parse(StatusNotice, notice) if notice is not None else None,
        components=StatusComponents(
            sending=parse(SendingComponent, c["sending"]),
            receiving=parse(ReceivingComponent, c["receiving"]),
            node=parse(NodeComponent, c["node"]),
            webhooks=parse(WebhooksComponent, c["webhooks"]),
        ),
    )


def _parse_status_bucket(b: dict[str, Any]) -> StatusBucket:
    return _build(
        StatusBucket,
        b,
        overall=parse(StatusBucketState, b["overall"]),
        sending=parse(StatusBucketSending, b["sending"]),
        receiving=parse(StatusBucketReceiving, b["receiving"]),
        node=parse(StatusBucketNode, b["node"]),
        webhooks=parse(StatusBucketWebhooks, b["webhooks"]),
    )


def parse_service_status_history(data: dict[str, Any]) -> ServiceStatusHistoryResponse:
    """Decode ``GET /v1/status/history``. Unknown keys are dropped at every level; string values are kept as sent."""
    s = data["summary"]
    uptime = s["uptime"]
    return _build(
        ServiceStatusHistoryResponse,
        data,
        from_=data["from"],
        summary=_build(
            StatusSummary,
            s,
            uptime=StatusUptime(**{part: parse(UptimeShare, uptime[part]) for part in StatusUptime.__dataclass_fields__}),
            settle_times=[parse(SettleTimeCount, t) for t in s["settleTimes"]],
        ),
        buckets=[_parse_status_bucket(b) for b in data["buckets"]],
        notices=[parse(StatusNotice, n) for n in data["notices"]],
    )
