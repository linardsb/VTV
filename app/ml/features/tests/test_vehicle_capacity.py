# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
"""Tests for vehicle capacity lookup (ML-3.1)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ml.features.vehicle_capacity import (
    DEFAULT_CAPACITY,
    FALLBACK_CAPACITY,
    get_default_capacity,
    get_vehicle_capacities,
)


class TestGetDefaultCapacity:
    def test_known_types(self) -> None:
        assert get_default_capacity("bus") == 60
        assert get_default_capacity("tram") == 200
        assert get_default_capacity("trolleybus") == 80
        assert get_default_capacity("articulated_bus") == 100

    def test_unknown_type_falls_back(self) -> None:
        assert get_default_capacity("monorail") == FALLBACK_CAPACITY
        assert get_default_capacity("") == FALLBACK_CAPACITY

    def test_case_insensitive(self) -> None:
        assert get_default_capacity("BUS") == DEFAULT_CAPACITY["bus"]
        assert get_default_capacity("Tram") == DEFAULT_CAPACITY["tram"]


class TestGetVehicleCapacities:
    @pytest.fixture()
    def mock_db(self) -> AsyncMock:
        return AsyncMock()

    async def test_db_override(self, mock_db: AsyncMock) -> None:
        mappings_mock = MagicMock()
        mappings_mock.all.return_value = [
            {"fleet_number": "4521", "capacity": 75, "vehicle_type": "bus"}
        ]
        result_mock = MagicMock()
        result_mock.mappings.return_value = mappings_mock
        mock_db.execute.return_value = result_mock

        caps = await get_vehicle_capacities(mock_db, ["4521"])
        assert caps["4521"] == 75

    async def test_fallback_to_type_default(self, mock_db: AsyncMock) -> None:
        mappings_mock = MagicMock()
        empty_rows: list[dict[str, Any]] = []
        mappings_mock.all.return_value = empty_rows
        result_mock = MagicMock()
        result_mock.mappings.return_value = mappings_mock
        mock_db.execute.return_value = result_mock

        caps = await get_vehicle_capacities(
            mock_db,
            ["4521"],
            transport_types={"4521": "tram"},
        )
        assert caps["4521"] == 200

    async def test_fallback_to_60_for_unknown(self, mock_db: AsyncMock) -> None:
        mappings_mock = MagicMock()
        empty_rows: list[dict[str, Any]] = []
        mappings_mock.all.return_value = empty_rows
        result_mock = MagicMock()
        result_mock.mappings.return_value = mappings_mock
        mock_db.execute.return_value = result_mock

        caps = await get_vehicle_capacities(mock_db, ["9999"])
        assert caps["9999"] == FALLBACK_CAPACITY

    async def test_empty_list_returns_empty(self, mock_db: AsyncMock) -> None:
        caps = await get_vehicle_capacities(mock_db, [])
        assert caps == {}
        mock_db.execute.assert_not_called()
