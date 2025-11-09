"""Helpers for querying workflow SLA events."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .client import KiketClient


class ExtensionSlaEventsClient:
    """Thin wrapper around the extension SLA events endpoint."""

    def __init__(self, client: KiketClient, project_id: int | str) -> None:
        if project_id is None or str(project_id).strip() == "":
            raise ValueError("project_id is required for SLA queries")

        self._client = client
        self._project_id = str(project_id)

    async def list(
        self,
        *,
        issue_id: int | str | None = None,
        state: str | None = None,
        limit: int | None = None,
    ) -> Mapping[str, Any]:
        """Return SLA events for the project."""
        params: dict[str, str] = {"project_id": self._project_id}
        if issue_id is not None:
            params["issue_id"] = str(issue_id)
        if state is not None:
            params["state"] = state
        if limit is not None:
            params["limit"] = str(limit)

        response = await self._client.get("/api/v1/ext/sla/events", params=params)
        return response.json()
