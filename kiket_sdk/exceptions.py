"""Custom exceptions used by the Kiket Python SDK."""
from __future__ import annotations


class KiketSDKError(Exception):
    """Base class for SDK errors."""


class AuthenticationError(KiketSDKError):
    """Raised when a webhook signature or token is invalid."""


class HandlerNotFoundError(KiketSDKError):
    """Raised when a webhook is received for an event without a registered handler."""


class SecretStoreError(KiketSDKError):
    """Raised when secret store operations fail."""


class OutboundRequestError(KiketSDKError):
    """Raised when outbound calls to Kiket fail."""


class AuditVerificationError(KiketSDKError):
    """Raised when blockchain audit verification operations fail."""


class ScopeError(KiketSDKError):
    """Raised when required scopes are not present."""

    def __init__(
        self,
        required_scopes: list[str],
        available_scopes: list[str],
    ) -> None:
        self.required_scopes = required_scopes
        self.available_scopes = available_scopes
        self.missing_scopes = [s for s in required_scopes if s not in available_scopes and "*" not in available_scopes]
        super().__init__(f"Insufficient scopes: missing {', '.join(self.missing_scopes)}")
