"""Data access layer for driver management."""

from __future__ import annotations

import builtins

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.drivers.models import Driver
from app.drivers.schemas import DriverCreate, DriverUpdate


class DriverRepository:
    """Database operations for drivers."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with an async database session.

        Args:
            db: SQLAlchemy async session.
        """
        self.db = db

    async def get(self, driver_id: int) -> Driver | None:
        """Get a driver by primary key ID.

        Args:
            driver_id: The driver's database ID.

        Returns:
            Driver instance or None if not found.
        """
        result = await self.db.execute(select(Driver).where(Driver.id == driver_id))
        return result.scalar_one_or_none()

    async def get_by_employee_number(self, employee_number: str) -> Driver | None:
        """Get a driver by employee number.

        Args:
            employee_number: The unique employee identifier.

        Returns:
            Driver instance or None if not found.
        """
        result = await self.db.execute(
            select(Driver).where(Driver.employee_number == employee_number)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
        active_only: bool = True,
        search: str | None = None,
        status: str | None = None,
        shift: str | None = None,
    ) -> list[Driver]:
        """List drivers with pagination and filtering.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to return.
            active_only: If True, only return active drivers.
            search: Case-insensitive search on first_name, last_name, employee_number.
            status: Filter by driver status.
            shift: Filter by default shift.

        Returns:
            List of Driver instances.
        """
        query = select(Driver)
        if active_only:
            query = query.where(Driver.is_active.is_(True))
        if search:
            pattern = f"%{search}%"
            query = query.where(
                or_(
                    Driver.first_name.ilike(pattern),
                    Driver.last_name.ilike(pattern),
                    Driver.employee_number.ilike(pattern),
                )
            )
        if status is not None:
            query = query.where(Driver.status == status)
        if shift is not None:
            query = query.where(Driver.default_shift == shift)
        query = query.order_by(Driver.last_name, Driver.first_name).offset(offset).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count(
        self,
        *,
        active_only: bool = True,
        search: str | None = None,
        status: str | None = None,
        shift: str | None = None,
    ) -> int:
        """Count drivers matching the given filters.

        Args:
            active_only: If True, only count active drivers.
            search: Case-insensitive search on first_name, last_name, employee_number.
            status: Filter by driver status.
            shift: Filter by default shift.

        Returns:
            Total number of matching drivers.
        """
        query = select(func.count()).select_from(Driver)
        if active_only:
            query = query.where(Driver.is_active.is_(True))
        if search:
            pattern = f"%{search}%"
            query = query.where(
                or_(
                    Driver.first_name.ilike(pattern),
                    Driver.last_name.ilike(pattern),
                    Driver.employee_number.ilike(pattern),
                )
            )
        if status is not None:
            query = query.where(Driver.status == status)
        if shift is not None:
            query = query.where(Driver.default_shift == shift)
        result = await self.db.execute(query)
        return result.scalar_one()

    async def create(self, data: DriverCreate) -> Driver:
        """Create a new driver record.

        Args:
            data: Driver creation data.

        Returns:
            The newly created Driver instance.
        """
        driver = Driver(**data.model_dump())
        self.db.add(driver)
        await self.db.commit()
        await self.db.refresh(driver)
        return driver

    async def update(self, driver: Driver, data: DriverUpdate) -> Driver:
        """Update an existing driver record.

        Args:
            driver: The driver instance to update.
            data: Fields to update (only set fields are applied).

        Returns:
            The updated Driver instance.
        """
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(driver, field, value)
        await self.db.commit()
        await self.db.refresh(driver)
        return driver

    async def delete(self, driver: Driver) -> None:
        """Delete a driver record.

        Args:
            driver: The driver instance to delete.
        """
        await self.db.delete(driver)
        await self.db.commit()

    async def list_for_agent(
        self,
        *,
        shift: str | None = None,
        route_id: str | None = None,
    ) -> builtins.list[Driver]:
        """List active drivers for agent tool queries.

        Args:
            shift: Optional shift filter.
            route_id: Optional route ID filter (checks qualified_route_ids).

        Returns:
            List of active Driver instances matching filters.
        """
        query = select(Driver).where(Driver.is_active.is_(True))
        if shift is not None:
            query = query.where(Driver.default_shift == shift)
        if route_id is not None:
            query = query.where(Driver.qualified_route_ids.contains(route_id))
        query = query.order_by(Driver.last_name, Driver.first_name)
        result = await self.db.execute(query)
        return list(result.scalars().all())
