"""Utilities for loading extension manifest metadata."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .utils import environment_secret_name, resolve_env_reference

DEFAULT_MANIFEST_FILENAMES = (
    "extension.yaml",
    "extension.yml",
    "manifest.yaml",
    "manifest.yml",
)


class ManifestNotFoundError(FileNotFoundError):
    """Raised when a manifest path is supplied but not found."""


@dataclass(slots=True)
class ExtensionManifest:
    """Container for manifest metadata."""

    path: Path
    raw: dict

    @property
    def extension_id(self) -> str | None:
        return (
            self.raw.get("id")
            or self.raw.get("extension", {}).get("id")
        )

    @property
    def version(self) -> str | None:
        return (
            self.raw.get("version")
            or self.raw.get("extension", {}).get("version")
        )

    @property
    def delivery_secret(self) -> str | None:
        delivery = (
            self.raw.get("delivery")
            or self.raw.get("extension", {}).get("delivery")
            or {}
        )
        if isinstance(delivery, str):
            return resolve_env_reference(delivery)

        callback = delivery.get("callback", {}) if isinstance(delivery, dict) else {}
        secret = callback.get("secret")
        return resolve_env_reference(secret)

    def configuration_properties(self) -> dict[str, dict]:
        config = (
            self.raw.get("configuration")
            or self.raw.get("extension", {}).get("configuration")
            or {}
        )
        properties = config.get("properties", {})
        if not isinstance(properties, dict):
            return {}
        return properties

    def settings_defaults(self) -> dict[str, object]:
        defaults: dict[str, object] = {}
        for key, meta in self.configuration_properties().items():
            if not isinstance(meta, dict):
                continue
            value = resolve_env_reference(meta.get("default"))
            if value is not None:
                defaults[key] = value
        return defaults

    def secret_keys(self) -> tuple[str, ...]:
        secrets = []
        for key, meta in self.configuration_properties().items():
            if isinstance(meta, dict) and meta.get("secret"):
                secrets.append(key)
        return tuple(secrets)


def load_manifest(path: str | None = None) -> ExtensionManifest | None:
    """Load an extension manifest from the provided path or default candidates."""
    candidate_path: Path | None = None

    if path:
        candidate_path = Path(path)
        if not candidate_path.is_file():
            raise ManifestNotFoundError(f"Manifest file not found at {candidate_path}")
    else:
        for name in DEFAULT_MANIFEST_FILENAMES:
            guess = Path(name)
            if guess.is_file():
                candidate_path = guess
                break

    if not candidate_path:
        return None

    data = _load_yaml(candidate_path)
    return ExtensionManifest(candidate_path, data or {})


def _load_yaml(path: Path) -> dict:
    content = path.read_text(encoding="utf-8")
    payload = yaml.safe_load(content)
    if isinstance(payload, dict):
        return payload
    return {}


def apply_secret_env_overrides(
    settings: dict[str, object],
    secret_keys: tuple[str, ...],
) -> dict[str, object]:
    """Overlay configuration settings with environment-provided secret values."""
    merged = dict(settings)
    for key in secret_keys:
        env_name = environment_secret_name(key)
        env_value = resolve_env_reference(f"env:{env_name}")
        if env_value is not None:
            merged[key] = env_value
    return merged
