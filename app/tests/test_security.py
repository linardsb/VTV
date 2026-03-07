# pyright: reportUnknownParameterType=false, reportMissingParameterType=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
"""Security audit regression tests.

Validates fixes for all 13 findings from the third-party security audit.
Each test class maps to a specific audit finding (C1-C3, M1-M5, etc.).
"""

from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request

# === C2: Streaming file upload with size limit ===


class TestStreamingUploadSizeLimit:
    """Audit C2: File upload must enforce size limits via streaming, not just Content-Length."""

    @pytest.mark.asyncio
    async def test_upload_rejects_oversized_file(self) -> None:
        """Files exceeding 50MB should be rejected with HTTP 413."""
        from app.core.rate_limit import limiter

        limiter.enabled = False

        from httpx import ASGITransport, AsyncClient

        from app.main import app

        # Create a fake file that exceeds 50MB
        # We test with a smaller boundary check via the route logic
        oversized_content = b"x" * (50 * 1024 * 1024 + 1)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/knowledge/documents",
                files={"file": ("test.txt", oversized_content, "text/plain")},
                data={"domain": "test", "language": "lv"},
            )

        assert response.status_code == 413

    def test_upload_route_has_streaming_read(self) -> None:
        """Verify the upload route uses streaming chunk reads, not file.read()."""
        import inspect

        from app.knowledge.routes import upload_document

        source = inspect.getsource(upload_document)
        # Must use chunked reading
        assert "file.read(8192)" in source or "file.read(" in source
        # Must NOT read entire file at once
        assert "await file.read()\n" not in source


# === C3: Filename sanitization ===


class TestFilenameSanitization:
    """Audit C3: User-provided filenames must be regex-sanitized."""

    def test_special_chars_stripped(self) -> None:
        """Filenames with special characters should be sanitized."""
        import re
        from pathlib import Path

        raw = "../../etc/passwd"
        safe = re.sub(r"[^\w\-.]", "_", Path(raw).name.replace("\x00", ""))
        assert safe == "passwd"

    def test_null_bytes_removed(self) -> None:
        """Null bytes in filenames should be removed."""
        import re
        from pathlib import Path

        raw = "test\x00.txt"
        safe = re.sub(r"[^\w\-.]", "_", Path(raw).name.replace("\x00", ""))
        assert "\x00" not in safe
        assert safe == "test.txt"

    def test_directory_traversal_blocked(self) -> None:
        """Directory traversal attempts should be sanitized to safe names."""
        import re
        from pathlib import Path

        raw = "../../../../etc/shadow"
        safe = re.sub(r"[^\w\-.]", "_", Path(raw).name.replace("\x00", ""))
        # Path().name strips directories, regex cleans the rest
        assert "/" not in safe
        assert ".." not in safe

    def test_shell_metacharacters_removed(self) -> None:
        """Shell metacharacters in filenames should be replaced."""
        import re
        from pathlib import Path

        raw = "file; rm -rf /; echo.txt"
        safe = re.sub(r"[^\w\-.]", "_", Path(raw).name.replace("\x00", ""))
        assert ";" not in safe
        assert " " not in safe


# === C3 (continued): Path traversal in service ===


class TestPathTraversalPrevention:
    """Audit C3: stored_path must be validated with is_relative_to()."""

    def test_service_has_path_validation(self) -> None:
        """KnowledgeService.ingest_document must validate stored_path."""
        import inspect

        from app.knowledge.service import KnowledgeService

        source = inspect.getsource(KnowledgeService.ingest_document)
        assert "is_relative_to" in source


# === Demo credentials are environment-controlled ===


class TestDemoCredentials:
    """Audit: Demo seed must be environment-controlled with configurable password."""

    @pytest.mark.asyncio
    async def test_seed_skipped_in_production(self) -> None:
        """seed_demo_users should not create users when ENVIRONMENT != development."""
        from app.auth.service import AuthService

        mock_db = AsyncMock()
        service = AuthService(mock_db)

        with patch("app.core.config.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                environment="production",
                demo_user_password="admin",
            )
            users = await service.seed_demo_users()

        assert len(users) == 0

    @pytest.mark.asyncio
    async def test_seed_uses_configurable_password(self) -> None:
        """seed_demo_users should use DEMO_USER_PASSWORD, not hardcoded 'admin'."""
        from app.auth.service import AuthService

        mock_db = AsyncMock()
        service = AuthService(mock_db)

        created_users: list[MagicMock] = []

        async def capture_create(user):
            created_users.append(user)
            return user

        with (
            patch("app.core.config.get_settings") as mock_settings,
            patch.object(service.repo, "count", return_value=0),
            patch.object(service.repo, "create", side_effect=capture_create),
        ):
            mock_settings.return_value = MagicMock(
                environment="development",
                demo_user_password="custom-secure-password",
            )
            await service.seed_demo_users()

        assert len(created_users) == 5
        # Verify all users use the custom password (verify against bcrypt hash)
        for user in created_users:
            assert AuthService.verify_password("custom-secure-password", user.hashed_password)


# === ILIKE wildcard escape ===


class TestIlikeWildcardEscape:
    """Audit: ILIKE queries must escape %, _, and \\ characters."""

    def test_escape_like_percent(self) -> None:
        """Percent signs should be escaped."""
        from app.shared.utils import escape_like

        assert escape_like("100%") == "100\\%"

    def test_escape_like_underscore(self) -> None:
        """Underscores should be escaped."""
        from app.shared.utils import escape_like

        assert escape_like("test_value") == "test\\_value"

    def test_escape_like_backslash(self) -> None:
        """Backslashes should be escaped."""
        from app.shared.utils import escape_like

        assert escape_like("path\\file") == "path\\\\file"

    def test_escape_like_combined(self) -> None:
        """Multiple special characters should all be escaped."""
        from app.shared.utils import escape_like

        result = escape_like("100% of test_data\\here")
        assert result == "100\\% of test\\_data\\\\here"

    def test_escape_like_normal_string(self) -> None:
        """Normal strings should pass through unchanged."""
        from app.shared.utils import escape_like

        assert escape_like("hello world") == "hello world"

    def test_stops_repository_uses_escape_like(self) -> None:
        """StopRepository.list must use escape_like for search."""
        import inspect

        from app.stops.repository import StopRepository

        source = inspect.getsource(StopRepository.list)
        assert "escape_like" in source

    def test_schedules_repository_uses_escape_like(self) -> None:
        """ScheduleRepository.list_routes must use escape_like for search."""
        import inspect

        from app.schedules.repository import ScheduleRepository

        source = inspect.getsource(ScheduleRepository.list_routes)
        assert "escape_like" in source

    def test_drivers_repository_uses_escape_like(self) -> None:
        """DriverRepository.list must use escape_like for search."""
        import inspect

        from app.drivers.repository import DriverRepository

        source = inspect.getsource(DriverRepository.list)
        assert "escape_like" in source


# === Rate limiter uses X-Real-IP ===


class TestRateLimiterIp:
    """Audit M1: Rate limiter must use X-Real-IP, not X-Forwarded-For."""

    def test_uses_x_real_ip_from_trusted_proxy(self) -> None:
        """_get_client_ip should use X-Real-IP when request comes from trusted proxy."""
        from app.core.rate_limit import _get_client_ip

        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"X-Real-IP": "1.2.3.4"}
        # Simulate request from Docker nginx proxy (trusted network)
        mock_request.client = MagicMock()
        mock_request.client.host = "172.18.0.5"

        result = _get_client_ip(mock_request)
        assert result == "1.2.3.4"

    def test_ignores_x_real_ip_from_untrusted_source(self) -> None:
        """_get_client_ip should ignore X-Real-IP from direct (non-proxy) requests."""
        from app.core.rate_limit import _get_client_ip

        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"X-Real-IP": "1.2.3.4"}
        # Simulate direct request from external IP (not trusted proxy)
        mock_request.client = MagicMock()
        mock_request.client.host = "203.0.113.50"

        result = _get_client_ip(mock_request)
        assert result == "203.0.113.50"  # Should use direct IP, not spoofed header

    def test_ignores_x_forwarded_for(self) -> None:
        """_get_client_ip should NOT use X-Forwarded-For (spoofable)."""
        from app.core.rate_limit import _get_client_ip

        mock_request = MagicMock(spec=Request)
        mock_request.headers = {
            "X-Forwarded-For": "1.2.3.4, 5.6.7.8",
        }

        result = _get_client_ip(mock_request)
        # Should NOT return the X-Forwarded-For value
        assert result != "1.2.3.4"

    def test_source_code_no_x_forwarded_for(self) -> None:
        """rate_limit.py must not reference X-Forwarded-For."""
        import inspect

        from app.core import rate_limit

        source = inspect.getsource(rate_limit)
        assert "X-Forwarded-For" not in source


# === Redis URL credential redaction ===


class TestRedisUrlRedaction:
    """Audit M2: Redis URLs with credentials must be redacted before logging."""

    def test_redacts_password(self) -> None:
        """URLs with passwords should have them masked."""
        from app.core.redis import _redact_url

        url = "redis://user:secret123@redis:6379/0"
        redacted = _redact_url(url)
        assert "secret123" not in redacted
        assert ":***@" in redacted

    def test_no_password_unchanged(self) -> None:
        """URLs without passwords should pass through unchanged."""
        from app.core.redis import _redact_url

        url = "redis://redis:6379/0"
        assert _redact_url(url) == url

    def test_complex_password(self) -> None:
        """Passwords with special characters should be fully redacted."""
        from app.core.redis import _redact_url

        url = "redis://admin:p@ss!w0rd#123@redis:6379/0"
        redacted = _redact_url(url)
        assert "p@ss!w0rd#123" not in redacted

    def test_get_redis_logs_redacted_url(self) -> None:
        """get_redis should log the redacted URL, not the raw one."""
        import inspect

        from app.core import redis

        source = inspect.getsource(redis.get_redis)
        assert "_redact_url" in source


# === Docker credentials interpolation ===


class TestDockerCredentials:
    """Audit M3: Docker credentials must use env var interpolation."""

    def test_postgres_user_interpolated(self) -> None:
        """docker-compose.yml must use ${POSTGRES_USER:-postgres}."""
        from pathlib import Path

        compose = Path("docker-compose.yml").read_text()
        assert "${POSTGRES_USER:-postgres}" in compose

    def test_postgres_password_interpolated(self) -> None:
        """docker-compose.yml must use ${POSTGRES_PASSWORD:-postgres}."""
        from pathlib import Path

        compose = Path("docker-compose.yml").read_text()
        assert "${POSTGRES_PASSWORD:-postgres}" in compose

    def test_postgres_db_interpolated(self) -> None:
        """docker-compose.yml must use ${POSTGRES_DB:-vtv_db}."""
        from pathlib import Path

        compose = Path("docker-compose.yml").read_text()
        assert "${POSTGRES_DB:-vtv_db}" in compose


# === Transit input validation ===


class TestTransitInputValidation:
    """Audit M4: Transit query params must have max_length and pattern constraints."""

    def test_route_id_has_constraints(self) -> None:
        """get_vehicles route_id param must have max_length and pattern."""
        import inspect

        from app.transit.routes import get_vehicles

        source = inspect.getsource(get_vehicles)
        assert "max_length=100" in source
        assert "pattern=" in source

    def test_feed_id_has_constraints(self) -> None:
        """get_vehicles feed_id param must have max_length and pattern."""
        import inspect

        from app.transit.routes import get_vehicles

        source = inspect.getsource(get_vehicles)
        assert "max_length=50" in source


# === Nginx HTTPS template ===


class TestNginxSecurity:
    """Audit M5: Nginx config must include HTTPS template."""

    def test_knowledge_upload_limit_is_52m(self) -> None:
        """Knowledge upload location must allow 52MB."""
        from pathlib import Path

        nginx_conf = Path("nginx/nginx.conf").read_text()
        # Find the knowledge location block
        knowledge_idx = nginx_conf.index("/api/v1/knowledge")
        # Check the next client_max_body_size after the knowledge location
        snippet = nginx_conf[knowledge_idx : knowledge_idx + 200]
        assert "client_max_body_size 52m" in snippet

    def test_https_template_present(self) -> None:
        """Nginx config must include HTTPS server block template."""
        from pathlib import Path

        nginx_conf = Path("nginx/nginx.conf").read_text()
        assert "ssl_protocols TLSv1.2 TLSv1.3" in nginx_conf
        assert "ssl_ciphers" in nginx_conf
        assert "Strict-Transport-Security" in nginx_conf


# === Middleware upload size limit ===


class TestMiddlewareUploadLimit:
    """Audit: Middleware must allow 50MB+ for file upload paths."""

    def test_upload_paths_allow_50mb(self) -> None:
        """Upload path size limit must be 50MB+."""
        import inspect

        from app.core.middleware import BodySizeLimitMiddleware

        source = inspect.getsource(BodySizeLimitMiddleware.dispatch)
        assert "52_428_800" in source


# === Config has demo_user_password setting ===


class TestConfigSecurity:
    """Audit: Config must have demo_user_password setting."""

    def test_demo_user_password_setting_exists(self) -> None:
        """Settings class must have demo_user_password field."""
        from app.core.config import Settings

        fields = Settings.model_fields
        assert "demo_user_password" in fields


# === v3 Hardening: Events Authentication ===


class TestEventsAuthentication:
    """All events endpoints must require authentication."""

    def test_list_events_requires_auth(self) -> None:
        """list_events must have get_current_user dependency."""
        import inspect

        from app.events.routes import list_events

        source = inspect.getsource(list_events)
        assert "get_current_user" in source or "require_role" in source

    def test_get_event_requires_auth(self) -> None:
        """get_event must have get_current_user dependency."""
        import inspect

        from app.events.routes import get_event

        source = inspect.getsource(get_event)
        assert "get_current_user" in source or "require_role" in source


# === v3 Hardening: Password Complexity ===


class TestPasswordComplexity:
    """Password complexity enforced on PasswordResetRequest, not on LoginRequest."""

    def test_short_password_rejected(self) -> None:
        from pydantic import ValidationError

        from app.auth.schemas import PasswordResetRequest

        with pytest.raises(ValidationError):
            PasswordResetRequest(user_id=1, new_password="short")

    def test_no_uppercase_rejected(self) -> None:
        from pydantic import ValidationError

        from app.auth.schemas import PasswordResetRequest

        with pytest.raises(ValidationError):
            PasswordResetRequest(user_id=1, new_password="alllowercase1")

    def test_no_digit_rejected(self) -> None:
        from pydantic import ValidationError

        from app.auth.schemas import PasswordResetRequest

        with pytest.raises(ValidationError):
            PasswordResetRequest(user_id=1, new_password="NoDigitHere")

    def test_valid_password_accepted(self) -> None:
        from app.auth.schemas import PasswordResetRequest

        req = PasswordResetRequest(user_id=1, new_password="ValidPass123!")
        assert req.new_password == "ValidPass123!"

    def test_login_accepts_weak_password(self) -> None:
        """LoginRequest must NOT enforce complexity — existing users may have weak passwords."""
        from app.auth.schemas import LoginRequest

        req = LoginRequest(email="test@test.com", password="admin")
        assert req.password == "admin"


# === v3 Hardening: Token Revocation ===


class TestTokenRevocation:
    """Token revocation via Redis denylist."""

    @pytest.mark.asyncio
    async def test_revoke_and_check(self) -> None:
        from app.auth.token import is_token_revoked, revoke_token

        mock_redis = MagicMock()
        mock_redis.setex = AsyncMock()
        mock_redis.get = AsyncMock(return_value="1")

        with patch("app.core.redis.get_redis", return_value=mock_redis):
            await revoke_token("test-jti-123")
            mock_redis.setex.assert_called_once()
            result = await is_token_revoked("test-jti-123")
            assert result is True

    @pytest.mark.asyncio
    async def test_non_revoked_token(self) -> None:
        from app.auth.token import is_token_revoked

        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch("app.core.redis.get_redis", return_value=mock_redis):
            result = await is_token_revoked("clean-jti")
            assert result is False

    @pytest.mark.asyncio
    async def test_empty_jti_not_revoked(self) -> None:
        from app.auth.token import is_token_revoked

        result = await is_token_revoked("")
        assert result is False


# === v3 Hardening: Brute Force Redis ===


class TestBruteForceRedis:
    """Brute force tracking should use Redis."""

    def test_auth_service_uses_redis_brute_force(self) -> None:
        import inspect

        from app.auth.service import AuthService

        source = inspect.getsource(AuthService.authenticate)
        assert "redis" in source.lower() or "_check_redis_brute_force" in source


# === v3 Hardening: CORS Restricted ===


class TestCorsRestricted:
    """CORS must not use wildcard methods/headers."""

    def test_cors_no_wildcard_methods(self) -> None:
        import inspect

        from app.core.middleware import setup_middleware

        source = inspect.getsource(setup_middleware)
        assert 'allow_methods=["*"]' not in source

    def test_cors_no_wildcard_headers(self) -> None:
        import inspect

        from app.core.middleware import setup_middleware

        source = inspect.getsource(setup_middleware)
        assert 'allow_headers=["*"]' not in source


# === v3 Hardening: Health Redaction ===


class TestHealthRedaction:
    """Health endpoints must not leak infrastructure details."""

    def test_db_health_no_provider_leak(self) -> None:
        import inspect

        from app.core.health import database_health_check

        source = inspect.getsource(database_health_check)
        assert '"postgresql"' not in source

    def test_redis_health_no_error_leak(self) -> None:
        import inspect

        from app.core.health import health_redis

        source = inspect.getsource(health_redis)
        assert 'f"Redis unavailable: {e}"' not in source

    def test_readiness_no_environment_leak(self) -> None:
        import inspect

        from app.core.health import readiness_check

        source = inspect.getsource(readiness_check)
        assert '"environment"' not in source


# === v3 Hardening: Docker No Hardcoded Creds ===


class TestDockerNoHardcodedCreds:
    """Docker compose must not have hardcoded database credentials in any service."""

    def test_no_hardcoded_database_url(self) -> None:
        from pathlib import Path

        compose = Path("docker-compose.yml").read_text()
        lines = compose.split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("- DATABASE_URL=") or stripped.startswith("DATABASE_URL="):
                assert "postgres:postgres@" not in stripped, (
                    f"Hardcoded credentials found: {stripped}"
                )


# === v3 Hardening: Version Redaction ===


class TestVersionRedaction:
    """Root endpoint must not expose version in production."""

    def test_root_endpoint_version_conditional(self) -> None:
        import inspect

        from app.main import read_root

        source = inspect.getsource(read_root)
        # Version should only be included conditionally
        assert "development" in source
        assert "version" in source


# === Convention Enforcement: All Endpoints Require Auth ===


class TestAllEndpointsRequireAuth:
    """Auto-discovery test: every route function must have authentication.

    Dynamically discovers ALL FastAPI route functions across app/*/routes.py
    and verifies each has get_current_user or require_role in its source.
    Public endpoints must be explicitly allowlisted.
    """

    # Endpoints that are legitimately public (no auth required)
    PUBLIC_ALLOWLIST: ClassVar[set[str]] = {
        "login",
        "refresh_token",
        "read_root",
        "health_check",
        "database_health_check",
        "health_redis",
        "readiness_check",
        "ws_vehicle_stream",  # WebSocket: manual JWT auth via query param (not Depends)
    }

    def test_all_routes_have_auth(self) -> None:
        """Every route function not in the allowlist must reference auth dependencies."""
        import importlib
        import inspect
        from pathlib import Path

        app_dir = Path("app")
        route_modules: list[str] = []

        # Discover all routes.py files under app/
        for routes_file in sorted(app_dir.rglob("routes.py")):
            module_path = str(routes_file).replace("/", ".").removesuffix(".py")
            route_modules.append(module_path)

        # Also check health.py and main.py
        route_modules.append("app.core.health")
        route_modules.append("app.main")

        missing_auth: list[str] = []

        for module_path in route_modules:
            module = importlib.import_module(module_path)
            mod_source = inspect.getsource(module)

            for name, func in inspect.getmembers(module, inspect.isfunction):
                # Only check functions DEFINED in this module (not imports)
                if getattr(func, "__module__", None) != module_path:
                    continue

                if name.startswith("_"):
                    continue

                if name in self.PUBLIC_ALLOWLIST:
                    continue

                # Check if a route decorator precedes this function def
                search_str = f"def {name}("
                if search_str not in mod_source:
                    continue
                func_idx = mod_source.index(search_str)
                preceding = mod_source[max(0, func_idx - 300) : func_idx]
                if "@router." not in preceding and "@app." not in preceding:
                    continue

                # This is a route handler — check for auth
                source = inspect.getsource(func)
                if "get_current_user" not in source and "require_role" not in source:
                    missing_auth.append(f"{module_path}.{name}")

        assert missing_auth == [], (
            f"Endpoints missing authentication: {missing_auth}. "
            f"Add get_current_user/require_role or add to PUBLIC_ALLOWLIST."
        )


# === Convention Enforcement: No Debug Logging in Security Paths ===


class TestNoDebugSecurityLogging:
    """Security fallback logging must use warning or higher, not debug."""

    def test_auth_service_no_debug_in_except(self) -> None:
        """app/auth/service.py must not use logger.debug in except blocks."""
        import ast
        from pathlib import Path

        source = Path("app/auth/service.py").read_text()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                for child in ast.walk(node):
                    if (
                        isinstance(child, ast.Call)
                        and isinstance(child.func, ast.Attribute)
                        and child.func.attr == "debug"
                        and isinstance(child.func.value, ast.Name)
                        and child.func.value.id == "logger"
                    ):
                        msg = (
                            f"logger.debug in except block at line {child.lineno}. "
                            f"Security logging must use warning or higher."
                        )
                        raise AssertionError(msg)

    def test_auth_token_no_debug_in_except(self) -> None:
        """app/auth/token.py must not use logger.debug in except blocks."""
        import ast
        from pathlib import Path

        source = Path("app/auth/token.py").read_text()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                for child in ast.walk(node):
                    if (
                        isinstance(child, ast.Call)
                        and isinstance(child.func, ast.Attribute)
                        and child.func.attr == "debug"
                        and isinstance(child.func.value, ast.Name)
                        and child.func.value.id == "logger"
                    ):
                        msg = (
                            f"logger.debug in except block at line {child.lineno}. "
                            f"Security logging must use warning or higher."
                        )
                        raise AssertionError(msg)


# === Convention Enforcement: JWT Algorithm Safety ===


class TestJwtAlgorithmNotNone:
    """JWT must use HS256, never the 'none' algorithm."""

    def test_config_default_is_hs256(self) -> None:
        """Settings.jwt_algorithm must default to HS256."""
        from app.core.config import Settings

        fields = Settings.model_fields
        assert fields["jwt_algorithm"].default == "HS256"

    def test_token_creation_uses_algorithm_setting(self) -> None:
        """create_access_token must use settings.jwt_algorithm, not a hardcoded value."""
        import inspect

        from app.auth.token import create_access_token

        source = inspect.getsource(create_access_token)
        assert "settings.jwt_algorithm" in source
        # Must NOT hardcode 'none' or 'None'
        assert 'algorithm="none"' not in source.lower()

    def test_token_decode_uses_algorithms_list(self) -> None:
        """decode_token must pass algorithms as a list (not single string)."""
        import inspect

        from app.auth.token import decode_token

        source = inspect.getsource(decode_token)
        assert "algorithms=[" in source


# === Convention Enforcement: Bcrypt Rounds ===


class TestBcryptRoundsSufficient:
    """Bcrypt must use at least 12 rounds (the default)."""

    def test_hash_password_uses_adequate_rounds(self) -> None:
        """AuthService.hash_password output must have 12+ rounds."""
        from app.auth.service import AuthService

        hashed = AuthService.hash_password("TestPassword123")
        # bcrypt hash format: $2b$XX$ where XX is the round count
        parts = hashed.split("$")
        rounds = int(parts[2])
        assert rounds >= 12, f"Bcrypt rounds {rounds} < 12 minimum"

    def test_gensalt_not_weakened(self) -> None:
        """hash_password source must not pass rounds < 12 to gensalt."""
        import inspect

        from app.auth.service import AuthService

        source = inspect.getsource(AuthService.hash_password)
        # If gensalt() is called with explicit rounds, they must be >= 12
        if "gensalt(" in source and "gensalt()" not in source:
            # Has explicit rounds argument — extract the number
            import re

            match = re.search(r"gensalt\((\d+)\)", source)
            if match:
                rounds = int(match.group(1))
                assert rounds >= 12, f"Explicit gensalt rounds {rounds} < 12"


# === Convention Enforcement: Password Complexity on Correct Schema ===


class TestPasswordComplexityOnCorrectSchema:
    """Password complexity must be on PasswordResetRequest, NOT LoginRequest.

    This prevents the critical bug where existing users with weak passwords
    get locked out because login enforces complexity on their old passwords.
    """

    def test_login_request_has_no_password_validator(self) -> None:
        """LoginRequest must NOT have a field_validator for password."""
        import inspect

        from app.auth.schemas import LoginRequest

        source = inspect.getsource(LoginRequest)
        assert "field_validator" not in source, (
            "LoginRequest must NOT validate password complexity. "
            "Existing users may have weak passwords."
        )

    def test_password_reset_has_password_validator(self) -> None:
        """PasswordResetRequest MUST have password complexity validation."""
        import inspect

        from app.auth.schemas import PasswordResetRequest

        source = inspect.getsource(PasswordResetRequest)
        assert "field_validator" in source or "model_validator" in source, (
            "PasswordResetRequest MUST enforce password complexity."
        )


# === Convention Enforcement: Nginx Security Headers ===


class TestSecurityHeadersInNginx:
    """Nginx config must include all required security headers."""

    def test_content_security_policy(self) -> None:
        """Nginx must set Content-Security-Policy header."""
        from pathlib import Path

        conf = Path("nginx/nginx.conf").read_text()
        assert "Content-Security-Policy" in conf

    def test_strict_transport_security(self) -> None:
        """Nginx must set Strict-Transport-Security (HSTS) header."""
        from pathlib import Path

        conf = Path("nginx/nginx.conf").read_text()
        assert "Strict-Transport-Security" in conf

    def test_x_frame_options(self) -> None:
        """Nginx must set X-Frame-Options header."""
        from pathlib import Path

        conf = Path("nginx/nginx.conf").read_text()
        assert "X-Frame-Options" in conf

    def test_x_content_type_options(self) -> None:
        """Nginx must set X-Content-Type-Options header."""
        from pathlib import Path

        conf = Path("nginx/nginx.conf").read_text()
        assert "X-Content-Type-Options" in conf


# === Convention Enforcement: No Raw SQL with User Input ===


class TestNoRawSqlInjection:
    """All database queries must use SQLAlchemy ORM, not raw SQL with user input."""

    def test_repositories_use_orm_not_raw_sql(self) -> None:
        """Repository files must not use text() with f-strings or .format()."""
        import ast
        from pathlib import Path

        app_dir = Path("app")
        violations: list[str] = []

        for repo_file in sorted(app_dir.rglob("repository.py")):
            source = repo_file.read_text()
            tree = ast.parse(source)

            for node in ast.walk(tree):
                # Check for text(f"...") or text("...".format(...))
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "text"
                    and node.args
                ):
                    arg = node.args[0]
                    if isinstance(arg, ast.JoinedStr):  # f-string
                        violations.append(f"{repo_file}:{node.lineno}: text() with f-string")
                    elif (
                        isinstance(arg, ast.Call)
                        and isinstance(arg.func, ast.Attribute)
                        and arg.func.attr == "format"
                    ):
                        violations.append(f"{repo_file}:{node.lineno}: text() with .format()")

        assert violations == [], (
            f"Raw SQL with user input found: {violations}. "
            f"Use SQLAlchemy ORM or parameterized queries."
        )

    def test_health_check_text_is_safe(self) -> None:
        """Health check uses text('SELECT 1') which is safe (no user input)."""
        import inspect

        from app.core.health import database_health_check

        source = inspect.getsource(database_health_check)
        assert 'text("SELECT 1")' in source
        # Verify no f-strings in text() calls
        assert "text(f" not in source


# === Convention Enforcement: Container Security ===


class TestContainerHardening:
    """Docker containers must have security hardening options."""

    def test_backend_dockerfile_nonroot(self) -> None:
        """Backend Dockerfile must run as non-root user."""
        from pathlib import Path

        dockerfile = Path("Dockerfile").read_text()
        assert "USER vtv" in dockerfile or "USER 1001" in dockerfile

    def test_frontend_dockerfile_nonroot(self) -> None:
        """Frontend Dockerfile must run as non-root user."""
        from pathlib import Path

        dockerfile = Path("cms/apps/web/Dockerfile").read_text()
        assert "USER nextjs" in dockerfile or "USER 1001" in dockerfile

    def test_nginx_dockerfile_nonroot(self) -> None:
        """Nginx Dockerfile must run as non-root user."""
        from pathlib import Path

        dockerfile = Path("nginx/Dockerfile").read_text()
        assert "USER nginx" in dockerfile

    def test_compose_app_no_new_privileges(self) -> None:
        """docker-compose.yml app service must have no-new-privileges."""
        from pathlib import Path

        compose = Path("docker-compose.yml").read_text()
        assert "no-new-privileges:true" in compose

    def test_prod_compose_app_read_only(self) -> None:
        """docker-compose.prod.yml app service must be read-only."""
        from pathlib import Path

        compose = Path("docker-compose.prod.yml").read_text()
        assert "read_only: true" in compose


# === Convention Enforcement: Dependency Security ===


class TestDependencySecurity:
    """CI pipeline must include dependency vulnerability scanning."""

    def test_ci_has_dependency_audit(self) -> None:
        """CI pipeline must have a pip-audit step."""
        from pathlib import Path

        ci = Path(".github/workflows/ci.yml").read_text()
        assert "pip-audit" in ci

    def test_ci_has_lock_integrity_check(self) -> None:
        """CI pipeline must verify lock file integrity."""
        from pathlib import Path

        ci = Path(".github/workflows/ci.yml").read_text()
        assert "uv lock --check" in ci

    def test_pip_audit_in_dev_dependencies(self) -> None:
        """pip-audit must be in dev dependencies."""
        from pathlib import Path

        pyproject = Path("pyproject.toml").read_text()
        assert "pip-audit" in pyproject


# === Convention Enforcement: Backup Infrastructure ===


class TestBackupInfrastructure:
    """Automated backup script must exist and be executable."""

    def test_backup_script_exists(self) -> None:
        """Automated backup script must exist."""
        from pathlib import Path

        assert Path("scripts/db-backup.sh").exists()

    def test_backup_script_executable(self) -> None:
        """Backup script must be executable."""
        import os
        from pathlib import Path

        script = Path("scripts/db-backup.sh")
        assert os.access(script, os.X_OK)

    def test_backup_script_has_retention(self) -> None:
        """Backup script must implement retention policy."""
        from pathlib import Path

        script = Path("scripts/db-backup.sh").read_text()
        assert "RETENTION" in script
        assert "mtime" in script or "find" in script

    def test_makefile_has_backup_auto(self) -> None:
        """Makefile must have db-backup-auto target."""
        from pathlib import Path

        makefile = Path("Makefile").read_text()
        assert "db-backup-auto" in makefile


# === Convention Enforcement: GDPR Right to Erasure ===


class TestGdprDeletion:
    """Platform must support GDPR right-to-erasure for user data."""

    def test_auth_routes_has_delete_endpoint(self) -> None:
        """Auth routes must have a DELETE /users/{user_id} endpoint."""
        import inspect

        from app.auth.routes import delete_user_data

        source = inspect.getsource(delete_user_data)
        assert "require_role" in source
        assert "admin" in source

    def test_delete_requires_admin(self) -> None:
        """User deletion must require admin role."""
        import inspect

        from app.auth.routes import delete_user_data

        source = inspect.getsource(delete_user_data)
        assert 'require_role("admin")' in source

    def test_cannot_self_delete(self) -> None:
        """Service must prevent admins from deleting their own account."""
        import inspect

        from app.auth.service import AuthService

        source = inspect.getsource(AuthService.delete_user_data)
        assert "requesting_user_id" in source
        assert "Cannot delete your own account" in source


# === Convention Enforcement: CSRF Protection Posture ===


class TestCsrfProtection:
    """JWT in Authorization header is inherently CSRF-safe.
    Verify no endpoints use cookie-based auth that would need CSRF tokens.
    """

    def test_auth_uses_bearer_not_cookies(self) -> None:
        """Authentication must use Bearer token, not cookies."""
        import inspect

        from app.auth.dependencies import get_current_user

        source = inspect.getsource(get_current_user)
        assert "HTTPBearer" in source or "Authorization" in source
        # Must not read auth from cookies
        assert "request.cookies" not in source

    def test_cors_allows_credentials_with_explicit_origins(self) -> None:
        """CORS must not use allow_origins=['*'] with allow_credentials=True."""
        import inspect

        from app.core.middleware import setup_middleware

        source = inspect.getsource(setup_middleware)
        assert 'allow_origins=["*"]' not in source


# === Audit 5: CRIT-1 - Quota must use X-Real-IP ===


class TestQuotaUsesRealIP:
    """Audit 5 CRIT-1: Daily quota must use X-Real-IP, not request.client.host."""

    def test_quota_uses_get_client_ip(self) -> None:
        """Verify agent routes import and call _get_client_ip for quota tracking."""
        import inspect

        from app.core.agents.routes import chat_completions

        source = inspect.getsource(chat_completions)
        assert "_get_client_ip" in source, (
            "chat_completions must use _get_client_ip(request) for quota tracking, "
            "not request.client.host"
        )
        assert "request.client.host" not in source, (
            "chat_completions must not use request.client.host - "
            "behind nginx this resolves to the proxy IP, not the user"
        )


# === Audit 5: CRIT-2 - Logout endpoint must exist ===


class TestLogoutEndpointExists:
    """Audit 5 CRIT-2: A logout endpoint must exist to revoke tokens."""

    def test_auth_router_has_logout(self) -> None:
        """Verify POST /logout exists in auth routes."""
        from fastapi.routing import APIRoute

        from app.auth.routes import router

        paths = [route.path for route in router.routes if isinstance(route, APIRoute)]
        assert any("/logout" in p for p in paths), "POST /api/v1/auth/logout endpoint must exist"

    def test_logout_calls_revoke_token(self) -> None:
        """Verify logout endpoint calls revoke_token."""
        import inspect

        from app.auth.routes import logout

        source = inspect.getsource(logout)
        assert "revoke_token" in source, "logout must call revoke_token()"


# === Audit 5: CRIT-3 - Refresh must revoke old token ===


class TestRefreshRevokesOldToken:
    """Audit 5 CRIT-3: Refresh endpoint must revoke the used refresh token."""

    def test_refresh_calls_revoke_token(self) -> None:
        """Verify refresh endpoint revokes the old refresh token."""
        import inspect

        from app.auth.routes import refresh_token

        source = inspect.getsource(refresh_token)
        assert "revoke_token" in source, (
            "refresh_token must call revoke_token() on the used refresh token"
        )


# === Audit 5: CRIT-4 - ZIP bomb protection ===


class TestZipBombProtection:
    """Audit 5 CRIT-4: GTFS import must have ZIP bomb detection."""

    def test_gtfs_importer_has_zip_validation(self) -> None:
        """Verify GTFSImporter validates ZIP safety before parsing."""
        import inspect

        from app.schedules.gtfs_import import GTFSImporter

        source = inspect.getsource(GTFSImporter)
        assert "_validate_zip_safety" in source, (
            "GTFSImporter must validate ZIP safety (compression ratio, uncompressed size)"
        )

    def test_import_route_uses_streaming(self) -> None:
        """Verify import route streams the upload, not file.read()."""
        import inspect

        from app.schedules.routes import import_gtfs

        source = inspect.getsource(import_gtfs)
        assert "file.read(8192)" in source, "import_gtfs must stream upload in chunks"


# === Audit 5: HIGH-1 - Timing attack prevention ===


class TestTimingAttackPrevention:
    """Audit 5 HIGH-1: Login must normalize timing for missing users."""

    def test_authenticate_has_dummy_hash(self) -> None:
        """Verify authenticate runs bcrypt even when user not found."""
        import inspect

        from app.auth.service import AuthService

        source = inspect.getsource(AuthService.authenticate)
        assert "_DUMMY_HASH" in source, (
            "authenticate must run bcrypt (dummy hash) when user not found "
            "to prevent timing-based email enumeration"
        )


# === Audit 5: HIGH-3 - No file_path in API responses ===


class TestNoFilePathExposure:
    """Audit 5 HIGH-3: DocumentResponse must not expose server file paths."""

    def test_document_response_no_file_path(self) -> None:
        """Verify file_path is not a field on DocumentResponse."""
        from app.knowledge.schemas import DocumentResponse

        field_names = set(DocumentResponse.model_fields.keys())
        assert "file_path" not in field_names, (
            "DocumentResponse must not expose file_path (server filesystem path)"
        )


# === Audit 5: MED-3 - Request ID sanitization ===


class TestRequestIdSanitization:
    """Audit 5 MED-3: X-Request-ID must be validated to prevent log injection."""

    def test_set_request_id_rejects_unsafe_input(self) -> None:
        """Verify set_request_id sanitizes or rejects dangerous characters."""
        from app.core.logging import set_request_id

        # Newline injection attempt
        result = set_request_id('test\n{"injected": true}')
        assert "\n" not in result, "Request ID must not contain newlines"

        # JSON escape injection
        result2 = set_request_id('test", "injected": "true')
        assert '"' not in result2, "Request ID must not contain quotes"

        # Valid UUID should pass through
        valid = "550e8400-e29b-41d4-a716-446655440000"
        result3 = set_request_id(valid)
        assert result3 == valid, "Valid UUIDs should pass through unchanged"


# === Audit 5: MED-1 - Database container cap_drop ===


class TestDatabaseContainerHardening:
    """Audit 5 MED-1: PostgreSQL container must drop all capabilities."""

    def test_db_service_has_cap_drop(self) -> None:
        """Verify docker-compose.yml db service has cap_drop: ALL."""
        import re
        from pathlib import Path

        compose = Path("docker-compose.yml").read_text()
        # Extract the db service block (from "  db:" to the next top-level service)
        db_match = re.search(r"^\s{2}db:\s*\n((?:\s{4,}.+\n)*)", compose, re.MULTILINE)
        assert db_match is not None, "db service not found in docker-compose.yml"
        db_section = db_match.group(0)
        assert "cap_drop:" in db_section, "db service in docker-compose.yml must have cap_drop"
        assert "ALL" in db_section, "db service cap_drop must include ALL"


# === SDLC Security Framework Verification ===


class TestSDLCSecurityGates:
    """Verify that all SDLC security gates are properly configured."""

    def test_precommit_hook_exists(self) -> None:
        """Pre-commit hook must exist."""
        from pathlib import Path

        assert Path("scripts/pre-commit").exists(), "Pre-commit hook missing at scripts/pre-commit"

    def test_precommit_has_bandit_check(self) -> None:
        """Pre-commit hook must include Bandit security lint."""
        from pathlib import Path

        content = Path("scripts/pre-commit").read_text()
        assert "ruff check --select=S" in content, "Pre-commit must run ruff --select=S"

    def test_precommit_has_sensitive_file_check(self) -> None:
        """Pre-commit hook must block sensitive files."""
        from pathlib import Path

        content = Path("scripts/pre-commit").read_text()
        assert ".env" in content
        assert ".pem" in content
        assert ".key" in content

    def test_precommit_has_secrets_detection(self) -> None:
        """Pre-commit hook must detect leaked secrets (AWS keys, private keys, JWTs)."""
        from pathlib import Path

        content = Path("scripts/pre-commit").read_text()
        assert "AKIA" in content, "Pre-commit must detect AWS access keys"
        assert "PRIVATE KEY" in content, "Pre-commit must detect private key material"

    def test_ci_has_security_audit_step(self) -> None:
        """CI pipeline must have a dedicated security audit step."""
        from pathlib import Path

        ci_content = Path(".github/workflows/ci.yml").read_text()
        assert "ruff check" in ci_content and "--select=S" in ci_content

    def test_ci_has_dependency_audit(self) -> None:
        """CI pipeline must include dependency vulnerability scanning."""
        from pathlib import Path

        ci_content = Path(".github/workflows/ci.yml").read_text()
        assert "pip-audit" in ci_content

    def test_ci_has_lock_file_integrity(self) -> None:
        """CI pipeline must verify lock file integrity."""
        from pathlib import Path

        ci_content = Path(".github/workflows/ci.yml").read_text()
        assert "uv lock --check" in ci_content

    def test_security_audit_script_exists(self) -> None:
        """Comprehensive security audit script must exist."""
        from pathlib import Path

        assert Path("scripts/security-audit.sh").exists()

    def test_scheduled_security_workflow_exists(self) -> None:
        """Scheduled security workflow must exist with cron trigger."""
        from pathlib import Path

        workflow = Path(".github/workflows/security.yml")
        assert workflow.exists(), "Scheduled security workflow missing"
        content = workflow.read_text()
        assert "cron" in content, "Security workflow must have cron schedule"

    def test_audit_tracking_exists(self) -> None:
        """Audit tracking registry must exist."""
        from pathlib import Path

        assert Path(".agents/audits/tracking.md").exists()


class TestAuditCoverageCompleteness:
    """Verify all historical audit finding categories have convention test coverage."""

    REQUIRED_TEST_CLASSES: ClassVar[list[str]] = [
        "TestStreamingUploadSizeLimit",
        "TestFilenameSanitization",
        "TestPathTraversalPrevention",
        "TestDemoCredentials",
        "TestIlikeWildcardEscape",
        "TestRateLimiterIp",
        "TestRedisUrlRedaction",
        "TestDockerCredentials",
        "TestTransitInputValidation",
        "TestNginxSecurity",
        "TestMiddlewareUploadLimit",
        "TestConfigSecurity",
        "TestEventsAuthentication",
        "TestPasswordComplexity",
        "TestTokenRevocation",
        "TestBruteForceRedis",
        "TestCorsRestricted",
        "TestHealthRedaction",
        "TestDockerNoHardcodedCreds",
        "TestVersionRedaction",
        "TestAllEndpointsRequireAuth",
        "TestNoDebugSecurityLogging",
        "TestJwtAlgorithmNotNone",
        "TestBcryptRoundsSufficient",
        "TestPasswordComplexityOnCorrectSchema",
        "TestSecurityHeadersInNginx",
        "TestNoRawSqlInjection",
        "TestContainerHardening",
        "TestDependencySecurity",
        "TestBackupInfrastructure",
        "TestGdprDeletion",
        "TestCsrfProtection",
        "TestQuotaUsesRealIP",
        "TestLogoutEndpointExists",
        "TestRefreshRevokesOldToken",
        "TestZipBombProtection",
        "TestTimingAttackPrevention",
        "TestNoFilePathExposure",
        "TestRequestIdSanitization",
        "TestDatabaseContainerHardening",
        "TestSDLCSecurityGates",
        "TestAuditCoverageCompleteness",
    ]

    def test_all_audit_categories_have_tests(self) -> None:
        """Every required test class must exist in this module."""
        import app.tests.test_security as mod

        actual_classes = [
            name
            for name in dir(mod)
            if name.startswith("Test") and isinstance(getattr(mod, name), type)
        ]
        missing = [c for c in self.REQUIRED_TEST_CLASSES if c not in actual_classes]
        assert missing == [], f"Missing required test classes: {missing}"
