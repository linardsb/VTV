"""Data access layer for vehicle management."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.scope import RequestScope
from app.core.exceptions import RBACConfigurationError
from app.core.logging import get_logger
from app.shared.utils import escape_like
from app.vehicles.models import MaintenanceRecord, Vehicle, VehicleRouteQualification
from app.vehicles.schemas import MaintenanceRecordCreate, VehicleCreate, VehicleUpdate

logger = get_logger(__name__)


class VehicleRepository:
    """Database operations for vehicles."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with an async database session.

        Args:
            db: SQLAlchemy async session.
        """
        self.db = db

    def _apply_scope(
        self, query: Select[tuple[Vehicle]], scope: RequestScope
    ) -> Select[tuple[Vehicle]]:
        if scope.is_unrestricted:
            return query
        subq = (
            select(VehicleRouteQualification.vehicle_id)
            .where(VehicleRouteQualification.route_id.in_(scope.route_ids or frozenset()))
            .scalar_subquery()
        )
        return query.where(Vehicle.id.in_(subq))

    async def get(self, vehicle_id: int, *, scope: RequestScope | None = None) -> Vehicle | None:
        """Get a vehicle by primary key ID.

        Args:
            vehicle_id: The vehicle's database ID.
            scope: Optional RBAC scope to filter by.

        Returns:
            Vehicle instance or None if not found.
        """
        query = select(Vehicle).where(Vehicle.id == vehicle_id)
        if scope is not None and not scope.is_unrestricted:
            subq = (
                select(VehicleRouteQualification.vehicle_id)
                .where(
                    VehicleRouteQualification.vehicle_id == vehicle_id,
                    VehicleRouteQualification.route_id.in_(scope.route_ids or frozenset()),
                )
                .scalar_subquery()
            )
            query = query.where(Vehicle.id.in_(subq))
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_fleet_number(self, fleet_number: str) -> Vehicle | None:
        """Get a vehicle by fleet number.

        Args:
            fleet_number: The unique fleet identifier.

        Returns:
            Vehicle instance or None if not found.
        """
        result = await self.db.execute(select(Vehicle).where(Vehicle.fleet_number == fleet_number))
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        search: str | None = None,
        vehicle_type: str | None = None,
        status: str | None = None,
        active_only: bool = True,
        scope: RequestScope | None = None,
    ) -> list[Vehicle]:
        """List vehicles with pagination and filtering.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to return.
            search: Case-insensitive search on fleet_number, license_plate, manufacturer, model_name.
            vehicle_type: Filter by vehicle type.
            status: Filter by vehicle status.
            active_only: If True, only return active vehicles.
            scope: RBAC scope for filtering. Required (fail-closed).

        Returns:
            List of Vehicle instances.

        Raises:
            RBACConfigurationError: If scope is None (programming error).
        """
        if scope is None:
            raise RBACConfigurationError("RequestScope required for vehicle list queries")
        query = select(Vehicle)
        query = self._apply_scope(query, scope)
        if active_only:
            query = query.where(Vehicle.is_active.is_(True))
        if search:
            pattern = f"%{escape_like(search)}%"
            query = query.where(
                or_(
                    Vehicle.fleet_number.ilike(pattern),
                    Vehicle.license_plate.ilike(pattern),
                    Vehicle.manufacturer.ilike(pattern),
                    Vehicle.model_name.ilike(pattern),
                )
            )
        if vehicle_type is not None:
            query = query.where(Vehicle.vehicle_type == vehicle_type)
        if status is not None:
            query = query.where(Vehicle.status == status)
        query = query.order_by(Vehicle.fleet_number).offset(offset).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count(
        self,
        *,
        search: str | None = None,
        vehicle_type: str | None = None,
        status: str | None = None,
        active_only: bool = True,
        scope: RequestScope | None = None,
    ) -> int:
        """Count vehicles matching the given filters.

        Args:
            search: Case-insensitive search on fleet_number, license_plate, manufacturer, model_name.
            vehicle_type: Filter by vehicle type.
            status: Filter by vehicle status.
            active_only: If True, only count active vehicles.
            scope: RBAC scope for filtering. Required (fail-closed).

        Returns:
            Total number of matching vehicles.

        Raises:
            RBACConfigurationError: If scope is None (programming error).
        """
        if scope is None:
            raise RBACConfigurationError("RequestScope required for vehicle count queries")
        query = select(func.count()).select_from(Vehicle)
        if not scope.is_unrestricted:
            subq = (
                select(VehicleRouteQualification.vehicle_id)
                .where(VehicleRouteQualification.route_id.in_(scope.route_ids or frozenset()))
                .scalar_subquery()
            )
            query = query.where(Vehicle.id.in_(subq))
        if active_only:
            query = query.where(Vehicle.is_active.is_(True))
        if search:
            pattern = f"%{escape_like(search)}%"
            query = query.where(
                or_(
                    Vehicle.fleet_number.ilike(pattern),
                    Vehicle.license_plate.ilike(pattern),
                    Vehicle.manufacturer.ilike(pattern),
                    Vehicle.model_name.ilike(pattern),
                )
            )
        if vehicle_type is not None:
            query = query.where(Vehicle.vehicle_type == vehicle_type)
        if status is not None:
            query = query.where(Vehicle.status == status)
        result = await self.db.execute(query)
        return result.scalar_one()

    async def create(self, data: VehicleCreate) -> Vehicle:
        """Create a new vehicle record.

        Args:
            data: Vehicle creation data.

        Returns:
            The newly created Vehicle instance.
        """
        vehicle = Vehicle(**data.model_dump())
        self.db.add(vehicle)
        await self.db.commit()
        await self.db.refresh(vehicle)
        return vehicle

    async def update(self, vehicle: Vehicle, data: VehicleUpdate) -> Vehicle:
        """Update an existing vehicle record.

        Args:
            vehicle: The vehicle instance to update.
            data: Fields to update (only set fields are applied).

        Returns:
            The updated Vehicle instance.
        """
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(vehicle, field, value)
        await self.db.commit()
        await self.db.refresh(vehicle)
        return vehicle

    async def delete(self, vehicle: Vehicle) -> None:
        """Delete a vehicle record.

        Args:
            vehicle: The vehicle instance to delete.
        """
        await self.db.delete(vehicle)
        await self.db.commit()

    async def get_vehicles_by_driver(
        self, driver_id: int, *, exclude_vehicle_id: int | None = None
    ) -> Sequence[Vehicle]:
        """Get active vehicles assigned to a specific driver.

        Args:
            driver_id: The driver's database ID.
            exclude_vehicle_id: Optional vehicle ID to exclude from results.

        Returns:
            List of Vehicle instances assigned to the driver.
        """
        query = (
            select(Vehicle)
            .where(Vehicle.current_driver_id == driver_id)
            .where(Vehicle.is_active.is_(True))
        )
        if exclude_vehicle_id is not None:
            query = query.where(Vehicle.id != exclude_vehicle_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())


class MaintenanceRecordRepository:
    """Database operations for maintenance records."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with an async database session.

        Args:
            db: SQLAlchemy async session.
        """
        self.db = db

    async def get(self, record_id: int) -> MaintenanceRecord | None:
        """Get a maintenance record by primary key ID.

        Args:
            record_id: The record's database ID.

        Returns:
            MaintenanceRecord instance or None if not found.
        """
        result = await self.db.execute(
            select(MaintenanceRecord).where(MaintenanceRecord.id == record_id)
        )
        return result.scalar_one_or_none()

    async def list_by_vehicle(
        self, vehicle_id: int, *, offset: int = 0, limit: int = 20
    ) -> list[MaintenanceRecord]:
        """List maintenance records for a vehicle ordered by date descending.

        Args:
            vehicle_id: The vehicle's database ID.
            offset: Number of records to skip.
            limit: Maximum records to return.

        Returns:
            List of MaintenanceRecord instances.
        """
        query = (
            select(MaintenanceRecord)
            .where(MaintenanceRecord.vehicle_id == vehicle_id)
            .order_by(MaintenanceRecord.performed_date.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count_by_vehicle(self, vehicle_id: int) -> int:
        """Count maintenance records for a vehicle.

        Args:
            vehicle_id: The vehicle's database ID.

        Returns:
            Total number of maintenance records.
        """
        query = (
            select(func.count())
            .select_from(MaintenanceRecord)
            .where(MaintenanceRecord.vehicle_id == vehicle_id)
        )
        result = await self.db.execute(query)
        return result.scalar_one()

    async def create(self, vehicle_id: int, data: MaintenanceRecordCreate) -> MaintenanceRecord:
        """Create a new maintenance record.

        Does NOT commit — the caller is responsible for committing the
        transaction so that related vehicle side-effects (mileage update,
        next maintenance date) are atomic with the record creation.

        Args:
            vehicle_id: The vehicle's database ID.
            data: Maintenance record creation data.

        Returns:
            The newly created MaintenanceRecord instance (pending flush).
        """
        record = MaintenanceRecord(vehicle_id=vehicle_id, **data.model_dump())
        self.db.add(record)
        await self.db.flush()
        return record
