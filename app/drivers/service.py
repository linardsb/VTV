"""Business logic for driver management."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.drivers.exceptions import DriverAlreadyExistsError, DriverNotFoundError
from app.drivers.repository import DriverRepository
from app.drivers.schemas import (
    DriverCreate,
    DriverResponse,
    DriverUpdate,
)
from app.shared.schemas import PaginatedResponse, PaginationParams

logger = get_logger(__name__)


class DriverService:
    """Business logic for driver management."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with database session.

        Args:
            db: SQLAlchemy async session.
        """
        self.db = db
        self.repository = DriverRepository(db)

    async def get_driver(self, driver_id: int) -> DriverResponse:
        """Get a driver by ID.

        Args:
            driver_id: The driver's database ID.

        Returns:
            DriverResponse for the found driver.

        Raises:
            DriverNotFoundError: If driver does not exist.
        """
        logger.info("drivers.fetch_started", driver_id=driver_id)

        driver = await self.repository.get(driver_id)
        if not driver:
            logger.warning("drivers.fetch_failed", driver_id=driver_id, reason="not_found")
            raise DriverNotFoundError(f"Driver {driver_id} not found")

        logger.info("drivers.fetch_completed", driver_id=driver_id)
        return DriverResponse.model_validate(driver)

    async def list_drivers(
        self,
        pagination: PaginationParams,
        *,
        search: str | None = None,
        active_only: bool = True,
        status: str | None = None,
        shift: str | None = None,
    ) -> PaginatedResponse[DriverResponse]:
        """List drivers with pagination and optional filtering.

        Args:
            pagination: Page and page_size parameters.
            search: Case-insensitive search on name and employee number.
            active_only: If True, only return active drivers.
            status: Filter by driver status.
            shift: Filter by default shift.

        Returns:
            Paginated list of DriverResponse items.
        """
        logger.info(
            "drivers.list_started",
            page=pagination.page,
            page_size=pagination.page_size,
            search=search,
            status=status,
            shift=shift,
        )

        drivers = await self.repository.list(
            offset=pagination.offset,
            limit=pagination.page_size,
            active_only=active_only,
            search=search,
            status=status,
            shift=shift,
        )
        total = await self.repository.count(
            active_only=active_only,
            search=search,
            status=status,
            shift=shift,
        )

        items = [DriverResponse.model_validate(d) for d in drivers]

        logger.info("drivers.list_completed", result_count=len(items), total=total)

        return PaginatedResponse[DriverResponse](
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    async def create_driver(self, data: DriverCreate) -> DriverResponse:
        """Create a new driver.

        Args:
            data: Driver creation data.

        Returns:
            DriverResponse for the created driver.

        Raises:
            DriverAlreadyExistsError: If employee_number already exists.
        """
        logger.info("drivers.create_started", employee_number=data.employee_number)

        existing = await self.repository.get_by_employee_number(data.employee_number)
        if existing:
            logger.warning(
                "drivers.create_failed",
                employee_number=data.employee_number,
                reason="duplicate",
            )
            raise DriverAlreadyExistsError(
                f"Driver with employee_number '{data.employee_number}' already exists"
            )

        driver = await self.repository.create(data)
        logger.info(
            "drivers.create_completed",
            driver_id=driver.id,
            employee_number=driver.employee_number,
        )

        return DriverResponse.model_validate(driver)

    async def update_driver(self, driver_id: int, data: DriverUpdate) -> DriverResponse:
        """Update an existing driver.

        Args:
            driver_id: The driver's database ID.
            data: Fields to update.

        Returns:
            DriverResponse for the updated driver.

        Raises:
            DriverNotFoundError: If driver does not exist.
            DriverAlreadyExistsError: If updating employee_number to a duplicate.
        """
        logger.info("drivers.update_started", driver_id=driver_id)

        driver = await self.repository.get(driver_id)
        if not driver:
            logger.warning("drivers.update_failed", driver_id=driver_id, reason="not_found")
            raise DriverNotFoundError(f"Driver {driver_id} not found")

        # Check for duplicate employee_number if it's being changed
        update_fields = data.model_dump(exclude_unset=True)
        new_emp_num = update_fields.get("employee_number")
        if isinstance(new_emp_num, str) and new_emp_num != driver.employee_number:
            existing = await self.repository.get_by_employee_number(new_emp_num)
            if existing:
                logger.warning(
                    "drivers.update_failed",
                    driver_id=driver_id,
                    employee_number=new_emp_num,
                    reason="duplicate",
                )
                raise DriverAlreadyExistsError(
                    f"Driver with employee_number '{new_emp_num}' already exists"
                )

        driver = await self.repository.update(driver, data)
        logger.info("drivers.update_completed", driver_id=driver.id)

        return DriverResponse.model_validate(driver)

    async def delete_driver(self, driver_id: int) -> None:
        """Delete a driver by ID.

        Args:
            driver_id: The driver's database ID.

        Raises:
            DriverNotFoundError: If driver does not exist.
        """
        logger.info("drivers.delete_started", driver_id=driver_id)

        driver = await self.repository.get(driver_id)
        if not driver:
            logger.warning("drivers.delete_failed", driver_id=driver_id, reason="not_found")
            raise DriverNotFoundError(f"Driver {driver_id} not found")

        await self.repository.delete(driver)
        logger.info("drivers.delete_completed", driver_id=driver_id)

    async def get_drivers_for_availability(
        self,
        *,
        shift: str | None = None,
        route_id: str | None = None,
    ) -> list[DriverResponse]:
        """Get active drivers for agent tool availability queries.

        Args:
            shift: Optional shift filter.
            route_id: Optional route ID filter.

        Returns:
            List of DriverResponse for matching active drivers.
        """
        drivers = await self.repository.list_for_agent(shift=shift, route_id=route_id)
        return [DriverResponse.model_validate(d) for d in drivers]
