"""Configuration helpers for KikET extensions."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ExtensionSettings:
    """Runtime settings exposed to handlers.

    These are resolved from the extension manifest's configuration block.
    """

    raw: Mapping[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any | None = None) -> Any | None:
        return self.raw.get(key, default)

    def require(self, key: str) -> Any:
        try:
            return self.raw[key]
        except KeyError as err:  # pragma: no cover - explicit error message
            raise KeyError(f"Missing required extension setting '{key}'") from err


@dataclass(slots=True)
class ExtensionConfig:
    """Top-level SDK configuration.

    Attributes
    ----------
    webhook_secret:
        Shared secret used for verifying inbound webhook signatures. Optional but strongly
        recommended.
    workspace_token:
        Token used for authenticating outbound calls back into Kiket.
    base_url:
        Base URL for the Kiket API. Defaults to ``https://kiket.dev`` but can be overridden
        for staging environments.
    settings:
        Optional manifest-derived settings that can be consumed by handlers.
    extension_id:
        The extension identifier (e.g. ``com.example.integration``). When provided, secret helpers
        default to this identifier so callers do not need to repeat it.
    extension_version:
        Optional semantic version of the extension runtime. Useful for logging, health checks,
        and dispatching version-aware handlers.
    """

    webhook_secret: str | None = None
    workspace_token: str | None = None
    base_url: str = "https://kiket.dev"
    settings: ExtensionSettings = field(default_factory=ExtensionSettings)
    extension_id: str | None = None
    extension_version: str | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> ExtensionConfig:
        return cls(
            webhook_secret=data.get("webhook_secret"),
            workspace_token=data.get("workspace_token"),
            base_url=data.get("base_url", "https://kiket.dev"),
            settings=ExtensionSettings(raw=data.get("settings", {})),
            extension_id=data.get("extension_id"),
            extension_version=data.get("extension_version"),
        )
