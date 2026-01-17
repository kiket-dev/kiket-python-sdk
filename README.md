# Kiket Python SDK

> Build and run Kiket extensions with a batteries-included, strongly-typed Python toolkit.

## Features
- 🔌 **Webhook decorators** – define handlers with `@sdk.webhook("issue.created", version="v1")`.
- 🔐 **Transparent authentication** – HMAC verification for inbound payloads, workspace-token client for outbound calls.
- 🔑 **Secret manager** – list, fetch, rotate, and delete extension secrets stored in Google Secret Manager.
- 🌐 **Built-in FastAPI app** – serve extension webhooks locally or in production without extra wiring.
- 🧪 **Testing utilities** – pytest fixtures, signed-payload factories, and replay helpers to keep extensions reliable.
- 🔁 **Version-aware routing** – register multiple handlers per event (`@sdk.webhook(..., version="v2")`) and propagate version headers on outbound calls.
- 📦 **Manifest-aware defaults** – automatically loads `extension.yaml`/`manifest.yaml`, applies configuration defaults, and hydrates secrets from `KIKET_SECRET_*` environment variables.
- 📇 **Custom data client** – call `/api/v1/ext/custom_data/...` with `context.endpoints.custom_data(project_id)` using the configured extension API key.
- 📉 **Rate-limit helper** – introspect `/api/v1/ext/rate_limit` before enqueueing large jobs or retries.
- 🧱 **Typed & documented** – designed for Python 3.11+ with Ruff linting, MyPy type hints, and rich docstrings.
- 📊 **Telemetry & feedback hooks** – capture handler duration/success metrics automatically and forward them to your own feedback callback or a hosted endpoint.

## Quickstart
```shell
uv add kiket-sdk
pytest
```

```python
# main.py
from kiket_sdk import KiketSDK

sdk = KiketSDK(
    workspace_token="wk_test",
    extension_id="com.example.marketing",
    extension_version="1.0.0",
)

@sdk.webhook("issue.created", version="v1")
async def handle_issue(payload, context):
    summary = payload["issue"]["title"]
    assert context.event_version == "v1"
    await context.endpoints.log_event("issue.created", summary=summary)
    await context.secrets.set("WEBHOOK_TOKEN", "abc123")
    return {"ok": True}

@sdk.webhook("issue.created", version="v2")
async def handle_issue_v2(payload, context):
    summary = payload["issue"]["title"]
    await context.endpoints.log_event("issue.created", summary=summary, schema="v2")
    return {"ok": True, "version": context.event_version}

# The SDK will auto-bootstrap settings from extension.yaml/manifest.yaml (if present),
# read secrets from env vars like KIKET_SECRET_EXAMPLE_APIKEY, and fall back to
# KIKET_WORKSPACE_TOKEN / KIKET_WEBHOOK_SECRET environment variables when explicit
# values are not supplied. Kiket sends the event version in the request path
# (/v/{version}/webhooks/{event}) or via the `X-Kiket-Event-Version` header.

if __name__ == "__main__":
    sdk.run(host="0.0.0.0", port=8080)
```

### Custom Data Client

When your manifest declares `custom_data.permissions`, the SDK automatically uses the runtime token provided in the webhook payload for API calls via `context.client`. Use the `custom_data(project_id)` helper to list or mutate module records:

```python
@sdk.webhook("issue.created", version="v1")
async def handle_issue(payload, context):
    project_id = payload["project_id"]
    contacts = await context.endpoints.custom_data(project_id).list(
        "com.example.crm.contacts",
        "automation_records",
        limit=25,
        filters={"status": "active"},
    )

    await context.endpoints.custom_data(project_id).create(
        "com.example.crm.contacts",
        "automation_records",
        {"email": "lead@example.com", "metadata": {"source": "webhook"}},
    )
```

Under the hood the helper speaks to `/api/v1/ext/custom_data/:module/:table`, adds the required `project_id`, and returns the parsed JSON payloads.

### SLA Alert Stream

Extensions can also react to SLA warnings/breaches without polling the UI. Use the SLA helper to inspect the latest alerts for the installation:

```python
@sdk.webhook("workflow.sla_status", version="v1")
async def handle_sla(payload, context):
    project_id = payload["issue"]["project_id"]

    recent = await context.endpoints.sla_events(project_id).list(
        state="imminent",
        limit=5,
    )
    if not recent["data"]:
        return {"ok": True}

    first = recent["data"][0]
    await context.endpoints.notify(
        "SLA warning",
        f"Issue #{first['issue_id']} is {first['state']} for {first['definition']['status']}",
        level="warning",
    )

    return {"acknowledged": True}
```

### Telemetry & Feedback Hooks
Every handler invocation emits an opt-in telemetry record containing the event name, version, duration, and status (`ok` / `error`). Enable or customise reporting when instantiating the SDK:

```python
from kiket_sdk import KiketSDK, TelemetryRecord

async def feedback(record: TelemetryRecord) -> None:
    print(f"[telemetry] {record.event}@{record.version} -> {record.status} ({record.duration_ms:.2f}ms)")

sdk = KiketSDK(
    webhook_secret="secret",
    workspace_token="wk_test",
    telemetry_enabled=True,
    feedback_hook=feedback,
    telemetry_url=os.getenv("KIKET_SDK_TELEMETRY_URL"),  # optional hosted endpoint
)
```

Set `KIKET_SDK_TELEMETRY_OPTOUT=1` to disable reporting entirely. When `telemetry_url` is provided (or the environment variable is set), the SDK will POST telemetry JSON to that endpoint with best-effort retry; failures are logged and never crash handlers.

### Publishing to PyPI

When you are ready to cut a release:

1. Update the version in `pyproject.toml`.
2. Run the test suite (`PYTHONPATH=. pytest`) and linting (`ruff check .`).
3. Build distributables:
   ```bash
   uv build  # or python -m build
   ```
4. Publish to TestPyPI or PyPI:
   ```bash
   uv publish --publish-url https://upload.pypi.org/legacy/  # uses ~/.pypirc credentials
   ```
5. Tag the release (`git tag v0.x.y && git push --tags`) so the CLI and docs reference the same version.

## Roadmap
- **MVP (done):** webhook decorators, FastAPI runtime, auth verification, outbound client, testing toolkit.
- **Enhancements:** high-level endpoints (`context.endpoints.*`), richer secret tooling (rotation helpers, runtime vault adapters), typed payload utilities.
- **Sample extension:** ship a production-grade marketing automation example demonstrating multi-event handlers, manifest-driven configuration, and deployment templates.
- **Documentation:** publish quickstart, reference, cookbook, and tutorial content alongside SDK release.
- **Early access:** package for PyPI, collect telemetry/feedback before general availability (telemetry hooks + publishing checklist now available).

### Secret Helper

The `secret()` method provides a simple way to retrieve secrets with automatic fallback:

```python
# Checks payload secrets first (per-org config), falls back to ENV
slack_token = context.secret("SLACK_BOT_TOKEN")

# Example usage
@sdk.webhook("issue.created", version="v1")
async def handle_issue(payload, context):
    api_key = context.secret("API_KEY")
    if not api_key:
        raise ValueError("API_KEY not configured")
    # Use api_key...
    return {"ok": True}
```

The lookup order is:
1. **Payload secrets** (per-org configuration from `payload["secrets"]`)
2. **Environment variables** (extension defaults via `os.environ`)

This allows organizations to override extension defaults with their own credentials.

### Rate-Limit Helper

Need to throttle expensive work? Ask the runtime for the current window and remaining calls:

```python
@sdk.webhook("automation.dispatch", version="v1")
async def handle_dispatch(payload, context):
    limits = await context.endpoints.rate_limit()
    if limits["remaining"] < 5:
        await context.endpoints.notify(
            "Rate limit warning",
            f"Only {limits['remaining']} calls remain in this window",
            level="warning",
        )
        return {"deferred": True, "reset_in": limits["reset_in"]}

    # Continue with the expensive call
    return {"ok": True}
```

### Runtime Token Authentication

The Kiket platform sends a per-invocation `runtime_token` in each webhook payload. This token is automatically extracted and used for all API calls made through `context.client` and `context.endpoints`. The runtime token provides organization-scoped access and is preferred over static tokens.

```python
@sdk.webhook("issue.created", version="v1")
async def handle_issue(payload, context):
    # Access authentication context
    print(f"Token expires at: {context.auth.expires_at}")
    print(f"Scopes: {', '.join(context.auth.scopes)}")

    # API calls automatically use the runtime token
    await context.endpoints.log_event("processed", ok=True)

    return {"ok": True}
```

The `context.auth` object contains:
- `runtime_token`: The per-invocation API token
- `token_type`: Typically "runtime"
- `expires_at`: Token expiration timestamp
- `scopes`: List of granted API scopes

### Scope Checking

Extensions can declare required scopes when registering handlers. The SDK will automatically check scopes before invoking the handler and return a 403 error if insufficient.

```python
# Declare required scopes at registration time
@sdk.webhook("issue.created", version="v1", required_scopes=["issues.read", "issues.write"])
async def handle_issue(payload, context):
    # Handler only executes if scopes are present
    await context.endpoints.log_event("issue.processed", id=payload["issue"]["id"])
    return {"ok": True}

# Check scopes dynamically within the handler
@sdk.webhook("workflow.triggered", version="v1")
async def handle_workflow(payload, context):
    # Raises ScopeError if scopes are missing
    context.require_scopes("workflows.execute", "custom_data.write")

    # Continue with scope-protected operations
    await context.endpoints.custom_data(project_id).create(...)
    return {"ok": True}
```
