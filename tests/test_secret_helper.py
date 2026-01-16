"""Tests for the SDK secret helper functionality."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from kiket_sdk import KiketSDK


class TestSecretHelper:
    """Tests for the _build_secret_helper method."""

    @pytest.fixture
    def sdk(self) -> KiketSDK:
        """Create a basic SDK instance for testing."""
        return KiketSDK(
            workspace_token="wk_test",
            extension_id="ext.test",
            extension_version="1.0.0",
            telemetry_enabled=False,
        )

    def test_returns_payload_secret_when_present(self, sdk: KiketSDK) -> None:
        """Payload secrets should be returned when present."""
        payload_secrets = {"SLACK_TOKEN": "payload-token", "API_KEY": "payload-key"}
        secret_helper = sdk._build_secret_helper(payload_secrets)  # noqa: SLF001

        assert secret_helper("SLACK_TOKEN") == "payload-token"
        assert secret_helper("API_KEY") == "payload-key"

    def test_falls_back_to_env_when_payload_secret_missing(self, sdk: KiketSDK) -> None:
        """Should fall back to ENV when payload secret is not present."""
        payload_secrets = {}
        secret_helper = sdk._build_secret_helper(payload_secrets)  # noqa: SLF001

        with patch.dict(os.environ, {"ENV_SECRET": "env-value"}):
            assert secret_helper("ENV_SECRET") == "env-value"

    def test_returns_none_when_secret_not_found(self, sdk: KiketSDK) -> None:
        """Should return None when secret is not in payload or ENV."""
        payload_secrets = {}
        secret_helper = sdk._build_secret_helper(payload_secrets)  # noqa: SLF001

        # Ensure env var doesn't exist
        with patch.dict(os.environ, {}, clear=True):
            assert secret_helper("NONEXISTENT") is None

    def test_payload_secrets_take_priority_over_env(self, sdk: KiketSDK) -> None:
        """Payload secrets should take priority over ENV variables."""
        payload_secrets = {"SHARED_KEY": "from-payload"}
        secret_helper = sdk._build_secret_helper(payload_secrets)  # noqa: SLF001

        with patch.dict(os.environ, {"SHARED_KEY": "from-env"}):
            assert secret_helper("SHARED_KEY") == "from-payload"

    def test_empty_payload_secret_falls_back_to_env(self, sdk: KiketSDK) -> None:
        """Empty string payload secrets should fall back to ENV."""
        payload_secrets = {"EMPTY_KEY": ""}
        secret_helper = sdk._build_secret_helper(payload_secrets)  # noqa: SLF001

        with patch.dict(os.environ, {"EMPTY_KEY": "env-value"}):
            # Empty string is falsy, so it should fall back to ENV
            assert secret_helper("EMPTY_KEY") == "env-value"

    def test_with_empty_payload_secrets_dict(self, sdk: KiketSDK) -> None:
        """Should work correctly with empty payload secrets dictionary."""
        payload_secrets = {}
        secret_helper = sdk._build_secret_helper(payload_secrets)  # noqa: SLF001

        with patch.dict(os.environ, {"ONLY_IN_ENV": "env-only-value"}):
            assert secret_helper("ONLY_IN_ENV") == "env-only-value"
