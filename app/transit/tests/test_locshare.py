# pyright: reportUnknownParameterType=false, reportMissingParameterType=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
"""Unit tests for share link JWT and QR code logic (LV-3.4)."""

import base64
import datetime
import hashlib
from unittest.mock import MagicMock, patch

from app.transit.locshare import (
    create_share_token,
    decode_share_token,
    generate_qr_code_base64,
    hash_token,
)


def _mock_settings() -> MagicMock:
    settings = MagicMock()
    settings.share_link_secret_key = None
    settings.jwt_secret_key = "test-secret-key-for-unit-tests"  # pragma: allowlist secret
    settings.jwt_algorithm = "HS256"
    return settings


@patch("app.transit.locshare.get_settings")
def test_create_share_token_returns_valid_jwt(mock_settings: MagicMock) -> None:
    """Sign a token and verify it returns a non-empty JWT and hash."""
    mock_settings.return_value = _mock_settings()

    token, token_hash = create_share_token(
        vehicle_id="4521",
        route_id="22",
        feed_id="riga",
        expiry_hours=1,
    )
    assert isinstance(token, str)
    assert len(token) > 0
    assert "." in token  # JWT has 3 dot-separated parts
    assert len(token_hash) == 64  # SHA-256 hex


@patch("app.transit.locshare.get_settings")
def test_create_share_token_hash_is_sha256(mock_settings: MagicMock) -> None:
    """Verify token_hash matches SHA-256 of the token."""
    mock_settings.return_value = _mock_settings()

    token, token_hash = create_share_token(
        vehicle_id="4521",
        route_id=None,
        feed_id="riga",
        expiry_hours=1,
    )
    expected = hashlib.sha256(token.encode()).hexdigest()
    assert token_hash == expected


@patch("app.transit.locshare.get_settings")
def test_decode_share_token_valid(mock_settings: MagicMock) -> None:
    """Decode a freshly signed token succeeds."""
    mock_settings.return_value = _mock_settings()

    token, _ = create_share_token(
        vehicle_id="4521",
        route_id="22",
        feed_id="riga",
        expiry_hours=1,
    )
    payload = decode_share_token(token)
    assert payload is not None
    assert payload.sub == "4521"
    assert payload.route_id == "22"
    assert payload.feed_id == "riga"
    assert payload.type == "share"


@patch("app.transit.locshare.get_settings")
def test_decode_share_token_expired(mock_settings: MagicMock) -> None:
    """Token with past expiry returns None."""
    mock_settings.return_value = _mock_settings()

    # Create token with -1 hours (already expired)
    from jose import jwt

    settings = _mock_settings()
    expire = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=1)
    token: str = jwt.encode(
        {
            "sub": "4521",
            "route_id": "22",
            "feed_id": "riga",
            "exp": expire,
            "type": "share",
            "jti": "abc123",
        },
        settings.jwt_secret_key,
        algorithm="HS256",
    )
    payload = decode_share_token(token)
    assert payload is None


@patch("app.transit.locshare.get_settings")
def test_decode_share_token_wrong_type(mock_settings: MagicMock) -> None:
    """Token with type='access' returns None."""
    mock_settings.return_value = _mock_settings()

    from jose import jwt

    settings = _mock_settings()
    expire = datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1)
    token: str = jwt.encode(
        {
            "sub": "4521",
            "route_id": "22",
            "feed_id": "riga",
            "exp": expire,
            "type": "access",
            "jti": "abc123",
        },
        settings.jwt_secret_key,
        algorithm="HS256",
    )
    payload = decode_share_token(token)
    assert payload is None


@patch("app.transit.locshare.get_settings")
def test_decode_share_token_tampered(mock_settings: MagicMock) -> None:
    """Tampered token returns None."""
    mock_settings.return_value = _mock_settings()

    token, _ = create_share_token(
        vehicle_id="4521",
        route_id="22",
        feed_id="riga",
        expiry_hours=1,
    )
    tampered = token + "TAMPERED"
    payload = decode_share_token(tampered)
    assert payload is None


def test_generate_qr_code_base64_valid_png() -> None:
    """QR code output is valid base64 PNG."""
    result = generate_qr_code_base64("https://example.com/share/abc")
    raw = base64.b64decode(result)
    # PNG magic bytes
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"


def test_hash_token_deterministic() -> None:
    """Same input produces same hash."""
    h1 = hash_token("test-token")
    h2 = hash_token("test-token")
    assert h1 == h2
    assert len(h1) == 64


def test_hash_token_different_inputs() -> None:
    """Different tokens produce different hashes."""
    h1 = hash_token("token-a")
    h2 = hash_token("token-b")
    assert h1 != h2
