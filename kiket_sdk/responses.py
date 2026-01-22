"""Response helpers for building properly formatted extension responses.

These helpers ensure your extension returns data in the format Kiket expects,
including support for output_fields which are displayed in the configuration UI.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Response:
    """Base response class for extension handlers."""

    status: str
    message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {"status": self.status, "metadata": self.metadata}
        if self.message is not None:
            result["message"] = self.message
        return result


@dataclass
class AllowResponse(Response):
    """Success response that allows the operation to proceed."""

    status: str = "allow"


@dataclass
class DenyResponse(Response):
    """Response that denies/rejects the operation."""

    status: str = "deny"


@dataclass
class PendingResponse(Response):
    """Response indicating async operation is pending."""

    status: str = "pending"


def allow(
    message: str | None = None,
    data: dict[str, Any] | None = None,
    output_fields: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build an allow response with optional output fields.

    Output fields are displayed in the extension configuration UI after setup,
    allowing extensions to expose generated data like email addresses, URLs,
    or status information.

    Args:
        message: Optional success message
        data: Additional metadata to include in the response
        output_fields: Key-value pairs to display in configuration UI

    Returns:
        Properly formatted response dict for Kiket

    Example:
        >>> allow(
        ...     message="Successfully configured",
        ...     data={"route_id": 123},
        ...     output_fields={"inbound_email": "abc@parse.example.com"}
        ... )
        {'status': 'allow', 'message': 'Successfully configured',
         'metadata': {'route_id': 123, 'output_fields': {'inbound_email': 'abc@parse.example.com'}}}
    """
    metadata = dict(data) if data else {}
    if output_fields:
        metadata["output_fields"] = output_fields

    result: dict[str, Any] = {"status": "allow", "metadata": metadata}
    if message is not None:
        result["message"] = message
    return result


def deny(message: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a deny response.

    Args:
        message: Reason for denial
        data: Additional metadata to include in the response

    Returns:
        Properly formatted response dict for Kiket

    Example:
        >>> deny(message="Invalid credentials", data={"error_code": "AUTH_FAILED"})
        {'status': 'deny', 'message': 'Invalid credentials',
         'metadata': {'error_code': 'AUTH_FAILED'}}
    """
    return {
        "status": "deny",
        "message": message,
        "metadata": data or {},
    }


def pending(message: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a pending response for async operations.

    Args:
        message: Status message
        data: Additional metadata to include in the response

    Returns:
        Properly formatted response dict for Kiket

    Example:
        >>> pending(message="Awaiting approval", data={"job_id": "abc123"})
        {'status': 'pending', 'message': 'Awaiting approval',
         'metadata': {'job_id': 'abc123'}}
    """
    return {
        "status": "pending",
        "message": message,
        "metadata": data or {},
    }
