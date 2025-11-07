"""High-level client for Kiket extension endpoints."""
from __future__ import annotations

from typing import Any

from .client import KiketClient
from .secrets import ExtensionSecretManager


class ExtensionEndpoints:
    """Typed helpers for calling common Kiket extension endpoints."""

    def __init__(
        self,
        client: KiketClient,
        extension_id: str | None = None,
        *,
        event_version: str | None = None,
    ) -> None:
        self._client = client
        self.secrets = ExtensionSecretManager(client, extension_id)
        self._event_version = event_version

    async def log_event(self, message: str, **metadata: Any) -> None:
        payload: dict[str, Any] = {"message": message, "metadata": metadata}
        await self._client.post(
            "/api/v1/extensions/logs",
            json=payload,
            headers=self._version_headers(),
        )

    async def emit_metric(self, name: str, value: float, unit: str = "count") -> None:
        payload = {"name": name, "value": value, "unit": unit}
        await self._client.post(
            "/api/v1/extensions/metrics",
            json=payload,
            headers=self._version_headers(),
        )

    async def notify(self, title: str, body: str, level: str = "info") -> None:
        payload = {"title": title, "body": body, "level": level}
        await self._client.post(
            "/api/v1/extensions/notifications",
            json=payload,
            headers=self._version_headers(),
        )

    def _version_headers(self) -> dict[str, str]:
        if not self._event_version:
            return {}
        return {"X-Kiket-Event-Version": self._event_version}
