"""Routing utilities for webhook handlers."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable

Handler = Callable[..., Awaitable[object] | object]


def webhook(
    event: str,
    *,
    version: str,
    required_scopes: list[str] | None = None,
) -> Callable[[Handler], Handler]:
    """Decorator for registering webhook handlers.

    Usage
    -----
    >>> from kiket_sdk import webhook
    >>> @webhook("issue.created", version="v2", required_scopes=["issues.read"])
    ... async def handle_issue(payload, context):
    ...     ...

    The decorator marks the function with metadata inspected by :class:`~kiket_sdk.sdk.KiketSDK`.
    """

    def decorator(func: Handler) -> Handler:
        func.__kiket_event__ = event  # type: ignore[attr-defined]
        func.__kiket_version__ = version  # type: ignore[attr-defined]
        func.__kiket_required_scopes__ = required_scopes or []  # type: ignore[attr-defined]
        return func

    return decorator


class HandlerMetadata:
    """Metadata for a registered handler."""

    __slots__ = ("handler", "version", "required_scopes")

    def __init__(self, handler: Handler, version: str, required_scopes: list[str]) -> None:
        self.handler = handler
        self.version = version
        self.required_scopes = required_scopes


class HandlerRegistry:
    """In-memory registry mapping event type to handler callables per version."""

    def __init__(self) -> None:
        self._handlers: dict[str, dict[str, HandlerMetadata]] = defaultdict(dict)

    def register(
        self,
        event: str,
        handler: Handler,
        *,
        version: str,
        required_scopes: list[str] | None = None,
    ) -> None:
        validated = _coerce_version(version)
        self._handlers[event][validated] = HandlerMetadata(
            handler=handler,
            version=validated,
            required_scopes=required_scopes or [],
        )

    def get(self, event: str, version: str | None) -> HandlerMetadata | None:
        if version is None:
            return None

        validated = _coerce_version(version)
        event_handlers = self._handlers.get(event)
        if not event_handlers:
            return None

        return event_handlers.get(validated)

    def all(self) -> dict[str, dict[str, HandlerMetadata]]:
        return {event: handlers.copy() for event, handlers in self._handlers.items()}

    def events(self) -> dict[str, dict[str, HandlerMetadata]]:
        """Return the registered handlers without exposing the internal dict."""
        return self.all()

    def event_names(self) -> list[str]:
        return sorted(f"{event}@{version}" for event, versions in self._handlers.items() for version in versions.keys())


def _coerce_version(version: str) -> str:
    trimmed = version.strip()
    if not trimmed:
        raise ValueError("Event version cannot be blank.")
    return trimmed
