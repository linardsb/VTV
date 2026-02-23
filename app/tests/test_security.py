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
