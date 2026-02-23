# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Tests for JWT token creation and validation."""

import datetime
from unittest.mock import patch

from app.auth.token import (
    TokenPayload,
    create_access_token,
    create_refresh_token,
    decode_token,
)


class TestCreateAccessToken:
    def test_creates_valid_token(self):
        token = create_access_token(user_id=1, role="admin")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_contains_correct_payload(self):
        token = create_access_token(user_id=42, role="editor")
        payload = decode_token(token)
        assert payload is not None
        assert payload.sub == 42
        assert payload.role == "editor"
        assert payload.type == "access"
        assert payload.jti != ""

    def test_token_expires_in_future(self):
        token = create_access_token(user_id=1, role="admin")
        payload = decode_token(token)
        assert payload is not None
        assert payload.exp > datetime.datetime.now(datetime.UTC)


class TestCreateRefreshToken:
    def test_creates_valid_token(self):
        token = create_refresh_token(user_id=1)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_refresh_token_type(self):
        token = create_refresh_token(user_id=7)
        payload = decode_token(token)
        assert payload is not None
        assert payload.type == "refresh"
        assert payload.sub == 7

    def test_refresh_token_has_empty_role(self):
        token = create_refresh_token(user_id=1)
        payload = decode_token(token)
        assert payload is not None
        assert payload.role == ""


class TestDecodeToken:
    def test_valid_token(self):
        token = create_access_token(user_id=1, role="viewer")
        payload = decode_token(token)
        assert payload is not None
        assert isinstance(payload, TokenPayload)

    def test_invalid_token_returns_none(self):
        result = decode_token("invalid.jwt.token")
        assert result is None

    def test_empty_token_returns_none(self):
        result = decode_token("")
        assert result is None

    def test_expired_token_returns_none(self):
        with patch("app.auth.token.get_settings") as mock_settings:
            mock_settings.return_value.jwt_secret_key = "test-secret"
            mock_settings.return_value.jwt_algorithm = "HS256"
            mock_settings.return_value.jwt_access_token_expire_minutes = -1  # Already expired
            token = create_access_token(user_id=1, role="admin")

        # Token was created with -1 min expiry, should be expired
        result = decode_token(token)
        assert result is None

    def test_wrong_secret_returns_none(self):
        token = create_access_token(user_id=1, role="admin")

        with patch("app.auth.token.get_settings") as mock_settings:
            mock_settings.return_value.jwt_secret_key = "wrong-secret"
            mock_settings.return_value.jwt_algorithm = "HS256"
            result = decode_token(token)

        assert result is None

    def test_different_users_get_different_tokens(self):
        token1 = create_access_token(user_id=1, role="admin")
        token2 = create_access_token(user_id=2, role="admin")
        assert token1 != token2

    def test_each_token_has_unique_jti(self):
        token1 = create_access_token(user_id=1, role="admin")
        token2 = create_access_token(user_id=1, role="admin")
        payload1 = decode_token(token1)
        payload2 = decode_token(token2)
        assert payload1 is not None
        assert payload2 is not None
        assert payload1.jti != payload2.jti
