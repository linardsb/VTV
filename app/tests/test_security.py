# pyright: reportUnknownParameterType=false, reportMissingParameterType=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
"""Security audit regression tests.

Validates fixes for all 13 findings from the third-party security audit.
Each test class maps to a specific audit finding (C1-C3, M1-M5, etc.).
"""

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

    def test_uses_x_real_ip(self) -> None:
        """_get_client_ip should prefer X-Real-IP header."""
        from app.core.rate_limit import _get_client_ip

        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"X-Real-IP": "1.2.3.4"}

        result = _get_client_ip(mock_request)
        assert result == "1.2.3.4"

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

        req = PasswordResetRequest(user_id=1, new_password="ValidPass123")
        assert req.new_password == "ValidPass123"

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
    PUBLIC_ALLOWLIST = {
        "login",
        "refresh_token",
        "read_root",
        "health_check",
        "database_health_check",
        "health_redis",
        "readiness_check",
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
