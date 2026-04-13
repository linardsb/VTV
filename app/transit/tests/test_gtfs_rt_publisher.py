# pyright: reportCallIssue=false, reportUnknownMemberType=false
# pyright: reportMissingTypeStubs=false, reportUnknownVariableType=false
"""Tests for LV-2.4 GTFS-RT publisher and endpoint."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.transit import gtfs_realtime_pb2

from app.core.rate_limit import limiter

limiter.enabled = False


def _vehicle_json(
    feed_id: str = "riga",
    vehicle_id: str = "v1",
    route_id: str = "22",
    latitude: float = 56.95,
    longitude: float = 24.11,
    status: str = "IN_TRANSIT_TO",
    timestamp: int = 1700000000,
) -> str:
    """Build a JSON string matching the EnrichedVehicle Redis format."""
    return json.dumps(
        {
            "feed_id": feed_id,
            "vehicle_id": vehicle_id,
            "route_id": route_id,
            "latitude": latitude,
            "longitude": longitude,
            "bearing": 180.0,
            "speed": 12.5,
            "current_status": status,
            "stop_id": "stop_1",
            "trip_id": "trip_1",
            "vehicle_label": "Bus 22",
            "timestamp": timestamp,
        }
    )


def _mock_redis(
    vehicle_data: dict[str, list[str]] | None = None,
) -> AsyncMock:
    """Create a mock Redis client with feed vehicle data.

    Args:
        vehicle_data: Mapping of feed_id -> list of JSON vehicle strings.
            If None, defaults to empty.
    """
    if vehicle_data is None:
        vehicle_data = {}

    redis = AsyncMock()

    # smembers returns set of vehicle IDs per feed
    async def _smembers(key: str) -> set[str]:
        for fid, vehicles in vehicle_data.items():
            if key == f"feed:{fid}:vehicles":
                return {json.loads(v)["vehicle_id"] for v in vehicles}
        return set()

    redis.smembers = AsyncMock(side_effect=_smembers)

    # mget returns vehicle JSON values
    async def _mget(keys: list[str]) -> list[str | None]:
        results: list[str | None] = []
        for k in keys:
            found = False
            for fid, vehicles in vehicle_data.items():
                for v_json in vehicles:
                    v = json.loads(v_json)
                    if k == f"vehicle:{fid}:{v['vehicle_id']}":
                        results.append(v_json)
                        found = True
                        break
                if found:
                    break
            if not found:
                results.append(None)
        return results

    redis.mget = AsyncMock(side_effect=_mget)

    # get/set for cache
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()

    return redis


def _mock_settings(feed_ids: list[str] | None = None) -> MagicMock:
    """Create mock settings with transit feeds."""
    if feed_ids is None:
        feed_ids = ["riga"]
    settings = MagicMock()
    feeds: list[MagicMock] = []
    for fid in feed_ids:
        feed = MagicMock()
        feed.feed_id = fid
        feed.enabled = True
        feeds.append(feed)
    settings.transit_feeds = feeds
    return settings


class TestBuildCombinedFeed:
    """Tests for the build_combined_feed function."""

    @pytest.mark.asyncio
    async def test_single_feed_serialization(self) -> None:
        """One vehicle round-trips through protobuf correctly."""
        v_json = _vehicle_json()
        redis = _mock_redis({"riga": [v_json]})

        with (
            patch("app.transit.gtfs_rt_publisher.get_redis", return_value=redis),
            patch("app.transit.gtfs_rt_publisher.get_settings", return_value=_mock_settings()),
        ):
            from app.transit.gtfs_rt_publisher import build_combined_feed

            result = await build_combined_feed()

        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(result)

        assert feed.header.gtfs_realtime_version == "2.0"
        assert feed.header.timestamp > 0
        assert len(feed.entity) == 1

        entity = feed.entity[0]
        assert entity.id == "riga_v1"
        assert entity.vehicle.vehicle.id == "v1"
        assert entity.vehicle.trip.route_id == "22"
        assert abs(entity.vehicle.position.latitude - 56.95) < 0.01
        assert entity.vehicle.current_status == 2  # IN_TRANSIT_TO

    @pytest.mark.asyncio
    async def test_multi_feed_assembly(self) -> None:
        """Two feeds x 2 vehicles produces 4 entities."""
        data = {
            "riga": [
                _vehicle_json(feed_id="riga", vehicle_id="v1"),
                _vehicle_json(feed_id="riga", vehicle_id="v2"),
            ],
            "liepaja": [
                _vehicle_json(feed_id="liepaja", vehicle_id="v3"),
                _vehicle_json(feed_id="liepaja", vehicle_id="v4"),
            ],
        }
        redis = _mock_redis(data)

        with (
            patch("app.transit.gtfs_rt_publisher.get_redis", return_value=redis),
            patch(
                "app.transit.gtfs_rt_publisher.get_settings",
                return_value=_mock_settings(["riga", "liepaja"]),
            ),
        ):
            from app.transit.gtfs_rt_publisher import build_combined_feed

            result = await build_combined_feed()

        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(result)
        assert len(feed.entity) == 4
        ids = {e.id for e in feed.entity}
        assert "riga_v1" in ids
        assert "liepaja_v4" in ids

    @pytest.mark.asyncio
    async def test_empty_feeds_returns_valid_feed(self) -> None:
        """No vehicles produces a valid FeedMessage with 0 entities."""
        redis = _mock_redis({})

        with (
            patch("app.transit.gtfs_rt_publisher.get_redis", return_value=redis),
            patch("app.transit.gtfs_rt_publisher.get_settings", return_value=_mock_settings()),
        ):
            from app.transit.gtfs_rt_publisher import build_combined_feed

            result = await build_combined_feed()

        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(result)
        assert len(feed.entity) == 0
        assert feed.header.gtfs_realtime_version == "2.0"

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_bytes(self) -> None:
        """Pre-populated cache key skips vehicle reads."""
        cached_bytes = b"\x0a\x02\x10\x00"
        redis = _mock_redis()
        redis.get = AsyncMock(return_value=cached_bytes)

        with (
            patch("app.transit.gtfs_rt_publisher.get_redis", return_value=redis),
            patch("app.transit.gtfs_rt_publisher.get_settings", return_value=_mock_settings()),
        ):
            from app.transit.gtfs_rt_publisher import build_combined_feed

            result = await build_combined_feed()

        assert result == cached_bytes
        redis.smembers.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_miss_populates_cache(self) -> None:
        """Cache SET is called after build with correct key and TTL."""
        redis = _mock_redis({"riga": [_vehicle_json()]})

        with (
            patch("app.transit.gtfs_rt_publisher.get_redis", return_value=redis),
            patch("app.transit.gtfs_rt_publisher.get_settings", return_value=_mock_settings()),
        ):
            from app.transit.gtfs_rt_publisher import build_combined_feed

            await build_combined_feed()

        redis.set.assert_called_once()
        call_args = redis.set.call_args
        assert call_args[0][0] == "gtfs_rt:combined:vehicle_positions"
        assert call_args[1]["ex"] == 5

    @pytest.mark.asyncio
    async def test_feed_id_filter(self) -> None:
        """Filtering by feed_id reads only that feed's vehicles."""
        data = {
            "riga": [_vehicle_json(feed_id="riga", vehicle_id="v1")],
            "liepaja": [_vehicle_json(feed_id="liepaja", vehicle_id="v2")],
        }
        redis = _mock_redis(data)

        with (
            patch("app.transit.gtfs_rt_publisher.get_redis", return_value=redis),
            patch(
                "app.transit.gtfs_rt_publisher.get_settings",
                return_value=_mock_settings(["riga", "liepaja"]),
            ),
        ):
            from app.transit.gtfs_rt_publisher import build_combined_feed

            result = await build_combined_feed(feed_id="riga")

        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(result)
        assert len(feed.entity) == 1
        assert feed.entity[0].id == "riga_v1"

    @pytest.mark.asyncio
    async def test_status_mapping(self) -> None:
        """VehicleStopStatus strings map to correct protobuf enum values."""
        vehicles = [
            _vehicle_json(vehicle_id="v1", status="IN_TRANSIT_TO"),
            _vehicle_json(vehicle_id="v2", status="STOPPED_AT"),
            _vehicle_json(vehicle_id="v3", status="INCOMING_AT"),
        ]
        redis = _mock_redis({"riga": vehicles})

        with (
            patch("app.transit.gtfs_rt_publisher.get_redis", return_value=redis),
            patch("app.transit.gtfs_rt_publisher.get_settings", return_value=_mock_settings()),
        ):
            from app.transit.gtfs_rt_publisher import build_combined_feed

            result = await build_combined_feed()

        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(result)
        statuses = {e.vehicle.vehicle.id: e.vehicle.current_status for e in feed.entity}
        assert statuses["v1"] == 2  # IN_TRANSIT_TO
        assert statuses["v2"] == 1  # STOPPED_AT
        assert statuses["v3"] == 0  # INCOMING_AT


class TestGtfsRtEndpoint:
    """Tests for the GET /gtfs-rt/vehicle_positions.pb endpoint."""

    @pytest.mark.asyncio
    async def test_returns_protobuf_content_type(self, client: MagicMock) -> None:
        """Response Content-Type is application/x-protobuf."""
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.header.gtfs_realtime_version = "2.0"
        pb_bytes: bytes = feed.SerializeToString()

        with patch(
            "app.transit.gtfs_rt_publisher.build_combined_feed",
            new_callable=AsyncMock,
            return_value=pb_bytes,
        ):
            response = client.get("/api/v1/transit/gtfs-rt/vehicle_positions.pb")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/x-protobuf"

    @pytest.mark.asyncio
    async def test_returns_valid_protobuf(self, client: MagicMock) -> None:
        """Response bytes parse as a valid FeedMessage."""
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.header.gtfs_realtime_version = "2.0"
        entity = feed.entity.add()
        entity.id = "riga_v1"
        entity.vehicle.vehicle.id = "v1"
        pb_bytes: bytes = feed.SerializeToString()

        with patch(
            "app.transit.gtfs_rt_publisher.build_combined_feed",
            new_callable=AsyncMock,
            return_value=pb_bytes,
        ):
            response = client.get("/api/v1/transit/gtfs-rt/vehicle_positions.pb")

        parsed = gtfs_realtime_pb2.FeedMessage()
        parsed.ParseFromString(response.content)
        assert len(parsed.entity) == 1
        assert parsed.entity[0].id == "riga_v1"

    @pytest.mark.asyncio
    async def test_feed_id_query_param(self, client: MagicMock) -> None:
        """feed_id query param is forwarded to build_combined_feed."""
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.header.gtfs_realtime_version = "2.0"
        pb_bytes: bytes = feed.SerializeToString()

        mock_build = AsyncMock(return_value=pb_bytes)
        with patch("app.transit.gtfs_rt_publisher.build_combined_feed", mock_build):
            response = client.get(
                "/api/v1/transit/gtfs-rt/vehicle_positions.pb",
                params={"feed_id": "riga"},
            )

        assert response.status_code == 200
        mock_build.assert_called_once_with(feed_id="riga")
