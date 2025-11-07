"""General utility helpers for the Kiket SDK."""
from __future__ import annotations

import os
import re

ENV_SECRET_PREFIX = "KIKET_SECRET_"


def environment_secret_name(key: str) -> str:
    """Convert a manifest/config secret key into a canonical env var name."""
    normalized = re.sub(r"[^A-Z0-9]+", "_", key.upper())
    normalized = normalized.strip("_")
    return f"{ENV_SECRET_PREFIX}{normalized}"


def resolve_env_reference(value: str | None) -> str | None:
    """Resolve ``env:VARIABLE`` references, returning the environment value when present."""
    if not isinstance(value, str):
        return value

    prefix = "env:"
    if value.lower().startswith(prefix):
        var_name = value[len(prefix):].strip()
        return os.getenv(var_name) if var_name else None
    return value
