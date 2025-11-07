"""Routing utilities for webhook handlers."""
from __future__ import annotations

from collections import defaultdict
from typing import Awaitable, Callable, Dict, List, Tuple

Handler = Callable[..., Awaitable[object] | object]


def webhook(event: str, *, version: str) -> Callable[[Handler], Handler]:
    """Decorator for registering webhook handlers.

    Usage
    -----
    >>> from kiket_sdk import webhook
    >>> @webhook("issue.created", version="v2")
    ... async def handle_issue(payload, context):
    ...     ...

    The decorator marks the function with metadata inspected by :class:`~kiket_sdk.sdk.KiketSDK`.
    """

    def decorator(func: Handler) -> Handler:
        setattr(func, "__kiket_event__", event)
        setattr(func, "__kiket_version__", version)
        return func

    return decorator


class HandlerRegistry:
    """In-memory registry mapping event type to handler callables per version."""

    def __init__(self) -> None:
        self._handlers: Dict[str, Dict[str, Handler]] = defaultdict(dict)

    def register(self, event: str, handler: Handler, *, version: str) -> None:
        validated = _coerce_version(version)
        self._handlers[event][validated] = handler

    def get(self, event: str, version: str | None) -> Tuple[Handler, str] | None:
        if version is None:
            return None

        validated = _coerce_version(version)
        event_handlers = self._handlers.get(event)
        if not event_handlers:
            return None

        handler = event_handlers.get(validated)
        if handler is None:
            return None
        return handler, validated

    def all(self) -> Dict[str, Dict[str, Handler]]:
        return {event: handlers.copy() for event, handlers in self._handlers.items()}

    def events(self) -> Dict[str, Dict[str, Handler]]:
        """Return the registered handlers without exposing the internal dict."""
        return self.all()

    def event_names(self) -> List[str]:
        return sorted(f"{event}@{version}" for event, versions in self._handlers.items() for version in versions.keys())


def _coerce_version(version: str) -> str:
    trimmed = version.strip()
    if not trimmed:
        raise ValueError("Event version cannot be blank.")
    return trimmed
