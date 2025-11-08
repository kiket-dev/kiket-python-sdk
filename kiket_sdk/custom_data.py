"""Helpers for interacting with the custom data API."""
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

from .client import KiketClient


class ExtensionCustomDataClient:
    """Thin wrapper around the extension custom data endpoints."""

    def __init__(self, client: KiketClient, project_id: str | int) -> None:
        if project_id is None:
            raise ValueError("project_id is required for custom data operations")

        self._client = client
        self._project_id = project_id

    async def list(
        self,
        module_key: str,
        table: str,
        *,
        limit: int = 50,
        filters: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        response = await self._client.get(
            self._path(module_key, table),
            params=self._base_params(limit=limit, filters=filters),
        )
        return response.json()

    async def get(self, module_key: str, table: str, record_id: str | int) -> Mapping[str, Any]:
        response = await self._client.get(
            self._path(module_key, table, record_id),
            params=self._base_params(),
        )
        return response.json()

    async def create(self, module_key: str, table: str, record: Mapping[str, Any]) -> Mapping[str, Any]:
        response = await self._client.post(
            self._path(module_key, table),
            params=self._base_params(),
            json={"record": record},
        )
        return response.json()

    async def update(
        self,
        module_key: str,
        table: str,
        record_id: str | int,
        record: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        response = await self._client.patch(
            self._path(module_key, table, record_id),
            params=self._base_params(),
            json={"record": record},
        )
        return response.json()

    async def delete(self, module_key: str, table: str, record_id: str | int) -> None:
        await self._client.delete(
            self._path(module_key, table, record_id),
            params=self._base_params(),
        )

    def _path(self, module_key: str, table: str, record_id: str | int | None = None) -> str:
        encoded_module = quote(module_key, safe="")
        encoded_table = quote(table, safe="")
        path = f"/api/v1/ext/custom_data/{encoded_module}/{encoded_table}"
        if record_id is not None:
            path += f"/{record_id}"
        return path

    def _base_params(
        self,
        *,
        limit: int | None = None,
        filters: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"project_id": self._project_id}
        if limit is not None:
            params["limit"] = limit
        if filters:
            params["filters"] = json.dumps(filters)
        return params
