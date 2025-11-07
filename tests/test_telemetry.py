from __future__ import annotations

import datetime
import json
from typing import List

from kiket_sdk import KiketSDK, TelemetryRecord


def sign_payload(payload: dict[str, object], secret: str, *, version: str = "v1") -> dict[str, object]:
    import hashlib
    import hmac

    body = json.dumps(payload)
    signature = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return {
        "body": body,
        "headers": {
            "Content-Type": "application/json",
            "X-Kiket-Signature": signature,
            "X-Kiket-Timestamp": timestamp,
            "X-Kiket-Event-Version": version,
        },
    }


async def _noop(record: TelemetryRecord) -> None:  # pragma: no cover - helper fallback
    return None


def test_feedback_hook_receives_success_record():
    events: List[TelemetryRecord] = []

    async def hook(record: TelemetryRecord) -> None:
        events.append(record)

    sdk = KiketSDK(
        webhook_secret="secret",
        workspace_token="wk_test",
        feedback_hook=hook,
    )

    @sdk.webhook("campaign.created", version="v1")
    async def handler(payload, context):  # noqa: ARG001
        return {"ok": True}

    client = sdk.create_test_client()
    signed = sign_payload({"campaign": {"id": 1}}, "secret")
    response = client.post("/webhooks/campaign.created", data=signed["body"], headers=signed["headers"])

    assert response.status_code == 200
    assert len(events) == 1
    record = events[0]
    assert record.event == "campaign.created"
    assert record.status == "ok"
    assert record.version == "v1"
    assert record.duration_ms >= 0


def test_feedback_hook_receives_error_record():
    events: List[TelemetryRecord] = []

    def hook(record: TelemetryRecord) -> None:
        events.append(record)

    sdk = KiketSDK(
        webhook_secret="secret",
        workspace_token="wk_test",
        feedback_hook=hook,
    )

    @sdk.webhook("campaign.created", version="v1")
    async def handler(payload, context):  # noqa: ARG001
        raise ValueError("boom")

    client = sdk.create_test_client()
    signed = sign_payload({"campaign": {"id": 1}}, "secret")
    response = client.post("/webhooks/campaign.created", data=signed["body"], headers=signed["headers"])

    assert response.status_code == 400
    assert len(events) == 1
    record = events[0]
    assert record.status == "error"
    assert record.metadata["message"] == "boom"
