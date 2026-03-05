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

### Send sats

```python
w.payments.create(target="alice@ln.bot", amount=500)
```

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
```

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
from lnbot import LnBot, BadRequestError, UnauthorizedError, NotFoundError, ConflictError, LnBotError

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

# Pay the challenge (client side)
result = w.l402.pay(www_authenticate=challenge.www_authenticate)

# Verify a token (server side, stateless)
v = w.l402.verify(authorization=result.authorization)
print(v.valid)
```

---

## Features

- **Zero extra dependencies** — only `httpx`
- **Wallet-scoped API** — `ln.wallet(id)` returns a typed scope with all sub-resources
- **Sync + async** — `LnBot` and `AsyncLnBot` with identical APIs
- **Typed exceptions** — `BadRequestError`, `NotFoundError`, `ConflictError`, `UnauthorizedError`, `ForbiddenError`
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
