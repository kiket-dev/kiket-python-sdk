"""Utilities for replaying webhook payloads against handlers."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from kiket_sdk import KiketSDK


def replay_payload(sdk: KiketSDK, event: str, payload_file: str | Path) -> Any:
    """Replay a recorded payload against the SDK handlers.

    Parameters
    ----------
    sdk:
        SDK instance with handlers registered.
    event:
        Name of the webhook event to replay.
    payload_file:
        Path to the JSON payload captured from production logs.
    """

    path = Path(payload_file)
    body = path.read_text()
    client = TestClient(sdk.app)
    response = client.post(
        f"/webhooks/{event}",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    response.raise_for_status()
    return response.json()
