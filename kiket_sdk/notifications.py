"""Notification types for extension development."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class NotificationRequest:
    """Standard notification request for extension delivery.

    Attributes:
        message: The notification message content
        channel_type: Type of channel ("channel", "dm", "group")
        channel_id: ID of the channel (for channel_type="channel")
        recipient_id: ID of the recipient (for channel_type="dm")
        format: Message format ("plain", "markdown", "html")
        priority: Notification priority ("low", "normal", "high", "urgent")
        metadata: Additional metadata for the notification
        thread_id: Optional thread ID for threaded messages
        attachments: Optional list of attachments
    """

    message: str
    channel_type: str
    channel_id: str | None = None
    recipient_id: str | None = None
    format: str = "markdown"
    priority: str = "normal"
    metadata: dict[str, Any] | None = None
    thread_id: str | None = None
    attachments: list[dict[str, Any]] | None = None

    def __post_init__(self) -> None:
        """Validate notification request."""
        if not self.message:
            raise ValueError("Message content is required")

        if self.channel_type not in ("channel", "dm", "group"):
            raise ValueError(f"Invalid channel_type: {self.channel_type}")

        if self.channel_type == "dm" and not self.recipient_id:
            raise ValueError("recipient_id is required for channel_type='dm'")

        if self.channel_type == "channel" and not self.channel_id:
            raise ValueError("channel_id is required for channel_type='channel'")

        if self.format not in ("plain", "markdown", "html"):
            raise ValueError(f"Invalid format: {self.format}")

        if self.priority not in ("low", "normal", "high", "urgent"):
            raise ValueError(f"Invalid priority: {self.priority}")


@dataclass
class NotificationResponse:
    """Standard notification response from extension.

    Attributes:
        success: Whether the notification was delivered successfully
        message_id: ID of the delivered message
        delivered_at: Timestamp when message was delivered
        error: Error message if delivery failed
        retry_after: Seconds to wait before retrying (for rate limits)
    """

    success: bool
    message_id: str | None = None
    delivered_at: datetime | None = None
    error: str | None = None
    retry_after: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert response to dictionary for JSON serialization."""
        result: dict[str, Any] = {"success": self.success}

        if self.message_id is not None:
            result["message_id"] = self.message_id

        if self.delivered_at is not None:
            result["delivered_at"] = self.delivered_at.isoformat()

        if self.error is not None:
            result["error"] = self.error

        if self.retry_after is not None:
            result["retry_after"] = self.retry_after

        return result


@dataclass
class ChannelValidationRequest:
    """Request to validate a notification channel.

    Attributes:
        channel_id: ID of the channel to validate
        channel_type: Type of channel ("channel", "dm", "group")
    """

    channel_id: str
    channel_type: str = "channel"


@dataclass
class ChannelValidationResponse:
    """Response from channel validation.

    Attributes:
        valid: Whether the channel is valid and accessible
        error: Error message if validation failed
        metadata: Additional channel metadata (name, member count, etc.)
    """

    valid: bool
    error: str | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert response to dictionary for JSON serialization."""
        result: dict[str, Any] = {"valid": self.valid}

        if self.error is not None:
            result["error"] = self.error

        if self.metadata is not None:
            result["metadata"] = self.metadata

        return result
