from collections.abc import Callable

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from security.clerk import ClerkTokenVerifier, TokenVerificationError


def test_valid_token_yields_identity(
    verifier: ClerkTokenVerifier, make_token: Callable[..., str]
) -> None:
    identity = verifier.verify(make_token("user_abc", email=" a@b.test ", name="Ada Lovelace"))
    assert identity.clerk_user_id == "user_abc"
    assert identity.email == "a@b.test"
    assert identity.full_name == "Ada Lovelace"


def test_server_to_server_token_without_azp_is_accepted(
    verifier: ClerkTokenVerifier, make_token: Callable[..., str]
) -> None:
    assert verifier.verify(make_token("user_abc", azp=None)).clerk_user_id == "user_abc"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"expires_in": -60}, "expired"),
        ({"issuer": "https://evil.example"}, "issuer"),
        ({"azp": "https://evil.example"}, "untrusted party"),
    ],
)
def test_rejected_tokens(
    verifier: ClerkTokenVerifier,
    make_token: Callable[..., str],
    overrides: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(TokenVerificationError, match=message):
        verifier.verify(make_token("user_abc", **overrides))


def test_token_signed_with_another_key_is_rejected(
    verifier: ClerkTokenVerifier, make_token: Callable[..., str]
) -> None:
    attacker_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(TokenVerificationError, match="Signature"):
        verifier.verify(make_token("user_abc", key=attacker_key))


def test_garbage_token_is_rejected(verifier: ClerkTokenVerifier) -> None:
    with pytest.raises(TokenVerificationError):
        verifier.verify("not-a-jwt")


def test_missing_issuer_configuration_fails_fast() -> None:
    with pytest.raises(ValueError, match="CLERK_ISSUER"):
        ClerkTokenVerifier("", [], lambda _t: None)
