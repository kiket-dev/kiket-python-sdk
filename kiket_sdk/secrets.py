"""Helpers for managing extension secrets via the Kiket API."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, Mapping, Optional, TYPE_CHECKING

from .exceptions import OutboundRequestError, SecretStoreError
from .utils import environment_secret_name

if TYPE_CHECKING:  # pragma: no cover - import for typing only
    from .client import KiketClient


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        # Support both ISO8601 with timezone and UTC shorthand
        sanitized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(sanitized)
    except ValueError:
        return None


@dataclass(slots=True)
class SecretMetadata:
    key: str
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


@dataclass(slots=True)
class SecretValue(SecretMetadata):
    value: str


class ExtensionSecretManager:
    """High-level helper for CRUD operations on extension secrets."""

    def __init__(self, client: "KiketClient", extension_id: Optional[str] = None) -> None:
        self._client = client
        self._extension_id = extension_id

    def with_extension(self, extension_id: str) -> "ExtensionSecretManager":
        return ExtensionSecretManager(self._client, extension_id)

    async def list(self, *, extension_id: Optional[str] = None) -> List[SecretMetadata]:
        ext = self._resolve_extension_id(extension_id)
        try:
            response = await self._client.get(f"/api/v1/extensions/{ext}/secrets")
        except OutboundRequestError as exc:
            raise SecretStoreError(f"Failed to list secrets for extension '{ext}'") from exc

        payload = response.json()
        if not isinstance(payload, list):
            raise SecretStoreError("Unexpected response format from secret listing")

        return [
            SecretMetadata(
                key=item.get("key", ""),
                created_at=_parse_timestamp(item.get("created_at")),
                updated_at=_parse_timestamp(item.get("updated_at")),
            )
            for item in payload
        ]

    async def get(self, key: str, *, extension_id: Optional[str] = None) -> SecretValue:
        env_secret = _get_env_secret(key)
        if env_secret is not None:
            return SecretValue(
                key=key,
                created_at=None,
                updated_at=None,
                value=env_secret,
            )

        ext = self._resolve_extension_id(extension_id)
        try:
            response = await self._client.get(f"/api/v1/extensions/{ext}/secrets/{key}")
        except OutboundRequestError as exc:
            raise SecretStoreError(f"Failed to load secret '{key}' for extension '{ext}'") from exc

        data = response.json()
        if not isinstance(data, Mapping) or "value" not in data:
            raise SecretStoreError("Unexpected response format from secret detail")

        return SecretValue(
            key=data.get("key", key),
            created_at=_parse_timestamp(data.get("created_at")),
            updated_at=_parse_timestamp(data.get("updated_at")),
            value=str(data["value"]),
        )

    async def set(self, key: str, value: str, *, extension_id: Optional[str] = None) -> None:
        if not value:
            raise SecretStoreError("Secret value cannot be blank")

        ext = self._resolve_extension_id(extension_id)
        payload = {"secret": {"key": key, "value": value}}
        try:
            await self._client.post(f"/api/v1/extensions/{ext}/secrets", json=payload)
        except OutboundRequestError as exc:
            raise SecretStoreError(f"Failed to persist secret '{key}' for extension '{ext}'") from exc

    async def delete(self, key: str, *, extension_id: Optional[str] = None) -> None:
        ext = self._resolve_extension_id(extension_id)
        try:
            await self._client.delete(f"/api/v1/extensions/{ext}/secrets/{key}")
        except OutboundRequestError as exc:
            raise SecretStoreError(f"Failed to delete secret '{key}' for extension '{ext}'") from exc

    def _resolve_extension_id(self, explicit: Optional[str]) -> str:
        resolved = explicit or self._extension_id
        if not resolved:
            raise SecretStoreError("Extension ID is required when managing secrets")
        return resolved


def _get_env_secret(key: str) -> Optional[str]:
    env_name = environment_secret_name(key)
    value = os.getenv(env_name)
    return value if value is not None else None
