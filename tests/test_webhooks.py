from __future__ import annotations

import datetime
import json

from kiket_sdk import KiketSDK


def build_sdk() -> KiketSDK:
    sdk = KiketSDK(
        webhook_secret="secret",
        workspace_token="wk_test",
        extension_id="ext.test",
        extension_version="1.2.3",
    )

    @sdk.webhook("issue.created", version="v1")
    async def handle_issue(payload, context):
        assert payload["issue"]["id"] == 1
        assert context.event == "issue.created"
        assert context.event_version == "v1"
        assert "Authorization" in context.client._build_headers({})  # type: ignore[attr-defined]  # noqa: SLF001
        assert context.extension_id == "ext.test"
        assert context.extension_version == "1.2.3"
        assert context.secrets is context.endpoints.secrets
        return {"received": True}

    return sdk


def sign_payload(
    payload: dict[str, object],
    secret: str,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, object]:
    body = json.dumps(payload)
    import hashlib
    import hmac

    signature = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-Kiket-Signature": signature,
        "X-Kiket-Timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
    }
    if extra_headers:
        headers.update(extra_headers)
    return {
        "body": body,
        "headers": headers,
    }


def test_webhook_dispatch_success():
    sdk = build_sdk()
    client = sdk.create_test_client()
    payload = {"issue": {"id": 1}}
    signed = sign_payload(payload, "secret", {"X-Kiket-Event-Version": "v1"})

    response = client.post(
        "/webhooks/issue.created",
        data=signed["body"],
        headers=signed["headers"],
    )

    assert response.status_code == 200
    assert response.json() == {"received": True}


def test_invalid_signature_returns_unauthorized():
    sdk = build_sdk()
    client = sdk.create_test_client()
    payload = {"issue": {"id": 1}}

    response = client.post(
        "/webhooks/issue.created",
        data=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 401


def test_missing_handler_returns_not_found():
    sdk = build_sdk()
    client = sdk.create_test_client()
    signed = sign_payload({"ping": True}, "secret", {"X-Kiket-Event-Version": "v1"})

    response = client.post(
        "/webhooks/unknown.event",
        data=signed["body"],
        headers=signed["headers"],
    )

    assert response.status_code == 404


def test_health_endpoint_exposes_metadata():
    sdk = build_sdk()
    client = sdk.create_test_client()

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["extension_id"] == "ext.test"
    assert payload["extension_version"] == "1.2.3"
    assert payload["registered_events"] == ["issue.created@v1"]


def test_versioned_handler_dispatch_by_header():
    sdk = KiketSDK(webhook_secret="secret", workspace_token="wk_test")

    @sdk.webhook("issue.created", version="v1")
    def handle_v1(payload, context):
        assert context.event_version == "v1"
        return {"version": "v1"}

    @sdk.webhook("issue.created", version="v2")
    def handle_v2(payload, context):
        assert context.event_version == "v2"
        return {"version": "v2"}

    client = sdk.create_test_client()
    signed = sign_payload({"issue": {"id": 1}}, "secret", {"X-Kiket-Event-Version": "v2"})

    response = client.post(
        "/webhooks/issue.created",
        data=signed["body"],
        headers=signed["headers"],
    )

    assert response.status_code == 200
    assert response.json() == {"version": "v2"}


def test_versioned_handler_dispatch_by_path():
    sdk = KiketSDK(webhook_secret="secret", workspace_token="wk_test")

    @sdk.webhook("issue.created", version="2024-10-01")
    def handler(payload, context):
        assert context.event_version == "2024-10-01"
        return {"version": context.event_version}

    client = sdk.create_test_client()
    signed = sign_payload({"issue": {"id": 1}}, "secret")

    response = client.post(
        "/v/2024-10-01/webhooks/issue.created",
        data=signed["body"],
        headers=signed["headers"],
    )

    assert response.status_code == 200
    assert response.json() == {"version": "2024-10-01"}


def test_unknown_version_returns_not_found():
    sdk = KiketSDK(webhook_secret="secret", workspace_token="wk_test")

    @sdk.webhook("issue.created", version="v1")
    def handler(payload, context):
        return {"version": "v1"}

    client = sdk.create_test_client()
    signed = sign_payload({"issue": {"id": 1}}, "secret", {"X-Kiket-Event-Version": "v9"})

    response = client.post(
        "/webhooks/issue.created",
        data=signed["body"],
        headers=signed["headers"],
    )

    assert response.status_code == 404
    assert "version 'v9'" in response.json()["detail"]


def test_missing_version_returns_bad_request():
    sdk = KiketSDK(webhook_secret="secret", workspace_token="wk_test")

    @sdk.webhook("issue.created", version="v1")
    def handler(payload, context):
        return {"ok": True}

    client = sdk.create_test_client()
    signed = sign_payload({"issue": {"id": 1}}, "secret")

    response = client.post(
        "/webhooks/issue.created",
        data=signed["body"],
        headers=signed["headers"],
    )

    assert response.status_code == 400
    assert "Event version required" in response.json()["detail"]


def test_runtime_token_passes_through_context_and_headers():
    sdk = KiketSDK(
        workspace_token="wk_test",
        extension_id="ext.runtime",
    )

    observed: dict[str, str | None] = {}

    @sdk.webhook("issue.created", version="v1")
    async def handle(payload, context):  # noqa: ANN001
        observed["runtime_token"] = context.auth.runtime_token
        headers = context.client._build_headers({})  # type: ignore[attr-defined] # noqa: SLF001
        observed["header_token"] = headers.get("X-Kiket-Runtime-Token")
        observed["token_type"] = context.auth.token_type
        observed["scope_count"] = len(context.auth.scopes)
        return {"ok": True}

    client = sdk.create_test_client()
    payload = {
        "issue": {"id": 1},
        "authentication": {
            "runtime_token": "rt_token",
            "token_type": "runtime",
            "expires_at": "2025-11-10T00:00:00Z",
            "scopes": ["ext.api.read", "ext.secrets.read"],
        },
    }
    signed = sign_payload(payload, "secret", {"X-Kiket-Event-Version": "v1"})

    response = client.post(
        "/webhooks/issue.created",
        data=signed["body"],
        headers=signed["headers"],
    )

    assert response.status_code == 200
    assert observed["runtime_token"] == "rt_token"
    assert observed["header_token"] == "rt_token"
    assert observed["token_type"] == "runtime"
    assert observed["scope_count"] == 2
