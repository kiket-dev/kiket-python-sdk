"""Authentication utilities."""
from __future__ import annotations

from datetime import datetime, timezone
import hmac
import hashlib
from typing import Mapping

from .exceptions import AuthenticationError

ALLOWED_SKEW_SECONDS = 300


def verify_signature(secret: str | None, body: bytes, headers: Mapping[str, str]) -> None:
    """Verify the HMAC signature on an inbound webhook.

    Parameters
    ----------
    secret:
        Shared secret configured for the extension. If ``None`` no verification is performed.
    body:
        Raw request body.
    headers:
        Incoming HTTP headers.
    """

    if not secret:
        return

    signature = headers.get("X-Kiket-Signature")
    if not signature:
        raise AuthenticationError("Missing X-Kiket-Signature header")

    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):  # pragma: no cover - constant time
        raise AuthenticationError("Invalid signature")

    timestamp = headers.get("X-Kiket-Timestamp")
    if timestamp:
        _validate_timestamp(timestamp)


def _validate_timestamp(timestamp: str) -> None:
    try:
        request_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:  # pragma: no cover - invalid timestamp
        raise AuthenticationError("Invalid X-Kiket-Timestamp header") from exc

    now = datetime.now(tz=timezone.utc)
    delta = abs((now - request_time).total_seconds())
    if delta > ALLOWED_SKEW_SECONDS:
        raise AuthenticationError("Request timestamp outside allowed window")
