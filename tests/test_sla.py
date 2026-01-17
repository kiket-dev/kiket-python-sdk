from __future__ import annotations

import httpx
import pytest

from kiket_sdk.client import KiketClient
from kiket_sdk.sla import ExtensionSlaEventsClient


class MockTransport(httpx.MockTransport):
    pass


@pytest.mark.asyncio
async def test_list_builds_query_params():
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(status_code=200, json={"data": []})

    client = KiketClient(base_url="https://example.invalid", workspace_token="wk_test", runtime_token="rt_test")
    client._client = httpx.AsyncClient(transport=MockTransport(handler), base_url=client.base_url)  # type: ignore[attr-defined]

    async with client as http_client:
        sla_client = ExtensionSlaEventsClient(http_client, project_id=42)
        await sla_client.list(issue_id=7, state="breached", limit=5)

    assert "/api/v1/ext/sla/events" in captured["url"]
    assert "project_id=42" in captured["url"]
    assert "issue_id=7" in captured["url"]
    assert "state=breached" in captured["url"]
    assert "limit=5" in captured["url"]
