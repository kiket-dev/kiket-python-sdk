"""JWT authentication utilities for webhook verification."""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient
from jwt.exceptions import ExpiredSignatureError, InvalidIssuerError, PyJWTError

from .exceptions import AuthenticationError

ALGORITHM = "ES256"
ISSUER = "kiket.dev"
JWKS_CACHE_TTL = 3600  # 1 hour

_jwks_cache: dict[str, tuple[PyJWKClient, float]] = {}


@dataclass
class JwtPayload:
    """Decoded JWT payload."""

    sub: str
    org_id: int | None = None
    ext_id: int | None = None
    proj_id: int | None = None
    pi_id: int | None = None
    scopes: list[str] | None = None
    src: str | None = None
    iss: str = ""
    iat: int = 0
    exp: int = 0
    jti: str = ""


@dataclass
class AuthContext:
    """Authentication context from verified JWT."""

    runtime_token: str
    token_type: str
    expires_at: str | None
    scopes: list[str]
    org_id: int | None = None
    ext_id: int | None = None
    proj_id: int | None = None


async def verify_runtime_token(payload: dict[str, Any], base_url: str) -> JwtPayload:
    """Verify the runtime token JWT from the webhook payload.

    Parameters
    ----------
    payload:
        The webhook payload containing authentication.runtime_token.
    base_url:
        Base URL for fetching JWKS.

    Returns
    -------
    JwtPayload:
        The decoded and verified JWT payload.

    Raises
    ------
    AuthenticationError:
        If the token is missing, invalid, or expired.
    """
    auth = payload.get("authentication", {}) if isinstance(payload, dict) else {}
    token = auth.get("runtime_token")

    if not token:
        raise AuthenticationError("Missing runtime_token in payload")

    return await decode_jwt(token, base_url)


async def decode_jwt(token: str, base_url: str) -> JwtPayload:
    """Decode and verify a JWT token using the public key from JWKS.

    Parameters
    ----------
    token:
        The JWT token to verify.
    base_url:
        Base URL for fetching JWKS.

    Returns
    -------
    JwtPayload:
        The decoded payload.

    Raises
    ------
    AuthenticationError:
        If the token is invalid.
    """
    try:
        jwks_client = await _get_jwks_client(base_url)
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        decoded = jwt.decode(
            token,
            signing_key.key,
            algorithms=[ALGORITHM],
            issuer=ISSUER,
            options={
                "verify_iat": True,
                "verify_exp": True,
                "require": ["exp", "iat", "iss"],
            },
        )

        return JwtPayload(
            sub=decoded.get("sub", ""),
            org_id=decoded.get("org_id"),
            ext_id=decoded.get("ext_id"),
            proj_id=decoded.get("proj_id"),
            pi_id=decoded.get("pi_id"),
            scopes=decoded.get("scopes", []),
            src=decoded.get("src"),
            iss=decoded.get("iss", ""),
            iat=decoded.get("iat", 0),
            exp=decoded.get("exp", 0),
            jti=decoded.get("jti", ""),
        )
    except ExpiredSignatureError as exc:
        raise AuthenticationError("Runtime token has expired") from exc
    except InvalidIssuerError as exc:
        raise AuthenticationError("Invalid token issuer") from exc
    except PyJWTError as exc:
        raise AuthenticationError(f"Invalid token: {exc}") from exc


async def _get_jwks_client(base_url: str) -> PyJWKClient:
    """Get or create a cached JWKS client."""
    now = time.time()
    cached = _jwks_cache.get(base_url)

    if cached and (now - cached[1]) < JWKS_CACHE_TTL:
        return cached[0]

    jwks_url = f"{base_url.rstrip('/')}/.well-known/jwks.json"

    try:
        # Fetch JWKS to verify it's available before creating client
        async with httpx.AsyncClient() as client:
            response = await client.get(jwks_url, timeout=10.0)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise AuthenticationError(f"Failed to fetch JWKS: {exc}") from exc

    # Create PyJWKClient with caching
    jwks_client = PyJWKClient(jwks_url, cache_keys=True, lifespan=JWKS_CACHE_TTL)
    _jwks_cache[base_url] = (jwks_client, now)

    return jwks_client


def build_auth_context(jwt_payload: JwtPayload, raw_payload: dict[str, Any]) -> AuthContext:
    """Build authentication context from verified JWT payload.

    Parameters
    ----------
    jwt_payload:
        The verified JWT claims.
    raw_payload:
        The original webhook payload.

    Returns
    -------
    AuthContext:
        Authentication context for use in handlers.
    """
    raw_auth = raw_payload.get("authentication", {}) if isinstance(raw_payload, dict) else {}

    expires_at = None
    if jwt_payload.exp:
        expires_at = datetime.fromtimestamp(jwt_payload.exp, tz=UTC).isoformat()

    return AuthContext(
        runtime_token=raw_auth.get("runtime_token", ""),
        token_type="runtime",
        expires_at=expires_at,
        scopes=jwt_payload.scopes or [],
        org_id=jwt_payload.org_id,
        ext_id=jwt_payload.ext_id,
        proj_id=jwt_payload.proj_id,
    )


def clear_jwks_cache() -> None:
    """Clear the JWKS cache (useful for testing or key rotation)."""
    _jwks_cache.clear()
