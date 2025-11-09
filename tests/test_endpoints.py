from __future__ import annotations

import json

import httpx
import pytest

from kiket_sdk.client import KiketClient
from kiket_sdk.custom_data import ExtensionCustomDataClient
from kiket_sdk.endpoints import ExtensionEndpoints
from kiket_sdk.sla import ExtensionSlaEventsClient


class MockTransport(httpx.MockTransport):
    pass


@pytest.mark.asyncio
async def test_log_event_invokes_api():
    calls = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        calls["method"] = request.method
        calls["url"] = str(request.url)
        calls["json"] = request.content.decode()
        calls["headers"] = dict(request.headers)
        return httpx.Response(status_code=204)

    client = KiketClient(base_url="https://example.invalid", workspace_token="wk_test")
    client._client = httpx.AsyncClient(transport=MockTransport(handler), base_url=client.base_url)  # type: ignore[attr-defined]

    async with client as http_client:
        endpoints = ExtensionEndpoints(http_client)
        await endpoints.log_event("issue.created", issue_id=1)

    assert calls["method"] == "POST"
    assert calls["url"].endswith("/api/v1/extensions/logs")
    payload = json.loads(calls["json"])
    assert payload["message"] == "issue.created"
    assert payload["metadata"]["issue_id"] == 1
    assert "X-Kiket-Event-Version" not in calls["headers"]


@pytest.mark.asyncio
async def test_version_header_added_when_event_version_present():
    calls = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        calls["headers"] = dict(request.headers)
        return httpx.Response(status_code=204)

    client = KiketClient(base_url="https://example.invalid", workspace_token="wk_test")
    client._client = httpx.AsyncClient(transport=MockTransport(handler), base_url=client.base_url)  # type: ignore[attr-defined]

    async with client as http_client:
        endpoints = ExtensionEndpoints(http_client, event_version="v2025")
        await endpoints.notify("Ping", "Hello world")

    header_key = next((k for k in calls["headers"] if k.lower() == "x-kiket-event-version"), None)
    assert header_key is not None
    assert calls["headers"][header_key] == "v2025"


def test_custom_data_helper_returns_client():
    client = object()
    endpoints = ExtensionEndpoints(client)  # type: ignore[arg-type]
    helper = endpoints.custom_data(project_id=123)
    assert isinstance(helper, ExtensionCustomDataClient)


def test_sla_helper_returns_client():
    client = object()
    endpoints = ExtensionEndpoints(client)  # type: ignore[arg-type]
    helper = endpoints.sla_events(project_id="proj-1")
    assert isinstance(helper, ExtensionSlaEventsClient)
