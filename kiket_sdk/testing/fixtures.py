"""Pytest fixtures for extension testing."""
from __future__ import annotations

from typing import Any, Callable, Dict

try:  # pragma: no cover - optional dependency
    import pytest
except ImportError:  # pragma: no cover - fixture module available only with pytest
    pytest = None  # type: ignore

from fastapi.testclient import TestClient

from kiket_sdk import KiketSDK
from kiket_sdk.auth import verify_signature


def webhook_payload_factory(secret: str | None = None) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    """Return a factory that produces signed webhook payloads."""

    def factory(body: Dict[str, Any]) -> Dict[str, Any]:
        import json
        import hmac
        import hashlib

        payload = json.dumps(body)
        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "X-Kiket-Timestamp": "1970-01-01T00:00:00Z",
        }
        if secret:
            signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
            headers["X-Kiket-Signature"] = signature
        return {"body": payload, "headers": headers}

    return factory


def kiket_client_fixture(sdk: KiketSDK) -> TestClient:
    """Create a synchronous test client for the provided SDK."""

    return TestClient(sdk.app)


if pytest:  # pragma: no cover

    @pytest.fixture
    def kiket_sdk_fixture() -> KiketSDK:
        return KiketSDK(webhook_secret="test", workspace_token="wk_test")

    @pytest.fixture
    def client(kiket_sdk_fixture: KiketSDK) -> TestClient:
        return kiket_client_fixture(kiket_sdk_fixture)

    @pytest.fixture
    def signed_payload():
        return webhook_payload_factory(secret="test")
