# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
"""Data access layer for geofence zone management and event tracking."""

import datetime
import json

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.geofences.models import Geofence, GeofenceEvent
from app.geofences.schemas import DwellTimeReport, GeofenceCreate, GeofenceUpdate
from app.shared.utils import escape_like


class GeofenceRepository:
    """Database operations for geofence zones."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with an async database session.

        Args:
            db: SQLAlchemy async session.
        """
        self.db = db

    async def get(self, geofence_id: int) -> Geofence | None:
        """Get a geofence by primary key ID.

        Args:
            geofence_id: The geofence's database ID.

        Returns:
            Geofence instance or None if not found.
        """
        result = await self.db.execute(select(Geofence).where(Geofence.id == geofence_id))
        return result.scalar_one_or_none()

    async def list_geofences(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        search: str | None = None,
        zone_type: str | None = None,
        is_active: bool | None = None,
    ) -> list[Geofence]:
        """List geofences with pagination and filtering.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to return.
            search: Case-insensitive search on name.
            zone_type: Filter by zone type.
            is_active: Filter by active status.

        Returns:
            List of Geofence instances.
        """
        query = select(Geofence)
        if search:
            pattern = f"%{escape_like(search)}%"
            query = query.where(Geofence.name.ilike(pattern))
        if zone_type is not None:
            query = query.where(Geofence.zone_type == zone_type)
        if is_active is not None:
            query = query.where(Geofence.is_active.is_(is_active))
        query = query.order_by(Geofence.id).offset(offset).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count(
        self,
        *,
        search: str | None = None,
        zone_type: str | None = None,
        is_active: bool | None = None,
    ) -> int:
        """Count geofences matching the given filters.

        Args:
            search: Case-insensitive search on name.
            zone_type: Filter by zone type.
            is_active: Filter by active status.

        Returns:
            Total number of matching geofences.
        """
        query = select(func.count()).select_from(Geofence)
        if search:
            pattern = f"%{escape_like(search)}%"
            query = query.where(Geofence.name.ilike(pattern))
        if zone_type is not None:
            query = query.where(Geofence.zone_type == zone_type)
        if is_active is not None:
            query = query.where(Geofence.is_active.is_(is_active))
        result = await self.db.execute(query)
        return result.scalar_one()

    async def create(self, data: GeofenceCreate, wkt_geometry: str) -> Geofence:
        """Create a new geofence zone.

        Args:
            data: Geofence creation data.
            wkt_geometry: WKT POLYGON string for the geometry.

        Returns:
            The newly created Geofence instance.
        """
        geofence = Geofence(
            name=data.name,
            zone_type=data.zone_type,
            geometry=func.ST_GeomFromText(wkt_geometry, 4326),
            color=data.color,
            description=data.description,
            alert_on_enter=data.alert_on_enter,
            alert_on_exit=data.alert_on_exit,
            alert_on_dwell=data.alert_on_dwell,
            dwell_threshold_minutes=data.dwell_threshold_minutes,
            alert_severity=data.alert_severity,
        )
        self.db.add(geofence)
        await self.db.commit()
        await self.db.refresh(geofence)
        return geofence

    async def update(
        self, geofence: Geofence, data: GeofenceUpdate, wkt_geometry: str | None
    ) -> Geofence:
        """Update an existing geofence zone.

        Args:
            geofence: The geofence instance to update.
            data: Fields to update (only set fields are applied).
            wkt_geometry: New WKT POLYGON string if coordinates changed.

        Returns:
            The updated Geofence instance.
        """
        for field, value in data.model_dump(exclude_unset=True, exclude={"coordinates"}).items():
            setattr(geofence, field, value)
        if wkt_geometry is not None:
            geofence.geometry = func.ST_GeomFromText(wkt_geometry, 4326)
        await self.db.commit()
        await self.db.refresh(geofence)
        return geofence

    async def delete(self, geofence: Geofence) -> None:
        """Delete a geofence zone.

        Args:
            geofence: The geofence instance to delete.
        """
        await self.db.delete(geofence)
        await self.db.commit()

    async def get_active_geofences(self) -> list[Geofence]:
        """Get all active geofences.

        Returns:
            List of active Geofence instances.
        """
        result = await self.db.execute(select(Geofence).where(Geofence.is_active.is_(True)))
        return list(result.scalars().all())

    async def check_containment(self, lat: float, lon: float) -> list[Geofence]:
        """Find all active geofences containing the given point.

        Uses PostGIS ST_Contains for spatial containment check.

        Args:
            lat: Latitude of the point.
            lon: Longitude of the point.

        Returns:
            List of Geofence instances containing the point.
        """
        point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
        result = await self.db.execute(
            select(Geofence).where(
                Geofence.is_active.is_(True),
                func.ST_Contains(Geofence.geometry, point),
            )
        )
        return list(result.scalars().all())

    async def get_coordinates(self, geofence: Geofence) -> list[list[float]]:
        """Extract polygon coordinates from PostGIS geometry.

        Args:
            geofence: The geofence instance.

        Returns:
            List of [lon, lat] coordinate pairs.
        """
        result = await self.db.execute(
            select(func.ST_AsGeoJSON(Geofence.geometry)).where(Geofence.id == geofence.id)
        )
        geojson_str = result.scalar_one()
        geojson = json.loads(str(geojson_str))
        coordinates: list[list[float]] = geojson["coordinates"][0]
        return coordinates


class GeofenceEventRepository:
    """Database operations for geofence events."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with an async database session.

        Args:
            db: SQLAlchemy async session.
        """
        self.db = db

    async def create(
        self,
        *,
        geofence_id: int,
        vehicle_id: str,
        event_type: str,
        entered_at: datetime.datetime,
        latitude: float,
        longitude: float,
    ) -> GeofenceEvent:
        """Create a new geofence event.

        Args:
            geofence_id: The geofence's database ID.
            vehicle_id: The vehicle identifier string.
            event_type: Event type (enter, exit, dwell_exceeded).
            entered_at: When the vehicle entered the zone.
            latitude: Vehicle latitude at event time.
            longitude: Vehicle longitude at event time.

        Returns:
            The newly created GeofenceEvent instance.
        """
        event = GeofenceEvent(
            geofence_id=geofence_id,
            vehicle_id=vehicle_id,
            event_type=event_type,
            entered_at=entered_at,
            latitude=latitude,
            longitude=longitude,
        )
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def get_open_entry(self, geofence_id: int, vehicle_id: str) -> GeofenceEvent | None:
        """Find an open entry event (no exit yet) for a vehicle in a geofence.

        Args:
            geofence_id: The geofence's database ID.
            vehicle_id: The vehicle identifier string.

        Returns:
            GeofenceEvent with event_type='enter' and exited_at=NULL, or None.
        """
        result = await self.db.execute(
            select(GeofenceEvent).where(
                GeofenceEvent.geofence_id == geofence_id,
                GeofenceEvent.vehicle_id == vehicle_id,
                GeofenceEvent.event_type == "enter",
                GeofenceEvent.exited_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def close_entry(
        self, event: GeofenceEvent, exited_at: datetime.datetime
    ) -> GeofenceEvent:
        """Close an open entry event by setting exit time and dwell duration.

        Args:
            event: The open entry event to close.
            exited_at: When the vehicle exited the zone.

        Returns:
            The updated GeofenceEvent instance.
        """
        event.exited_at = exited_at
        event.dwell_seconds = int((exited_at - event.entered_at).total_seconds())
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def list_by_geofence(
        self,
        geofence_id: int,
        *,
        offset: int = 0,
        limit: int = 20,
        event_type: str | None = None,
        start_time: datetime.datetime | None = None,
        end_time: datetime.datetime | None = None,
    ) -> list[GeofenceEvent]:
        """List events for a specific geofence with filtering.

        Args:
            geofence_id: The geofence's database ID.
            offset: Number of records to skip.
            limit: Maximum records to return.
            event_type: Filter by event type.
            start_time: Filter events after this time.
            end_time: Filter events before this time.

        Returns:
            List of GeofenceEvent instances.
        """
        query = select(GeofenceEvent).where(GeofenceEvent.geofence_id == geofence_id)
        if event_type is not None:
            query = query.where(GeofenceEvent.event_type == event_type)
        if start_time is not None:
            query = query.where(GeofenceEvent.entered_at >= start_time)
        if end_time is not None:
            query = query.where(GeofenceEvent.entered_at <= end_time)
        query = query.order_by(GeofenceEvent.entered_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count_by_geofence(
        self,
        geofence_id: int,
        *,
        event_type: str | None = None,
        start_time: datetime.datetime | None = None,
        end_time: datetime.datetime | None = None,
    ) -> int:
        """Count events for a specific geofence with filtering.

        Args:
            geofence_id: The geofence's database ID.
            event_type: Filter by event type.
            start_time: Filter events after this time.
            end_time: Filter events before this time.

        Returns:
            Total number of matching events.
        """
        query = (
            select(func.count())
            .select_from(GeofenceEvent)
            .where(GeofenceEvent.geofence_id == geofence_id)
        )
        if event_type is not None:
            query = query.where(GeofenceEvent.event_type == event_type)
        if start_time is not None:
            query = query.where(GeofenceEvent.entered_at >= start_time)
        if end_time is not None:
            query = query.where(GeofenceEvent.entered_at <= end_time)
        result = await self.db.execute(query)
        return result.scalar_one()

    async def list_all(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        vehicle_id: str | None = None,
        event_type: str | None = None,
        geofence_id: int | None = None,
        start_time: datetime.datetime | None = None,
        end_time: datetime.datetime | None = None,
    ) -> list[GeofenceEvent]:
        """List all geofence events with filtering.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to return.
            vehicle_id: Filter by vehicle ID.
            event_type: Filter by event type.
            geofence_id: Filter by geofence ID.
            start_time: Filter events after this time.
            end_time: Filter events before this time.

        Returns:
            List of GeofenceEvent instances.
        """
        query = select(GeofenceEvent)
        if vehicle_id is not None:
            query = query.where(GeofenceEvent.vehicle_id == vehicle_id)
        if event_type is not None:
            query = query.where(GeofenceEvent.event_type == event_type)
        if geofence_id is not None:
            query = query.where(GeofenceEvent.geofence_id == geofence_id)
        if start_time is not None:
            query = query.where(GeofenceEvent.entered_at >= start_time)
        if end_time is not None:
            query = query.where(GeofenceEvent.entered_at <= end_time)
        query = query.order_by(GeofenceEvent.entered_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count_all(
        self,
        *,
        vehicle_id: str | None = None,
        event_type: str | None = None,
        geofence_id: int | None = None,
        start_time: datetime.datetime | None = None,
        end_time: datetime.datetime | None = None,
    ) -> int:
        """Count all geofence events with filtering.

        Args:
            vehicle_id: Filter by vehicle ID.
            event_type: Filter by event type.
            geofence_id: Filter by geofence ID.
            start_time: Filter events after this time.
            end_time: Filter events before this time.

        Returns:
            Total number of matching events.
        """
        query = select(func.count()).select_from(GeofenceEvent)
        if vehicle_id is not None:
            query = query.where(GeofenceEvent.vehicle_id == vehicle_id)
        if event_type is not None:
            query = query.where(GeofenceEvent.event_type == event_type)
        if geofence_id is not None:
            query = query.where(GeofenceEvent.geofence_id == geofence_id)
        if start_time is not None:
            query = query.where(GeofenceEvent.entered_at >= start_time)
        if end_time is not None:
            query = query.where(GeofenceEvent.entered_at <= end_time)
        result = await self.db.execute(query)
        return result.scalar_one()

    async def get_dwell_report(
        self,
        geofence_id: int,
        geofence_name: str,
        start_time: datetime.datetime | None = None,
        end_time: datetime.datetime | None = None,
    ) -> DwellTimeReport:
        """Get aggregated dwell time statistics for a geofence.

        Args:
            geofence_id: The geofence's database ID.
            geofence_name: The geofence name for the report.
            start_time: Filter events after this time.
            end_time: Filter events before this time.

        Returns:
            DwellTimeReport with aggregated statistics.
        """
        query = select(
            func.count().label("total_events"),
            func.coalesce(func.avg(GeofenceEvent.dwell_seconds), 0).label("avg_dwell"),
            func.coalesce(func.max(GeofenceEvent.dwell_seconds), 0).label("max_dwell"),
        ).where(
            GeofenceEvent.geofence_id == geofence_id,
            GeofenceEvent.dwell_seconds.is_not(None),
        )
        if start_time is not None:
            query = query.where(GeofenceEvent.entered_at >= start_time)
        if end_time is not None:
            query = query.where(GeofenceEvent.entered_at <= end_time)
        result = await self.db.execute(query)
        row = result.one()

        # Count vehicles currently inside (open entries)
        vehicles_query = select(func.count(func.distinct(GeofenceEvent.vehicle_id))).where(
            GeofenceEvent.geofence_id == geofence_id,
            GeofenceEvent.event_type == "enter",
            GeofenceEvent.exited_at.is_(None),
        )
        vehicles_result = await self.db.execute(vehicles_query)
        vehicles_inside: int = vehicles_result.scalar_one()

        return DwellTimeReport(
            geofence_id=geofence_id,
            geofence_name=geofence_name,
            total_events=int(row.total_events),
            avg_dwell_seconds=float(row.avg_dwell),
            max_dwell_seconds=int(row.max_dwell),
            vehicles_inside=vehicles_inside,
        )
