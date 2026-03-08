"""Data access layer for fleet device management."""

from __future__ import annotations

import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.fleet.models import TrackedDevice
from app.fleet.schemas import TrackedDeviceCreate, TrackedDeviceUpdate
from app.shared.utils import escape_like


class FleetRepository:
    """Database operations for tracked devices."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with an async database session.

        Args:
            db: SQLAlchemy async session.
        """
        self.db = db

    async def get(self, device_id: int) -> TrackedDevice | None:
        """Get a tracked device by primary key ID.

        Args:
            device_id: The device's database ID.

        Returns:
            TrackedDevice instance or None if not found.
        """
        result = await self.db.execute(select(TrackedDevice).where(TrackedDevice.id == device_id))
        return result.scalar_one_or_none()

    async def get_by_imei(self, imei: str) -> TrackedDevice | None:
        """Get a tracked device by IMEI number.

        Args:
            imei: The 15-digit IMEI number.

        Returns:
            TrackedDevice instance or None if not found.
        """
        result = await self.db.execute(select(TrackedDevice).where(TrackedDevice.imei == imei))
        return result.scalar_one_or_none()

    async def get_by_traccar_id(self, traccar_device_id: int) -> TrackedDevice | None:
        """Get a tracked device by Traccar's internal device ID.

        Args:
            traccar_device_id: Traccar's internal device ID.

        Returns:
            TrackedDevice instance or None if not found.
        """
        result = await self.db.execute(
            select(TrackedDevice).where(TrackedDevice.traccar_device_id == traccar_device_id)
        )
        return result.scalar_one_or_none()

    async def get_by_vehicle_id(self, vehicle_id: int) -> TrackedDevice | None:
        """Get a tracked device linked to a specific vehicle.

        Args:
            vehicle_id: The vehicle's database ID.

        Returns:
            TrackedDevice instance or None if not found.
        """
        result = await self.db.execute(
            select(TrackedDevice).where(TrackedDevice.vehicle_id == vehicle_id)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        search: str | None = None,
        status: str | None = None,
        vehicle_linked: bool | None = None,
    ) -> list[TrackedDevice]:
        """List tracked devices with pagination and filtering.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to return.
            search: Case-insensitive search on imei, device_name, sim_number.
            status: Filter by device status.
            vehicle_linked: True=linked, False=unlinked, None=all.

        Returns:
            List of TrackedDevice instances.
        """
        query = select(TrackedDevice)
        if search:
            pattern = f"%{escape_like(search)}%"
            query = query.where(
                or_(
                    TrackedDevice.imei.ilike(pattern),
                    TrackedDevice.device_name.ilike(pattern),
                    TrackedDevice.sim_number.ilike(pattern),
                )
            )
        if status is not None:
            query = query.where(TrackedDevice.status == status)
        if vehicle_linked is True:
            query = query.where(TrackedDevice.vehicle_id.is_not(None))
        elif vehicle_linked is False:
            query = query.where(TrackedDevice.vehicle_id.is_(None))
        query = query.order_by(TrackedDevice.id).offset(offset).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count(
        self,
        *,
        search: str | None = None,
        status: str | None = None,
        vehicle_linked: bool | None = None,
    ) -> int:
        """Count tracked devices matching the given filters.

        Args:
            search: Case-insensitive search on imei, device_name, sim_number.
            status: Filter by device status.
            vehicle_linked: True=linked, False=unlinked, None=all.

        Returns:
            Total number of matching devices.
        """
        query = select(func.count()).select_from(TrackedDevice)
        if search:
            pattern = f"%{escape_like(search)}%"
            query = query.where(
                or_(
                    TrackedDevice.imei.ilike(pattern),
                    TrackedDevice.device_name.ilike(pattern),
                    TrackedDevice.sim_number.ilike(pattern),
                )
            )
        if status is not None:
            query = query.where(TrackedDevice.status == status)
        if vehicle_linked is True:
            query = query.where(TrackedDevice.vehicle_id.is_not(None))
        elif vehicle_linked is False:
            query = query.where(TrackedDevice.vehicle_id.is_(None))
        result = await self.db.execute(query)
        return result.scalar_one()

    async def create(self, data: TrackedDeviceCreate) -> TrackedDevice:
        """Create a new tracked device record.

        Args:
            data: Device creation data.

        Returns:
            The newly created TrackedDevice instance.
        """
        device = TrackedDevice(**data.model_dump())
        self.db.add(device)
        await self.db.commit()
        await self.db.refresh(device)
        return device

    async def update(self, device: TrackedDevice, data: TrackedDeviceUpdate) -> TrackedDevice:
        """Update an existing tracked device record.

        Args:
            device: The device instance to update.
            data: Fields to update (only set fields are applied).

        Returns:
            The updated TrackedDevice instance.
        """
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(device, field, value)
        await self.db.commit()
        await self.db.refresh(device)
        return device

    async def delete(self, device: TrackedDevice) -> None:
        """Delete a tracked device record.

        Args:
            device: The device instance to delete.
        """
        await self.db.delete(device)
        await self.db.commit()

    async def update_last_seen(self, device: TrackedDevice, seen_at: datetime.datetime) -> None:
        """Update device last_seen_at timestamp.

        Lightweight update for webhook telemetry processing.

        Args:
            device: The device instance to update.
            seen_at: The timestamp when the device was last seen.
        """
        device.last_seen_at = seen_at
        await self.db.commit()
