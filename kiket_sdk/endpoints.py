"""High-level client for Kiket extension endpoints."""
from __future__ import annotations

from typing import Any, TypedDict

from .client import KiketClient
from .custom_data import ExtensionCustomDataClient
from .intake_forms import IntakeFormsClient
from .secrets import ExtensionSecretManager
from .sla import ExtensionSlaEventsClient


class RateLimitInfo(TypedDict):
    """Shape of the `/api/v1/ext/rate_limit` response."""

    limit: int
    remaining: int
    window_seconds: int
    reset_in: int


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

    def custom_data(self, project_id: int | str) -> ExtensionCustomDataClient:
        """Return a helper for interacting with the custom data API."""
        return ExtensionCustomDataClient(self._client, project_id=project_id)

    def sla_events(self, project_id: int | str) -> ExtensionSlaEventsClient:
        """Return a helper for querying SLA alerts for a project."""
        return ExtensionSlaEventsClient(self._client, project_id)

    def intake_forms(self, project_id: int | str) -> IntakeFormsClient:
        """Return a helper for managing intake forms and submissions."""
        return IntakeFormsClient(self._client, project_id)

    async def rate_limit(self) -> RateLimitInfo:
        """Fetch the current extension-specific rate limit window."""
        response = await self._client.get("/api/v1/ext/rate_limit")
        payload = response.json()
        data = payload.get("rate_limit") or {}
        return {
            "limit": int(data.get("limit", 0) or 0),
            "remaining": int(data.get("remaining", 0) or 0),
            "window_seconds": int(data.get("window_seconds", 0) or 0),
            "reset_in": int(data.get("reset_in", 0) or 0),
        }

    def _version_headers(self) -> dict[str, str]:
        if not self._event_version:
            return {}
        return {"X-Kiket-Event-Version": self._event_version}
