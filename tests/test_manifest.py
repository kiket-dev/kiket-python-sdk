from __future__ import annotations

from textwrap import dedent

import pytest

from kiket_sdk import KiketSDK
from kiket_sdk.secrets import ExtensionSecretManager


def write_manifest(tmp_path):
    manifest_text = dedent(
        """
        manifestVersion: "1.0"
        id: com.example.sdk
        version: "2.5.1"
        delivery:
          type: http
          callback:
            secret: env:TEST_WEBHOOK_SECRET
        configuration:
          properties:
            example.apiUrl:
              type: string
              default: "https://api.example.com"
            example.apiKey:
              type: string
              secret: true
        """
    ).strip()
    (tmp_path / "extension.yaml").write_text(manifest_text, encoding="utf-8")


def test_sdk_auto_loads_manifest_and_env(tmp_path, monkeypatch):
    write_manifest(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TEST_WEBHOOK_SECRET", "whsec_123")
    monkeypatch.setenv("KIKET_SECRET_EXAMPLE_APIKEY", "env-secret-456")
    monkeypatch.setenv("KIKET_WORKSPACE_TOKEN", "wk_env_token")

    sdk = KiketSDK()

    assert sdk.config.extension_id == "com.example.sdk"
    assert sdk.config.extension_version == "2.5.1"
    assert sdk.config.workspace_token == "wk_env_token"
    assert sdk.config.settings.get("example.apiUrl") == "https://api.example.com"
    assert sdk.config.settings.get("example.apiKey") == "env-secret-456"
    assert sdk.manifest is not None
    assert sdk.manifest.path.name == "extension.yaml"


@pytest.mark.asyncio
async def test_secret_manager_prefers_environment(monkeypatch):
    monkeypatch.setenv("KIKET_SECRET_SAMPLE_TOKEN", "super-secret")

    class DummyClient:
        async def get(self, *_args, **_kwargs):
            raise AssertionError("HTTP client should not be called when env secret present.")

    manager = ExtensionSecretManager(DummyClient(), "com.example.sdk")
    secret = await manager.get("sample.token")

    assert secret.value == "super-secret"
    assert secret.key == "sample.token"
