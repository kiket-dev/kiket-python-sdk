"""Lightweight telemetry helpers for the Python SDK."""
from __future__ import annotations

import asyncio
import logging
import os
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger("kiket_sdk.telemetry")


FeedbackHook = Callable[["TelemetryRecord"], Awaitable[None] | None]


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class TelemetryRecord:
    """Payload representing a single handler invocation."""

    event: str
    version: str
    status: str
    duration_ms: float
    extension_id: str | None
    extension_version: str | None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: time.time())


class TelemetryReporter:
    """Dispatches telemetry/feedback hooks for handler invocations."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        telemetry_url: str | None = None,
        feedback_hook: FeedbackHook | None = None,
        extension_id: str | None,
        extension_version: str | None,
    ) -> None:
        self.enabled = enabled and not _is_truthy(os.getenv("KIKET_SDK_TELEMETRY_OPTOUT"))
        self.telemetry_url = telemetry_url or os.getenv("KIKET_SDK_TELEMETRY_URL")
        self.feedback_hook = feedback_hook
        self.extension_id = extension_id
        self.extension_version = extension_version

    async def record(self, event: str, version: str, status: str, duration_ms: float, **metadata: Any) -> None:
        if not self.enabled:
            return

        record = TelemetryRecord(
            event=event,
            version=version,
            status=status,
            duration_ms=duration_ms,
            extension_id=self.extension_id,
            extension_version=self.extension_version,
            metadata=metadata,
        )

        tasks: list[Awaitable[Any]] = []

        if self.feedback_hook:
            try:
                maybe_awaitable = self.feedback_hook(record)
                if asyncio.iscoroutine(maybe_awaitable):
                    tasks.append(maybe_awaitable)
            except Exception as exc:  # pragma: no cover - feedback errors are soft-fail
                logger.debug("Feedback hook failed: %s", exc)

        if self.telemetry_url:
            tasks.append(self._post(record))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:  # pragma: no branch - loop executes when tasks exist
                if isinstance(result, Exception):
                    logger.debug("Telemetry dispatch failed: %s", result)

    async def _post(self, record: TelemetryRecord) -> None:
        if not self.telemetry_url:  # pragma: no cover - defensive check
            return

        payload = {
            "event": record.event,
            "version": record.version,
            "status": record.status,
            "duration_ms": record.duration_ms,
            "timestamp": record.timestamp,
            "extension_id": record.extension_id,
            "extension_version": record.extension_version,
            "metadata": record.metadata,
        }

        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                await client.post(self.telemetry_url, json=payload)
        except Exception as exc:  # pragma: no cover - external network issues
            logger.debug("Unable to POST telemetry: %s", exc)
