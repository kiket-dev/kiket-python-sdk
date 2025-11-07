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
    webhook_secret="sh_123",
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
