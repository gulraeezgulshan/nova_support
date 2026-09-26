"""Verification of Clerk session tokens (RS256 JWTs).

Clerk only proves *who* the caller is. What the caller may do is decided by our own
role table (see `security.dependencies`).

The key resolver is injectable, so tests can sign tokens with a local key and still
exercise the full verification path (signature, expiry, issuer, authorised party).
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import jwt

from src.core.config import Settings

KeyResolver = Callable[[str], Any]


class TokenVerificationError(Exception):
    """Raised when a bearer token is missing, malformed, expired or not trusted."""


@dataclass(frozen=True, slots=True)
class AuthIdentity:
    clerk_user_id: str
    session_id: str | None
    email: str | None
    full_name: str | None


class ClerkTokenVerifier:
    ALGORITHMS = ("RS256",)
    LEEWAY_SECONDS = 5

    def __init__(self, issuer: str, authorized_parties: list[str], key_resolver: KeyResolver):
        if not issuer:
            raise ValueError("Clerk issuer is not configured (set CLERK_ISSUER).")
        self._issuer = issuer.rstrip("/")
        self._authorized_parties = set(authorized_parties)
        self._key_resolver = key_resolver

    @classmethod
    def from_settings(cls, settings: Settings) -> "ClerkTokenVerifier":
        jwks_client = jwt.PyJWKClient(settings.clerk_jwks_url, cache_keys=True, lifespan=3600)

        def resolve(token: str) -> Any:
            return jwks_client.get_signing_key_from_jwt(token).key

        return cls(settings.clerk_issuer, settings.clerk_authorized_party_list, resolve)

    def verify(self, token: str) -> AuthIdentity:
        try:
            key = self._key_resolver(token)
            claims: dict[str, Any] = jwt.decode(
                token,
                key,
                algorithms=list(self.ALGORITHMS),
                issuer=self._issuer,
                leeway=self.LEEWAY_SECONDS,
                options={"require": ["exp", "iat", "iss", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise TokenVerificationError(f"Invalid session token: {exc}") from exc

        # `azp` is set for browser-issued tokens; it must be one of our own front-ends.
        azp = claims.get("azp")
        if azp is not None and self._authorized_parties and azp not in self._authorized_parties:
            raise TokenVerificationError(f"Token issued for untrusted party: {azp}")

        return AuthIdentity(
            clerk_user_id=str(claims["sub"]),
            session_id=claims.get("sid"),
            # Optional custom claims configured in the Clerk session-token template.
            email=_clean(claims.get("email")),
            full_name=_clean(claims.get("name")),
        )


def _clean(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None
