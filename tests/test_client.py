from __future__ import annotations

import httpx
import pytest

from kiket_sdk.client import KiketClient
from kiket_sdk.exceptions import OutboundRequestError, SecretStoreError


class MockTransport(httpx.MockTransport):
    pass


@pytest.mark.asyncio
async def test_client_request_success(monkeypatch):
    async def handler(request: httpx.Request):
        assert request.headers["Authorization"].startswith("Bearer ")
        return httpx.Response(200, json={"ok": True})

    client = KiketClient("https://example.invalid", "wk_test")
    client._client = httpx.AsyncClient(transport=MockTransport(handler), base_url=client.base_url)  # type: ignore[attr-defined]
    async with client as c:
        response = await c.get("/ping")
        assert response.json() == {"ok": True}


@pytest.mark.asyncio
async def test_client_request_error(monkeypatch):
    async def handler(request: httpx.Request):
        return httpx.Response(500)

    client = KiketClient("https://example.invalid", "wk_test")
    client._client = httpx.AsyncClient(transport=MockTransport(handler), base_url=client.base_url)  # type: ignore[attr-defined]
    async with client as c:
        with pytest.raises(OutboundRequestError):
            await c.get("/ping")


@pytest.mark.asyncio
async def test_secret_store_error(monkeypatch):
    async def handler(_: httpx.Request):
        return httpx.Response(500)

    client = KiketClient("https://example.invalid", "wk_test")
    client._client = httpx.AsyncClient(transport=MockTransport(handler), base_url=client.base_url)  # type: ignore[attr-defined]
    async with client as c:
        with pytest.raises(SecretStoreError):
            await c.store_secret("ext.test", "api_key", "value")


@pytest.mark.asyncio
async def test_store_secret_sends_payload(monkeypatch):
    async def handler(request: httpx.Request):
        assert request.method == "POST"
        assert request.url.path == "/api/v1/extensions/ext.test/secrets"
        body = httpx.Response(200, content=request.content).json()
        assert body == {"secret": {"key": "api_key", "value": "value"}}
        return httpx.Response(201)

    client = KiketClient("https://example.invalid", "wk_test")
    client._client = httpx.AsyncClient(transport=MockTransport(handler), base_url=client.base_url)  # type: ignore[attr-defined]
    async with client as c:
        await c.store_secret("ext.test", "api_key", "value")


@pytest.mark.asyncio
async def test_runtime_token_header_takes_precedence():
    async def handler(request: httpx.Request):
        assert request.headers["X-Runtime-Token"] == "rt_test"
        assert "X-Kiket-API-Key" not in request.headers
        return httpx.Response(200, json={"ok": True})

    client = KiketClient("https://example.invalid", "wk_test", "api_test", runtime_token="rt_test")
    client._client = httpx.AsyncClient(transport=MockTransport(handler), base_url=client.base_url)  # type: ignore[attr-defined]
    async with client as c:
        response = await c.get("/ping")
        assert response.json() == {"ok": True}
