"""Core SDK class and FastAPI integration."""
from __future__ import annotations

import inspect
import os
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from .auth import verify_signature
from .client import KiketClient
from .config import ExtensionConfig
from .endpoints import ExtensionEndpoints
from .exceptions import AuthenticationError, KiketSDKError
from .manifest import apply_secret_env_overrides, load_manifest
from .routing import HandlerRegistry
from .secrets import ExtensionSecretManager
from .telemetry import TelemetryRecord, TelemetryReporter

Handler = Callable[[Any, "HandlerContext"], Awaitable[Any] | Any]


@dataclass(slots=True)
class AuthenticationContext:
    """Authentication metadata sent with each webhook payload."""

    runtime_token: str | None
    token_type: str | None
    expires_at: str | None
    scopes: list[str]


@dataclass(slots=True)
class HandlerContext:
    """Context passed into webhook handlers."""

    event: str
    event_version: str
    headers: Mapping[str, str]
    client: KiketClient
    endpoints: ExtensionEndpoints
    settings: Mapping[str, Any]
    extension_id: str | None
    extension_version: str | None
    secrets: ExtensionSecretManager
    auth: AuthenticationContext


class KiketSDK:
    """Main entrypoint for building extensions."""

    def __init__(
        self,
        *,
        webhook_secret: str | None = None,
        workspace_token: str | None = None,
        extension_api_key: str | None = None,
        base_url: str | None = None,
        settings: Mapping[str, Any] | None = None,
        extension_id: str | None = None,
        extension_version: str | None = None,
        manifest_path: str | None = None,
        auto_env_secrets: bool = True,
        telemetry_enabled: bool = True,
        feedback_hook: Callable[[TelemetryRecord], Awaitable[None] | None] | None = None,
        telemetry_url: str | None = None,
    ) -> None:
        manifest = load_manifest(manifest_path)
        self.manifest = manifest

        resolved_base_url = base_url or os.getenv("KIKET_BASE_URL") or "https://kiket.dev"
        resolved_workspace_token = workspace_token or os.getenv("KIKET_WORKSPACE_TOKEN")
        resolved_extension_api_key = extension_api_key or os.getenv("KIKET_EXTENSION_API_KEY")

        manifest_settings: dict[str, Any] = manifest.settings_defaults() if manifest else {}
        if manifest and auto_env_secrets:
            manifest_settings = apply_secret_env_overrides(manifest_settings, manifest.secret_keys())

        merged_settings: dict[str, Any] = dict(manifest_settings)
        if settings:
            merged_settings.update(settings)

        resolved_extension_id = extension_id or (manifest.extension_id if manifest else None)
        resolved_extension_version = extension_version or (manifest.version if manifest else None)

        resolved_webhook_secret = (
            webhook_secret
            or (manifest.delivery_secret if manifest else None)
            or os.getenv("KIKET_WEBHOOK_SECRET")
        )

        resolved_telemetry_url = telemetry_url or os.getenv("KIKET_SDK_TELEMETRY_URL") or f"{resolved_base_url}/api/v1/ext"

        self.config = ExtensionConfig.from_mapping({
            "webhook_secret": resolved_webhook_secret,
            "workspace_token": resolved_workspace_token,
            "extension_api_key": resolved_extension_api_key,
            "base_url": resolved_base_url,
            "settings": merged_settings,
            "extension_id": resolved_extension_id,
            "extension_version": resolved_extension_version,
        })
        self.registry = HandlerRegistry()
        self.telemetry = TelemetryReporter(
            enabled=telemetry_enabled,
            telemetry_url=resolved_telemetry_url,
            feedback_hook=feedback_hook,
            extension_id=resolved_extension_id,
            extension_version=resolved_extension_version,
            api_key=resolved_extension_api_key,
        )
        self.app = self._build_app()

    # ------------------------------------------------------------------
    # Registration API
    # ------------------------------------------------------------------
    def register(self, event: str, handler: Handler, *, version: str) -> None:
        self.registry.register(event, handler, version=version)

    def webhook(self, event: str, *, version: str) -> Callable[[Handler], Handler]:
        def decorator(func: Handler) -> Handler:
            self.register(event, func, version=version)
            return func

        return decorator

    def load(self, module: Any) -> None:
        """Load all webhook handlers defined in a module."""

        for attr in dir(module):
            func = getattr(module, attr)
            event = getattr(func, "__kiket_event__", None)
            if event:
                version = getattr(func, "__kiket_version__", None)
                if version is None:
                    raise ValueError(f"Handler '{module.__name__}.{attr}' missing version metadata; use @sdk.webhook(..., version='...').")
                self.registry.register(event, func, version=version)

    # ------------------------------------------------------------------
    # Runtime API
    # ------------------------------------------------------------------
    def run(self, host: str = "127.0.0.1", port: int = 8000) -> None:  # pragma: no cover
        uvicorn.run(self.app, host=host, port=port)

    def create_test_client(self):  # pragma: no cover - convenience wrapper
        from fastapi.testclient import TestClient

        return TestClient(self.app)

    # ------------------------------------------------------------------
    # Internal FastAPI setup
    # ------------------------------------------------------------------
    def _build_app(self) -> FastAPI:
        app = FastAPI(title="Kiket Extension")

        async def _dispatch(event: str, request: Request, path_version: str | None = None) -> Response:
            body = await request.body()
            try:
                verify_signature(self.config.webhook_secret, body, request.headers)
            except AuthenticationError as exc:
                raise HTTPException(status_code=401, detail=str(exc)) from exc

            requested_version = _coerce_optional(path_version) or _coerce_optional(
                request.headers.get("X-Kiket-Event-Version")
            ) or _coerce_optional(request.query_params.get("version"))

            if requested_version is None:
                raise HTTPException(
                    status_code=400,
                    detail="Event version required. Provide X-Kiket-Event-Version header, version query param, or /v/{version} path.",
                )

            resolved = self.registry.get(event, requested_version)
            if not resolved:
                raise HTTPException(
                    status_code=404,
                    detail=f"No handler registered for event '{event}' with version '{requested_version}'",
                )

            handler, resolved_version = resolved
            payload = await request.json()
            auth_context = self._coerce_authentication(payload)
            async with KiketClient(
                base_url=self.config.base_url,
                workspace_token=self.config.workspace_token,
                extension_api_key=self.config.extension_api_key,
                runtime_token=auth_context.runtime_token,
            ) as client:
                endpoints = ExtensionEndpoints(
                    client,
                    self.config.extension_id,
                    event_version=resolved_version,
                )
                context = HandlerContext(
                    event=event,
                    event_version=resolved_version,
                    headers=dict(request.headers),
                    client=client,
                    endpoints=endpoints,
                    settings=self.config.settings.raw,
                    extension_id=self.config.extension_id,
                    extension_version=self.config.extension_version,
                    secrets=endpoints.secrets,
                    auth=auth_context,
                )
                start_ns = time.perf_counter_ns()
                try:
                    result = await _invoke(handler, payload, context)
                except Exception as exc:
                    duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
                    await self.telemetry.record(
                        event,
                        resolved_version,
                        "error",
                        duration_ms,
                        error_message=str(exc),
                        error_class=exc.__class__.__name__,
                    )
                    raise
                duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
                await self.telemetry.record(
                    event,
                    resolved_version,
                    "ok",
                    duration_ms,
                )
            return JSONResponse(content=result or {"ok": True})

        @app.post("/webhooks/{event}")
        async def dispatch(event: str, request: Request) -> Response:
            return await _dispatch(event, request)

        @app.post("/v/{version}/webhooks/{event}")
        async def dispatch_version(version: str, event: str, request: Request) -> Response:
            return await _dispatch(event, request, path_version=version)

        @app.get("/health")
        async def health() -> Response:
            payload = {
                "status": "ok",
                "extension_id": self.config.extension_id,
                "extension_version": self.config.extension_version,
                "registered_events": self.registry.event_names(),
            }
            return JSONResponse(payload)

        @app.exception_handler(KiketSDKError)
        async def sdk_error_handler(_: Request, exc: KiketSDKError) -> JSONResponse:
            return JSONResponse({"error": str(exc)}, status_code=400)

        return app

    def _coerce_authentication(self, payload: Any) -> AuthenticationContext:
        if isinstance(payload, Mapping):
            raw_auth = payload.get("authentication") or {}
        else:
            raw_auth = {}

        runtime_token = raw_auth.get("runtime_token")
        token_type = raw_auth.get("token_type")
        expires_at = raw_auth.get("expires_at")
        scopes = raw_auth.get("scopes") or []

        return AuthenticationContext(
            runtime_token=str(runtime_token) if runtime_token else None,
            token_type=str(token_type) if token_type else None,
            expires_at=str(expires_at) if expires_at else None,
            scopes=[str(scope) for scope in scopes if scope],
        )


async def _invoke(handler: Handler, payload: Any, context: HandlerContext) -> Any:
    try:
        result = handler(payload, context)
        if inspect.isawaitable(result):
            return await result
        return result
    except Exception as exc:  # pragma: no cover - surface error to caller
        raise KiketSDKError(str(exc)) from exc


def create_app(**kwargs: Any) -> FastAPI:
    """Convenience helper to build an app without instantiating :class:`KiketSDK` manually."""

    sdk = KiketSDK(**kwargs)
    return sdk.app


def _coerce_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
