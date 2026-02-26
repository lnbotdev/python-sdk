# lnbot

[![PyPI version](https://img.shields.io/pypi/v/lnbot)](https://pypi.org/project/lnbot/)
[![PyPI downloads](https://img.shields.io/pypi/dm/lnbot)](https://pypi.org/project/lnbot/)
[![Python](https://img.shields.io/pypi/pyversions/lnbot)](https://pypi.org/project/lnbot/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](./LICENSE)

**The official Python SDK for [LnBot](https://ln.bot)** — Bitcoin for AI Agents.

Give your AI agents, apps, and services access to Bitcoin over the Lightning Network. Create wallets, send and receive sats, and get real-time payment notifications.

```python
from lnbot import LnBot

ln = LnBot(api_key="lnbot_...")

invoice = ln.invoices.create(amount=1000, memo="Coffee")
ln.payments.create(target="alice@ln.bot", amount=500)
```

> LnBot also ships a **[TypeScript SDK](https://www.npmjs.com/package/@lnbot/sdk)**, **[CLI](https://ln.bot/docs)**, and **[MCP server](https://ln.bot/docs)**.

---

## Install

```bash
pip install lnbot
```

---

## Quick start

### 1. Create a wallet

```python
from lnbot import LnBot

ln = LnBot()
wallet = ln.wallets.create(name="my-agent")

print(wallet.primary_key)          # your API key
print(wallet.address)              # your Lightning address
print(wallet.recovery_passphrase)  # back this up!
```

### 2. Receive sats

```python
ln = LnBot(api_key=wallet.primary_key)

invoice = ln.invoices.create(amount=1000, memo="Payment for task #42")
print(invoice.bolt11)
```

### 3. Wait for payment

```python
for event in ln.invoices.wait_for_settlement(invoice.number):
    if event.event == "settled":
        print("Paid!")
```

### 4. Send sats

```python
ln.payments.create(target="alice@ln.bot", amount=500)
ln.payments.create(target="lnbc10u1p...")
```

### 5. Check balance

```python
wallet = ln.wallets.current()
print(f"{wallet.available} sats available")
```

---

## Async support

Every method has an async equivalent via `AsyncLnBot`:

```python
from lnbot import AsyncLnBot

async with AsyncLnBot(api_key="lnbot_...") as ln:
    wallet = await ln.wallets.current()
    invoice = await ln.invoices.create(amount=1000)

    async for event in ln.invoices.wait_for_settlement(invoice.number):
        if event.event == "settled":
            print("Paid!")
```

---

## Error handling

```python
from lnbot import LnBot, BadRequestError, UnauthorizedError, NotFoundError, ConflictError, LnBotError

try:
    ln.payments.create(target="invalid", amount=100)
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
    api_key="lnbot_...",            # or set LNBOT_API_KEY env var
    base_url="https://api.ln.bot",  # optional — this is the default
    timeout=30.0,                   # optional — request timeout in seconds
)
```

The API key can also be provided via the `LNBOT_API_KEY` environment variable. If both are provided, the constructor argument takes precedence.

---

## API reference

### Wallets

| Method | Description |
| --- | --- |
| `ln.wallets.create(name=)` | Create a new wallet (no auth required) |
| `ln.wallets.current()` | Get current wallet info and balance |
| `ln.wallets.update(name=)` | Update wallet name |

### Invoices

| Method | Description |
| --- | --- |
| `ln.invoices.create(amount=, memo=, reference=)` | Create a BOLT11 invoice |
| `ln.invoices.list(limit=, after=)` | List invoices |
| `ln.invoices.get(number)` | Get invoice by number |
| `ln.invoices.wait_for_settlement(number, timeout=)` | SSE stream for settlement/expiry |

### Payments

| Method | Description |
| --- | --- |
| `ln.payments.create(target=, amount=, ...)` | Send sats to a Lightning address or BOLT11 invoice |
| `ln.payments.list(limit=, after=)` | List payments |
| `ln.payments.get(number)` | Get payment by number |

### Addresses

| Method | Description |
| --- | --- |
| `ln.addresses.create(address=)` | Create a random or vanity Lightning address |
| `ln.addresses.list()` | List all addresses |
| `ln.addresses.delete(address)` | Delete an address |
| `ln.addresses.transfer(address, target_wallet_key=)` | Transfer address to another wallet |

### Transactions

| Method | Description |
| --- | --- |
| `ln.transactions.list(limit=, after=)` | List credit and debit transactions |

### Webhooks

| Method | Description |
| --- | --- |
| `ln.webhooks.create(url=)` | Register a webhook endpoint (max 10) |
| `ln.webhooks.list()` | List all webhooks |
| `ln.webhooks.delete(webhook_id)` | Delete a webhook |

### API Keys

| Method | Description |
| --- | --- |
| `ln.keys.list()` | List API keys (metadata only) |
| `ln.keys.rotate(slot)` | Rotate a key (0 = primary, 1 = secondary) |

### Backup & Restore

| Method | Description |
| --- | --- |
| `ln.backup.recovery()` | Generate 12-word BIP-39 recovery passphrase |
| `ln.backup.passkey_begin()` | Start passkey backup (WebAuthn) |
| `ln.backup.passkey_complete(session_id=, attestation=)` | Complete passkey backup |
| `ln.restore.recovery(passphrase=)` | Restore wallet with recovery passphrase |
| `ln.restore.passkey_begin()` | Start passkey restore (WebAuthn) |
| `ln.restore.passkey_complete(session_id=, assertion=)` | Complete passkey restore |

---

## Requirements

- Python 3.10+
- Get your API key at [ln.bot](https://ln.bot)

## Links

- [ln.bot](https://ln.bot) — website
- [Documentation](https://ln.bot/docs)
- [GitHub](https://github.com/lnbotdev)
- [TypeScript SDK](https://www.npmjs.com/package/@lnbot/sdk)

## License

MIT
