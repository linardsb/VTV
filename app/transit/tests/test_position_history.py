"""Tests for historical vehicle position storage models and schemas."""

from app.transit.models import VehiclePositionRecord
from app.transit.schemas import (
    HistoricalPosition,
    RouteDelayTrendPoint,
    RouteDelayTrendResponse,
    VehicleHistoryResponse,
)


class TestVehiclePositionRecordModel:
    """Tests for the VehiclePositionRecord SQLAlchemy model."""

    def test_tablename(self) -> None:
        assert VehiclePositionRecord.__tablename__ == "vehicle_positions"

    def test_required_columns_exist(self) -> None:
        columns = {c.name for c in VehiclePositionRecord.__table__.columns}
        required = {
            "id",
            "recorded_at",
            "feed_id",
            "vehicle_id",
            "route_id",
            "latitude",
            "longitude",
            "delay_seconds",
            "current_status",
        }
        assert required.issubset(columns)

    def test_optional_columns_exist(self) -> None:
        columns = {c.name for c in VehiclePositionRecord.__table__.columns}
        optional = {"bearing", "speed_kmh", "trip_id", "route_short_name"}
        assert optional.issubset(columns)


class TestHistoricalPositionSchema:
    """Tests for history response schemas."""

    def test_historical_position_creation(self) -> None:
        pos = HistoricalPosition(
            recorded_at="2026-03-07T12:00:00+00:00",
            vehicle_id="4521",
            route_id="22",
            route_short_name="22",
            latitude=56.9496,
            longitude=24.1052,
            delay_seconds=45,
            current_status="IN_TRANSIT_TO",
        )
        assert pos.vehicle_id == "4521"
        assert pos.delay_seconds == 45

    def test_historical_position_defaults(self) -> None:
        pos = HistoricalPosition(
            recorded_at="2026-03-07T12:00:00+00:00",
            vehicle_id="4521",
            route_id="22",
            route_short_name="22",
            latitude=56.9496,
            longitude=24.1052,
            current_status="IN_TRANSIT_TO",
        )
        assert pos.bearing is None
        assert pos.speed_kmh is None
        assert pos.delay_seconds == 0
        assert pos.feed_id == ""

    def test_vehicle_history_response(self) -> None:
        resp = VehicleHistoryResponse(
            vehicle_id="4521",
            count=0,
            positions=[],
            from_time="2026-03-07T00:00:00+00:00",
            to_time="2026-03-07T23:59:59+00:00",
        )
        assert resp.count == 0
        assert resp.vehicle_id == "4521"

    def test_route_delay_trend_response(self) -> None:
        point = RouteDelayTrendPoint(
            time_bucket="2026-03-07T12:00:00+00:00",
            avg_delay_seconds=30.5,
            min_delay_seconds=-10,
            max_delay_seconds=120,
            sample_count=42,
        )
        resp = RouteDelayTrendResponse(
            route_id="22",
            route_short_name="22",
            interval_minutes=60,
            count=1,
            data_points=[point],
            from_time="2026-03-07T00:00:00+00:00",
            to_time="2026-03-07T23:59:59+00:00",
        )
        assert resp.count == 1
        assert resp.data_points[0].sample_count == 42

    def test_vehicle_history_response_with_positions(self) -> None:
        pos = HistoricalPosition(
            recorded_at="2026-03-07T12:00:00+00:00",
            vehicle_id="4521",
            route_id="22",
            route_short_name="22",
            latitude=56.9496,
            longitude=24.1052,
            bearing=180.0,
            speed_kmh=32.4,
            delay_seconds=15,
            current_status="IN_TRANSIT_TO",
            feed_id="riga",
        )
        resp = VehicleHistoryResponse(
            vehicle_id="4521",
            count=1,
            positions=[pos],
            from_time="2026-03-07T00:00:00+00:00",
            to_time="2026-03-07T23:59:59+00:00",
        )
        assert resp.count == 1
        assert resp.positions[0].bearing == 180.0
