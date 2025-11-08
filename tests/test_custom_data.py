from __future__ import annotations

import json

import httpx
import pytest

from kiket_sdk.client import KiketClient
from kiket_sdk.custom_data import ExtensionCustomDataClient


class MockTransport(httpx.MockTransport):
    pass


@pytest.mark.asyncio
async def test_custom_data_client_includes_project_id_and_filters():
    captured: dict[str, httpx.Request] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(status_code=200, json={"data": []})

    client = KiketClient(base_url="https://api.kiket.dev", workspace_token=None, extension_api_key="ext_123")
    client._client = httpx.AsyncClient(transport=MockTransport(handler), base_url=client.base_url)  # type: ignore[attr-defined]

    custom_data = ExtensionCustomDataClient(client, project_id=7)
    async with client:  # reuse context manager for cleanup
        await custom_data.list("com.example.module", "records", filters={"status": "open"})

    request = captured["request"]
    assert request.url.path.endswith("/api/v1/ext/custom_data/com.example.module/records")
    assert request.url.params["project_id"] == "7"
    assert json.loads(request.url.params["filters"]) == {"status": "open"}
    assert request.headers["X-Kiket-API-Key"] == "ext_123"
