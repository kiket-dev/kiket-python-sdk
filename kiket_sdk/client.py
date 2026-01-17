"""HTTP client helpers for interacting with the Kiket API."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from .exceptions import OutboundRequestError, SecretStoreError


class KiketClient:
    """Async HTTP client that injects workspace token headers automatically."""

    def __init__(
        self,
        base_url: str,
        workspace_token: str | None,
        runtime_token: str | None = None,
        *,
        timeout: float = 15.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.workspace_token = workspace_token
        self.runtime_token = runtime_token
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    async def __aenter__(self) -> KiketClient:
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self._client.__aexit__(*args)

    async def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = await self._client.request(
                method,
                path,
                headers=self._build_headers(kwargs.pop("headers", {})),
                **kwargs,
            )
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            raise OutboundRequestError(f"Kiket API returned {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:  # pragma: no cover - network failures
            raise OutboundRequestError("Failed to communicate with Kiket API") from exc

    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("PUT", path, **kwargs)

    async def patch(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("PATCH", path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("DELETE", path, **kwargs)

    async def store_secret(self, extension_id: str, key: str, value: str) -> None:
        if not value:
            raise SecretStoreError("Secret value cannot be blank")

        payload = {"secret": {"key": key, "value": value}}
        try:
            await self.post(f"/api/v1/extensions/{extension_id}/secrets", json=payload)
        except OutboundRequestError as exc:
            raise SecretStoreError("Failed to store extension secret") from exc

    async def delete_secret(self, extension_id: str, key: str) -> None:
        try:
            await self.delete(f"/api/v1/extensions/{extension_id}/secrets/{key}")
        except OutboundRequestError as exc:
            raise SecretStoreError("Failed to delete extension secret") from exc

    def _build_headers(self, headers: Mapping[str, str]) -> Mapping[str, str]:
        merged = {"Accept": "application/json", **headers}
        if self.workspace_token:
            merged.setdefault("Authorization", f"Bearer {self.workspace_token}")
        if self.runtime_token:
            merged.setdefault("X-Kiket-Runtime-Token", self.runtime_token)
        return merged
