"""Tests for e-ticket validation data pipeline (ML-1.2)."""

# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

import datetime
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

# Import httpx at module level for exception references in test methods
import httpx
import pytest

from app.transit.eticket_importer import (
    EticketRecord,
    _check_zip_bomb,
    backfill_all,
    build_archive_url,
    import_monthly_archive,
    parse_eticket_txt,
)
from app.transit.models import EticketImport, EticketValidation
from app.transit.tests.conftest import (
    make_eticket_line,
    make_eticket_txt,
)


class _AsyncCM:
    """Minimal async context manager wrapper for mocking."""

    def __init__(self, value: Any) -> None:
        self._value = value

    async def __aenter__(self) -> Any:
        return self._value

    async def __aexit__(self, *args: Any) -> bool:
        return False


def _async_cm(value: Any) -> _AsyncCM:
    """Create an async context manager that yields the given value."""
    return _AsyncCM(value)


def _async_cm_value(value: Any) -> _AsyncCM:
    """Create an async context manager for httpx.AsyncClient() usage."""
    return _AsyncCM(value)


class TestParseEticketTxt:
    """Unit tests for parse_eticket_txt."""

    def test_parse_basic(self, tmp_path: Path) -> None:
        """Parse 3 valid lines, verify field mapping."""
        lines = [
            make_eticket_line(record_id="R1", route_code="10"),
            make_eticket_line(record_id="R2", route_code="22"),
            make_eticket_line(record_id="R3", route_code="33"),
        ]
        txt_data = make_eticket_txt(lines)
        txt_path = tmp_path / "data.txt"
        txt_path.write_bytes(txt_data)

        records = list(parse_eticket_txt(txt_path))
        assert len(records) == 3
        assert records[0].record_id == "R1"
        assert records[0].route_code == "10"
        assert records[1].record_id == "R2"
        assert records[2].route_code == "33"
        assert isinstance(records[0], EticketRecord)
        assert isinstance(records[0].validated_at, datetime.datetime)

    def test_parse_latin1_encoding(self, tmp_path: Path) -> None:
        """Parse lines with Latin-1 special characters (e.g., umlauts)."""
        # Use actual Latin-1 encodable chars: e with dieresis, o with dieresis
        lines = [
            make_eticket_line(
                depot="R\u00e9gi-1",
                route_name="Mar\u00f6ruts 22",
            ),
        ]
        txt_data = make_eticket_txt(lines, encoding="latin-1")
        txt_path = tmp_path / "latvian.txt"
        txt_path.write_bytes(txt_data)

        records = list(parse_eticket_txt(txt_path))
        assert len(records) == 1
        assert "gi-1" in records[0].depot
        assert "ruts 22" in records[0].route_name

    def test_parse_skip_malformed(self, tmp_path: Path) -> None:
        """Lines with wrong field count are skipped."""
        txt_content = (
            "record_id;depot;transport_type;vehicle_number;"
            "route_name;route_code;direction;validation_id;validated_at\n"
            "R1;Riga-1;bus;4521;Route 22;22;A;VAL001;2026-01-15 08:30:00\n"
            "BAD;LINE;ONLY;THREE\n"
            "R2;Riga-1;bus;4521;Route 22;22;A;VAL002;2026-01-15 09:00:00\n"
        )
        txt_path = tmp_path / "mixed.txt"
        txt_path.write_bytes(txt_content.encode("latin-1"))

        records = list(parse_eticket_txt(txt_path))
        assert len(records) == 2
        assert records[0].record_id == "R1"
        assert records[1].record_id == "R2"

    def test_parse_empty_file(self, tmp_path: Path) -> None:
        """Header-only file yields 0 records."""
        header = (
            "record_id;depot;transport_type;vehicle_number;"
            "route_name;route_code;direction;validation_id;validated_at\n"
        )
        txt_path = tmp_path / "empty.txt"
        txt_path.write_bytes(header.encode("latin-1"))

        records = list(parse_eticket_txt(txt_path))
        assert len(records) == 0

    def test_parse_invalid_datetime(self, tmp_path: Path) -> None:
        """Lines with invalid datetime are skipped."""
        txt_content = (
            "record_id;depot;transport_type;vehicle_number;"
            "route_name;route_code;direction;validation_id;validated_at\n"
            "R1;Riga-1;bus;4521;Route 22;22;A;VAL001;NOT-A-DATE\n"
            "R2;Riga-1;bus;4521;Route 22;22;A;VAL002;2026-01-15 09:00:00\n"
        )
        txt_path = tmp_path / "bad_date.txt"
        txt_path.write_bytes(txt_content.encode("latin-1"))

        records = list(parse_eticket_txt(txt_path))
        assert len(records) == 1
        assert records[0].record_id == "R2"


class TestZipBombGuard:
    """Tests for ZIP bomb protection."""

    def test_rejects_oversized_archive(self, tmp_path: Path) -> None:
        """Archive with uncompressed size > limit is rejected."""
        zip_path = tmp_path / "bomb.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            # Create a file that claims to be large
            zf.writestr("big.txt", "x" * 1024)

        with zipfile.ZipFile(zip_path, "r") as zf:
            # Use a tiny limit to trigger the guard
            with pytest.raises(ValueError, match="exceeds limit"):
                _check_zip_bomb(zf, max_size_mb=0)

    def test_accepts_normal_archive(self, tmp_path: Path) -> None:
        """Archive within size limit passes."""
        zip_path = tmp_path / "ok.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("small.txt", "hello")

        with zipfile.ZipFile(zip_path, "r") as zf:
            _check_zip_bomb(zf, max_size_mb=1)  # Should not raise


class TestBuildArchiveUrl:
    """Tests for archive URL generation."""

    def test_basic_url(self) -> None:
        url = build_archive_url("https://data.rigassatiksme.lv/eticket/", "2026-01")
        assert url == "https://data.rigassatiksme.lv/eticket/2026-01.zip"

    def test_strips_trailing_slash(self) -> None:
        url = build_archive_url("https://example.com/data/", "2024-06")
        assert url == "https://example.com/data/2024-06.zip"

    def test_no_trailing_slash(self) -> None:
        url = build_archive_url("https://example.com/data", "2024-06")
        assert url == "https://example.com/data/2024-06.zip"


class TestImportMonthlyArchive:
    """Tests for import_monthly_archive using mocks."""

    @pytest.mark.asyncio
    async def test_skips_completed_month(self) -> None:
        """Already-completed month is skipped without downloading."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_import = MagicMock(spec=EticketImport)
        mock_result.scalar_one_or_none.return_value = mock_import
        mock_db.execute.return_value = mock_result

        settings = MagicMock()
        settings.eticket_max_archive_size_mb = 500
        settings.eticket_batch_size = 5000

        count = await import_monthly_archive(
            "https://example.com/2026-01.zip",
            "2026-01",
            db=mock_db,
            settings=settings,
        )

        assert count == 0

    @pytest.mark.asyncio
    async def test_sets_failed_on_download_error(self) -> None:
        """Download failure sets tracking status to failed."""
        mock_db = AsyncMock()
        first_result = MagicMock()
        first_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = first_result

        settings = MagicMock()
        settings.eticket_max_archive_size_mb = 500
        settings.eticket_batch_size = 5000

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found",
            request=httpx.Request("GET", "https://example.com/bad.zip"),
            response=httpx.Response(404),
        )

        # Build nested async context managers for httpx
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=_async_cm(mock_response))

        with (
            patch(
                "app.transit.eticket_importer.httpx.AsyncClient",
                return_value=_async_cm_value(mock_client),
            ),
            pytest.raises(httpx.HTTPStatusError),
        ):
            await import_monthly_archive(
                "https://example.com/bad.zip",
                "2026-01",
                db=mock_db,
                settings=settings,
            )

    @pytest.mark.asyncio
    async def test_temp_files_cleaned_on_failure(self) -> None:
        """Temp directory is cleaned up even after failure."""
        mock_db = AsyncMock()
        first_result = MagicMock()
        first_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = first_result

        settings = MagicMock()
        settings.eticket_max_archive_size_mb = 500
        settings.eticket_batch_size = 5000

        created_tmp_dirs: list[str] = []
        original_mkdtemp = tempfile.mkdtemp

        def tracking_mkdtemp(**kwargs: Any) -> str:
            result: str = original_mkdtemp(**kwargs)
            created_tmp_dirs.append(result)
            return result

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.ConnectError("fail")

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=_async_cm(mock_response))

        with (
            patch(
                "app.transit.eticket_importer.httpx.AsyncClient",
                return_value=_async_cm_value(mock_client),
            ),
            patch("app.transit.eticket_importer.tempfile.mkdtemp", side_effect=tracking_mkdtemp),
            pytest.raises(httpx.ConnectError),
        ):
            await import_monthly_archive(
                "https://example.com/fail.zip",
                "2026-01",
                db=mock_db,
                settings=settings,
            )

        # Verify temp dir was cleaned up
        for tmp_dir in created_tmp_dirs:
            assert not Path(tmp_dir).exists(), f"Temp dir not cleaned: {tmp_dir}"


class TestBackfillAll:
    """Tests for backfill_all."""

    @pytest.mark.asyncio
    async def test_skips_completed_months(self) -> None:
        """Backfill skips months already marked as completed."""
        mock_db = AsyncMock()

        # Mock: completed months query returns 2 months
        completed_result = MagicMock()
        completed_result.all.return_value = [("2018-01",), ("2018-02",)]
        mock_db.execute.return_value = completed_result

        settings = MagicMock()
        settings.eticket_archive_base_url = "https://example.com/eticket/"
        settings.eticket_max_archive_size_mb = 500
        settings.eticket_batch_size = 5000

        with patch(
            "app.transit.eticket_importer.import_monthly_archive",
            new_callable=AsyncMock,
            return_value=100,
        ) as mock_import:
            # Use a narrow range to keep the test fast
            with patch(
                "app.transit.eticket_importer.datetime",
            ) as mock_dt:
                mock_dt.datetime.now.return_value = datetime.datetime(
                    2018,
                    3,
                    15,
                    tzinfo=datetime.UTC,
                )
                mock_dt.UTC = datetime.UTC
                total = await backfill_all(
                    db=mock_db,
                    settings=settings,
                    dry_run=False,
                )

            # 2018-01 to 2018-03 = 3 months, 2 completed, 1 remaining
            assert mock_import.call_count == 1
            assert total == 100


class TestModels:
    """Tests for e-ticket SQLAlchemy model definitions."""

    def test_eticket_validation_columns(self) -> None:
        """EticketValidation has all expected columns."""
        columns = {c.name for c in EticketValidation.__table__.columns}
        expected = {
            "id",
            "record_id",
            "depot",
            "transport_type",
            "vehicle_number",
            "route_name",
            "route_code",
            "direction",
            "validation_id",
            "validated_at",
        }
        assert expected == columns

    def test_eticket_validation_tablename(self) -> None:
        assert EticketValidation.__tablename__ == "eticket_validations"

    def test_eticket_import_columns(self) -> None:
        """EticketImport has all expected columns including TimestampMixin."""
        columns = {c.name for c in EticketImport.__table__.columns}
        expected = {
            "id",
            "archive_month",
            "record_count",
            "status",
            "created_at",
            "updated_at",
        }
        assert expected == columns

    def test_eticket_import_tablename(self) -> None:
        assert EticketImport.__tablename__ == "eticket_imports"

    def test_eticket_validation_indexes(self) -> None:
        """Composite indexes exist on route_code+validated_at and vehicle_number+validated_at."""
        # Access table_args tuples to verify index names
        table_args = EticketValidation.__table_args__
        index_names = {arg.name for arg in table_args if hasattr(arg, "name")}
        assert "ix_eticket_route_time" in index_names
        assert "ix_eticket_vehicle_time" in index_names
