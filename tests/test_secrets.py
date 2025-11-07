from __future__ import annotations

import datetime as dt

import httpx
import pytest

from kiket_sdk.client import KiketClient
from kiket_sdk.exceptions import SecretStoreError
from kiket_sdk.secrets import ExtensionSecretManager


class MockTransport(httpx.MockTransport):
    pass


def isoformat(dt_obj: dt.datetime) -> str:
    return dt_obj.replace(microsecond=0).isoformat()


@pytest.mark.asyncio
async def test_list_secrets_parses_timestamps():
    now = dt.datetime.now(dt.timezone.utc)

    async def handler(request: httpx.Request):
        assert request.url.path == "/api/v1/extensions/ext.test/secrets"
        payload = [
            {
                "key": "API_KEY",
                "created_at": isoformat(now),
                "updated_at": isoformat(now),
            }
        ]
        return httpx.Response(200, json=payload)

    client = KiketClient("https://example.invalid", "wk_test")
    client._client = httpx.AsyncClient(transport=MockTransport(handler), base_url=client.base_url)  # type: ignore[attr-defined]

    async with client:
        manager = ExtensionSecretManager(client, "ext.test")
        secrets = await manager.list()

    assert len(secrets) == 1
    secret = secrets[0]
    assert secret.key == "API_KEY"
    assert secret.created_at.tzinfo is not None
    assert secret.updated_at.tzinfo is not None


@pytest.mark.asyncio
async def test_get_secret_returns_value():
    async def handler(request: httpx.Request):
        assert request.url.path == "/api/v1/extensions/ext.test/secrets/API_KEY"
        return httpx.Response(200, json={"key": "API_KEY", "value": "123", "created_at": None, "updated_at": None})

    client = KiketClient("https://example.invalid", "wk_test")
    client._client = httpx.AsyncClient(transport=MockTransport(handler), base_url=client.base_url)  # type: ignore[attr-defined]

    async with client:
        manager = ExtensionSecretManager(client, "ext.test")
        secret = await manager.get("API_KEY")

    assert secret.value == "123"


@pytest.mark.asyncio
async def test_set_secret_requires_value():
    client = KiketClient("https://example.invalid", "wk_test")
    async with client:
        manager = ExtensionSecretManager(client, "ext.test")
        with pytest.raises(SecretStoreError):
            await manager.set("API_KEY", "")


@pytest.mark.asyncio
async def test_set_secret_posts_payload():
    async def handler(request: httpx.Request):
        assert request.url.path == "/api/v1/extensions/ext.test/secrets"
        body = httpx.Response(200, content=request.content).json()
        assert body == {"secret": {"key": "API_KEY", "value": "123"}}
        return httpx.Response(201, json={"key": "API_KEY"})

    client = KiketClient("https://example.invalid", "wk_test")
    client._client = httpx.AsyncClient(transport=MockTransport(handler), base_url=client.base_url)  # type: ignore[attr-defined]

    async with client:
        manager = ExtensionSecretManager(client, "ext.test")
        await manager.set("API_KEY", "123")


@pytest.mark.asyncio
async def test_delete_secret_success():
    async def handler(request: httpx.Request):
        assert request.url.path == "/api/v1/extensions/ext.test/secrets/API_KEY"
        return httpx.Response(204)

    client = KiketClient("https://example.invalid", "wk_test")
    client._client = httpx.AsyncClient(transport=MockTransport(handler), base_url=client.base_url)  # type: ignore[attr-defined]

    async with client:
        manager = ExtensionSecretManager(client, "ext.test")
        await manager.delete("API_KEY")


@pytest.mark.asyncio
async def test_missing_extension_id_raises():
    client = KiketClient("https://example.invalid", "wk_test")
    async with client:
        manager = ExtensionSecretManager(client)
        with pytest.raises(SecretStoreError):
            await manager.list()
