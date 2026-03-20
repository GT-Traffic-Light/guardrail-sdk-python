# guardrail-sdk

Official Python SDK for the [Guardrail API](https://api.code.aitrafficlight.com).

Requires Python 3.9+ and [`httpx`](https://www.python-httpx.org/).

## Install

```bash
pip install guardrail-sdk
```

## Quick Start

```python
from guardrail import GuardrailClient

client = GuardrailClient(
    "https://api.code.aitrafficlight.com",
    token="gr_live_xxxxxxxxx",
)

# Initiate a scan
scan = client.scan("https://github.com/owner/repo", "github", "standard")
print(scan["scanId"], scan["status"])

# Guest checkout (no auth required)
checkout = client.guest_checkout(
    email="user@example.com",
    name="Jane Smith",
    tier="pro",
    interval="month",
)

if "clientSecret" in checkout:
    # Mount Stripe.js with checkout["clientSecret"] …

    # Apply a promo code — must use the token from guest_checkout
    result = client.apply_coupon(
        subscription_id=checkout["subscriptionId"],
        promotion_code="SUMMER40",
        checkout_token=checkout["checkoutToken"],
    )
    print(result["discount"]["label"])  # e.g. "40% off"
```

## Authentication

```python
# Pass token at construction time
client = GuardrailClient(BASE_URL, token="gr_live_…")

# Or update at runtime
client.set_token(new_token)

# Or pass per-call
me = client.me(token="gr_live_…")
```

## Context Manager

```python
with GuardrailClient(BASE_URL, token=TOKEN) as client:
    print(client.health())
```

## Device Flow (CLI login)

```python
import time

auth = client.device_authorize()
print(f"Visit {auth['verification_uri']} and enter: {auth['user_code']}")

while True:
    time.sleep(auth["interval"])
    poll = client.device_token(auth["device_code"])
    if "access_token" in poll:
        client.set_token(poll["access_token"])
        break
    if poll.get("error") == "access_denied":
        raise SystemExit("Login denied")
```

## Error Handling

```python
from guardrail import GuardrailClient, ApiError

try:
    client.get_subscription()
except ApiError as e:
    print(e.status, e.code, str(e))
```

## Development

```bash
pip install -e ".[dev]"
pytest
mypy guardrail
```
