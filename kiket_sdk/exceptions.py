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
