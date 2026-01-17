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

from .auth import AuthContext, build_auth_context, verify_runtime_token
from .client import KiketClient
from .config import ExtensionConfig
from .endpoints import ExtensionEndpoints
from .exceptions import AuthenticationError, KiketSDKError, ScopeError
from .manifest import apply_secret_env_overrides, load_manifest
from .routing import HandlerRegistry
from .secrets import ExtensionSecretManager
from .telemetry import TelemetryRecord, TelemetryReporter

Handler = Callable[[Any, "HandlerContext"], Awaitable[Any] | Any]
ScopeChecker = Callable[..., None]
SecretHelper = Callable[[str], str | None]


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
    secret: SecretHelper
    payload_secrets: Mapping[str, str]
    auth: AuthContext
    require_scopes: ScopeChecker


class KiketSDK:
    """Main entrypoint for building extensions."""

    def __init__(
        self,
        *,
        workspace_token: str | None = None,
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

        manifest_settings: dict[str, Any] = manifest.settings_defaults() if manifest else {}
        if manifest and auto_env_secrets:
            manifest_settings = apply_secret_env_overrides(manifest_settings, manifest.secret_keys())

        merged_settings: dict[str, Any] = dict(manifest_settings)
        if settings:
            merged_settings.update(settings)

        resolved_extension_id = extension_id or (manifest.extension_id if manifest else None)
        resolved_extension_version = extension_version or (manifest.version if manifest else None)

        resolved_telemetry_url = telemetry_url or os.getenv("KIKET_SDK_TELEMETRY_URL") or f"{resolved_base_url}/api/v1/ext"

        self.config = ExtensionConfig.from_mapping({
            "workspace_token": resolved_workspace_token,
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
        )
        self.app = self._build_app()

    # ------------------------------------------------------------------
    # Registration API
    # ------------------------------------------------------------------
    def register(
        self,
        event: str,
        handler: Handler,
        *,
        version: str,
        required_scopes: list[str] | None = None,
    ) -> None:
        self.registry.register(event, handler, version=version, required_scopes=required_scopes)

    def webhook(
        self,
        event: str,
        *,
        version: str,
        required_scopes: list[str] | None = None,
    ) -> Callable[[Handler], Handler]:
        def decorator(func: Handler) -> Handler:
            self.register(event, func, version=version, required_scopes=required_scopes)
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
            payload = await request.json()

            # Resolve API base URL from payload or config
            api_base_url = payload.get("api", {}).get("base_url") or self.config.base_url

            # Verify JWT runtime token
            try:
                jwt_payload = await verify_runtime_token(payload, api_base_url)
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

            metadata = self.registry.get(event, requested_version)
            if not metadata:
                raise HTTPException(
                    status_code=404,
                    detail=f"No handler registered for event '{event}' with version '{requested_version}'",
                )

            handler = metadata.handler
            resolved_version = metadata.version
            auth_context = build_auth_context(jwt_payload, payload)

            # Check required scopes before proceeding
            if metadata.required_scopes:
                missing = self._check_scopes(metadata.required_scopes, auth_context.scopes)
                if missing:
                    raise HTTPException(
                        status_code=403,
                        detail={
                            "error": "Insufficient scopes",
                            "required_scopes": metadata.required_scopes,
                            "missing_scopes": missing,
                        },
                    )

            # Extract payload secrets for quick access (bundled by SecretResolver)
            payload_secrets = payload.get("secrets") or {}

            # Build secret helper: checks payload secrets first (per-org), falls back to ENV (extension defaults)
            secret_helper = self._build_secret_helper(payload_secrets)

            async with KiketClient(
                base_url=api_base_url,
                workspace_token=self.config.workspace_token,
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
                    secret=secret_helper,
                    payload_secrets=payload_secrets,
                    auth=auth_context,
                    require_scopes=self._build_scope_checker(auth_context.scopes),
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

    def _check_scopes(self, required_scopes: list[str], available_scopes: list[str]) -> list[str]:
        """Check if all required scopes are present. Returns missing scopes."""
        if "*" in available_scopes:
            return []
        return [s for s in required_scopes if s not in available_scopes]

    def _build_scope_checker(self, available_scopes: list[str]) -> ScopeChecker:
        """Build a scope checker function for use in handler context."""
        def checker(*required_scopes: str) -> None:
            missing = self._check_scopes(list(required_scopes), available_scopes)
            if missing:
                raise ScopeError(list(required_scopes), available_scopes)
        return checker

    def _build_secret_helper(self, payload_secrets: Mapping[str, str]) -> SecretHelper:
        """Build a secret helper function for use in handler context.

        Checks payload secrets first (per-org configuration bundled by SecretResolver),
        then falls back to environment variables (extension defaults).

        Example:
            # In handler:
            slack_token = context.secret('SLACK_BOT_TOKEN')
            # Returns payload["secrets"]["SLACK_BOT_TOKEN"] or os.getenv("SLACK_BOT_TOKEN")
        """
        def helper(key: str) -> str | None:
            # Payload secrets (per-org) take priority over ENV (extension defaults)
            return payload_secrets.get(key) or os.getenv(key)
        return helper


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
