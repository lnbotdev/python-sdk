# ln.bot

[![PyPI version](https://img.shields.io/pypi/v/lnbot)](https://pypi.org/project/lnbot/)
[![PyPI downloads](https://img.shields.io/pypi/dm/lnbot)](https://pypi.org/project/lnbot/)
[![Python](https://img.shields.io/pypi/pyversions/lnbot)](https://pypi.org/project/lnbot/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](./LICENSE)

**The official Python SDK for [ln.bot](https://ln.bot)** — Bitcoin for AI Agents.

Give your AI agents, apps, and services access to Bitcoin over the Lightning Network. Create wallets, send and receive sats, and get real-time payment notifications.

```python
from lnbot import LnBot

ln = LnBot(api_key="uk_...")
w = ln.wallet("wal_...")

invoice = w.invoices.create(amount=1000, memo="Coffee")
```

> ln.bot also ships a **[TypeScript SDK](https://www.npmjs.com/package/@lnbot/sdk)**, **[C# SDK](https://www.nuget.org/packages/LnBot)**, **[Go SDK](https://pkg.go.dev/github.com/lnbotdev/go-sdk)**, **[Rust SDK](https://crates.io/crates/lnbot)**, **[CLI](https://ln.bot/docs)**, and **[MCP server](https://ln.bot/docs)**.

---

## Install

```bash
pip install lnbot
```

---

## Quick start

### Register an account

```python
from lnbot import LnBot

ln = LnBot()
account = ln.register()
print(account.primary_key)
print(account.recovery_passphrase)
```

### Create a wallet

```python
ln = LnBot(api_key=account.primary_key)
wallet = ln.wallets.create()
print(wallet.wallet_id)
```

### Receive sats

```python
w = ln.wallet(wallet.wallet_id)

invoice = w.invoices.create(amount=1000, memo="Payment for task #42")
print(invoice.bolt11)
```

### Wait for payment (SSE)

```python
for event in w.invoices.watch(invoice.number):
    if event.event == "settled":
        print("Paid!")
        break
```

An `expired` invoice is not always final: one paid just before it expired can turn `settled` a moment later. Before giving up, check again with `w.invoices.get(invoice.number)`, or keep listening for `invoice.settled` on `w.events.stream()` or a webhook.

If the wait runs out first (`timeout=` seconds, 60 by default, 300 at most), the last event is `timeout`: `event.data` is the current state; read again or watch again.

Event stream and webhook payloads use snake_case on the wire (`max_fee`, `created_at`). The SDK converts event payloads to the same field names as its REST types; a webhook handler reads the snake_case JSON as is.

### Send sats

```python
payment = w.payments.create(target="alice@ln.bot", amount=500)
```

Leave `max_fee` unset. The server defaults it to 1% of the amount (minimum 20 sats), which covers the network fee (0.25% plus Lightning routing) for most payments. Only the fee estimate plus a small buffer is held while the payment is in flight. On success the wallet is debited `amount + actual_fee + service_fee`.

If the fee estimate is above the limit, `create` raises `BadRequestError` (for example `Network fee estimate (X sats) exceeds maxFee (Y sats).`). Pass a higher `max_fee` only if you accept that fee.

A payment that can't be sent fails quickly, and its funds are released at once: within about half a minute if the Lightning service refuses it, or after 10 minutes of automatic retries for a temporary problem (`stage` `"retrying"`, until `retry_until`). If its invoice expires first, it fails then, with `Invoice expired before it could be paid.` A payment stays `processing` longer only when its funds are already on the Lightning network: it settles or fails as soon as the network does, usually within seconds, and is never refunded while it could still be paid. If `watch()` runs out of time first, it ends with a `timeout` event whose `data` is the current state: check again with `w.payments.get(payment.number)` or watch again. A failed payment carries the reason in `failure_reason`: show it as is, and when it ends in "Please try again.", sending the payment again later can work.

### Payment stages

Every payment carries `stage`, which says where it is more precisely than `status`, and `status_detail`, a sentence to show your user as is:

```python
from lnbot import PaymentStage

p = w.payments.get(payment.number)
print(p.status, p.stage, p.status_detail)

if p.stage == PaymentStage.RETRYING:
    print("Retried until", p.retry_until)
```

| `stage` | With `status` | `status_detail` |
|---------|---------------|-----------------|
| `queued` | `pending` | Waiting to be sent. |
| `retrying` | `pending` | Not sent yet; retrying for a few minutes. If it still can't be sent, it fails and the funds are released. |
| `sending` | `pending` or `processing` | Being sent. Between ln.bot wallets: Being transferred to the recipient's wallet. |
| `in_flight` | `processing` | Sent; the Lightning network is completing it, usually within seconds. |
| `confirming` | `processing` | Checking with the Lightning network whether it went out. The funds stay on hold until then. |
| `on_hold` | `processing` | Interrupted by an earlier version of the service and on hold until it is reviewed. The funds are held, not lost. |
| `settled` | `settled` | `None` |
| `failed` | `failed` | The `failure_reason` |

A `retrying` payment carries `retry_until`: if it still can't be sent by then, it fails within about a minute and the funds are released. A payment can go from `processing` back to `pending` when it is retried, so treat both as in progress.

`stage` is a plain string and more stages may be added: for one you don't know, go by `status`. When the API doesn't send them, `stage`, `status_detail` and `retry_until` are `None`.

`watch()` events carry the same fields, but the stream only ends with `settled`, `failed` or `timeout` (the payment's current state): it doesn't send stage changes as they happen. Webhooks and `w.events.stream()` don't carry `stage`.

### Price a payment before sending

```python
quote = w.payments.resolve(target="alice@example.com", amount=500)
print(quote.network_fee_estimate, quote.service_fee, quote.total)

if quote.fee_warning:
    print(quote.fee_warning)  # sending without max_fee would be rejected
```

For a BOLT11 invoice, leave out `amount` (or pass the invoice amount). `quote.internal` is `True` when the recipient is a wallet on ln.bot, which makes the transfer free.

Pricing a Lightning address or LNURL fetches an invoice from the recipient, so it is slower. Call it once the amount is settled, not on every keystroke.

`resolve` raises `BadRequestError` when the target can't be paid, for example `Recipient not found.` for an unknown ln.bot address or `Cannot transfer to yourself.` for your own. When the amount is outside the recipient's range, the JSON in the error's `body` also carries `min` and `max`.

### Send everything

Resolve a Lightning address or LNURL without an amount to get `max_sendable`, the most this wallet can send there now after fees:

```python
quote = w.payments.resolve(target="alice@example.com")

if quote.max_sendable:
    w.payments.create(target="alice@example.com", amount=quote.max_sendable)
```

Don't pass `max_fee` here: `max_sendable` assumes the default. It is `0` when the balance can't cover the recipient's minimum.

### Check balance

```python
info = w.get()
print(f"{info.available} sats available")
```

---

## Wallet-scoped API

All wallet operations go through a `Wallet` handle obtained via `ln.wallet(wallet_id)`:

```python
w = ln.wallet("wal_abc123")

# Wallet info
info = w.get()
w.update(name="production")

# Sub-resources
w.key           # Wallet key management (wk_ keys)
w.invoices      # Create, list, get, watch invoices
w.payments      # Send, list, get, watch, resolve payments
w.addresses     # Create, list, delete, transfer Lightning addresses
w.transactions  # List transaction history
w.webhooks      # Create, list, delete webhook endpoints
w.events        # Real-time SSE event stream
w.l402          # L402 paywall authentication
```

Account-level operations stay on the client:

```python
ln.register()                       # Register new account
ln.me()                             # Get authenticated identity
ln.wallets.create()                 # Create wallet
ln.wallets.list()                   # List wallets
ln.keys.rotate(0)                   # Rotate account key
ln.invoices.create_for_wallet(...)  # Public invoice by wallet ID
ln.invoices.create_for_address(...) # Public invoice by address
ln.status()                         # Service status now (no key needed)
ln.status_history("7d")             # Service status over time (no key needed)
```

---

## Service status

Whether ln.bot is working, measured about once a minute. Both calls are public: they need no API key and no wallet.

```python
from lnbot import LnBot

ln = LnBot()
s = ln.status()
print(s.status)  # "operational", "degraded", "outage" or "unknown"

if s.notice:
    print(s.notice.level, s.notice.message)  # a message from the operators

sending = s.components.sending
print(sending.in_progress, sending.by_stage, sending.median_seconds)
```

`s.components` has `sending` (payments out), `receiving` (payments in), `node` (the Lightning node) and `webhooks` (deliveries), each with its own `status`. `unknown` means nothing was measured for 5 minutes, and the numbers are as old as `s.updated_at`. A number that wasn't measured is `None`, for example `sending.median_seconds` when nothing was sent.

```python
h = ln.status_history("7d")
print(h.summary.uptime.overall.operational)  # percent of the measured time

for b in h.buckets:
    if b.samples == 0:
        continue  # not measured: no data, neither up nor down
    uptime = (b.samples - b.overall.degraded - b.overall.outage) / b.samples
    print(b.at, f"{uptime:.1%}", b.sending.sent, b.sending.p95_seconds)
```

| `range` | One bucket per | `bucket_seconds` |
|---------|----------------|------------------|
| `24h` (default) | 5 minutes | 300 |
| `7d` | hour | 3600 |
| `30d` | 6 hours | 21600 |
| `90d` | day | 86400 |

Buckets are aligned to UTC and the last one is still filling, so don't assume how many there are. `h.summary` covers the whole range, with `settle_times` as a histogram of settlement times, and `h.notices` lists the operators' notices during it. The range starts at `h.from_` (`from` in the JSON). Any other `range` raises `BadRequestError`.

Statuses and notice levels are plain strings, like `stage`, and new values may be added: compare them with the constants in `ServiceState` and `NoticeLevel`, and handle a value you don't know.

Both calls share the API's limit for public routes, 10 requests a minute per IP; over it they raise `TooManyRequestsError` (status 429). The status changes about once a minute, so there is no point asking more often.

---

## Async support

Every method has an async equivalent via `AsyncLnBot`:

```python
from lnbot import AsyncLnBot

async with AsyncLnBot(api_key="uk_...") as ln:
    w = ln.wallet("wal_...")
    info = await w.get()
    invoice = await w.invoices.create(amount=1000)

    async for event in w.invoices.watch(invoice.number):
        if event.event == "settled":
            print("Paid!")
            break
```

---

## Error handling

```python
from lnbot import LnBot, BadRequestError, UnauthorizedError, NotFoundError, ConflictError, TooManyRequestsError, LnBotError

try:
    w.payments.create(target="invalid", amount=100)
except BadRequestError:
    ...  # 400
except UnauthorizedError:
    ...  # 401
except NotFoundError:
    ...  # 404
except ConflictError:
    ...  # 409
except TooManyRequestsError:
    ...  # 429
except LnBotError as e:
    print(e.status, e.body)
```

## Configuration

```python
from lnbot import LnBot

ln = LnBot(
    api_key="uk_...",                 # or set LNBOT_API_KEY env var
    base_url="https://api.ln.bot",    # optional — this is the default
    timeout=30.0,                     # optional — request timeout in seconds
)
```

The API key can also be provided via the `LNBOT_API_KEY` environment variable. If both are provided, the constructor argument takes precedence.

---

## L402 paywalls

```python
w = ln.wallet("wal_...")

# Create a challenge (server side)
challenge = w.l402.create_challenge(amount=100, description="API access", expiry_seconds=3600)

# Pay the challenge (client side). max_fee works as for payments: leave it unset for the default.
result = w.l402.pay(www_authenticate=challenge.www_authenticate)
print(result.fee)  # network fee charged

# Verify a token (server side, stateless)
v = w.l402.verify(authorization=result.authorization)
print(v.valid)
```

---

## Features

- **Zero extra dependencies** — only `httpx`
- **Wallet-scoped API** — `ln.wallet(id)` returns a typed scope with all sub-resources
- **Sync + async** — `LnBot` and `AsyncLnBot` with identical APIs
- **Typed exceptions** — `BadRequestError`, `NotFoundError`, `ConflictError`, `UnauthorizedError`, `ForbiddenError`, `TooManyRequestsError`
- **SSE support** — `watch()` returns an iterator/async iterator for real-time events
- **Dataclass responses** — all responses are frozen dataclasses

## Requirements

- Python 3.10+
- Get your API key at [ln.bot](https://ln.bot)

## Links

- [ln.bot](https://ln.bot) — website
- [Documentation](https://ln.bot/docs)
- [GitHub](https://github.com/lnbotdev)
- [PyPI](https://pypi.org/project/lnbot/)

## Other SDKs

- [TypeScript SDK](https://github.com/lnbotdev/typescript-sdk) · [npm](https://www.npmjs.com/package/@lnbot/sdk)
- [C# SDK](https://github.com/lnbotdev/csharp-sdk) · [NuGet](https://www.nuget.org/packages/LnBot)
- [Go SDK](https://github.com/lnbotdev/go-sdk) · [pkg.go.dev](https://pkg.go.dev/github.com/lnbotdev/go-sdk)
- [Rust SDK](https://github.com/lnbotdev/rust-sdk) · [crates.io](https://crates.io/crates/lnbot) · [docs.rs](https://docs.rs/lnbot)

## License

MIT
