"""Business logic for vehicle management."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.drivers.repository import DriverRepository
from app.shared.schemas import PaginatedResponse, PaginationParams
from app.vehicles.exceptions import (
    DriverAssignmentError,
    VehicleAlreadyExistsError,
    VehicleNotFoundError,
)
from app.vehicles.repository import MaintenanceRecordRepository, VehicleRepository
from app.vehicles.schemas import (
    MaintenanceRecordCreate,
    MaintenanceRecordResponse,
    VehicleCreate,
    VehicleResponse,
    VehicleUpdate,
)

logger = get_logger(__name__)


class VehicleService:
    """Business logic for vehicle management."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with database session.

        Args:
            db: SQLAlchemy async session.
        """
        self.db = db
        self.vehicle_repo = VehicleRepository(db)
        self.maintenance_repo = MaintenanceRecordRepository(db)

    async def get_vehicle(self, vehicle_id: int) -> VehicleResponse:
        """Get a vehicle by ID.

        Args:
            vehicle_id: The vehicle's database ID.

        Returns:
            VehicleResponse for the found vehicle.

        Raises:
            VehicleNotFoundError: If vehicle does not exist.
        """
        logger.info("vehicles.fetch_started", vehicle_id=vehicle_id)

        vehicle = await self.vehicle_repo.get(vehicle_id)
        if not vehicle:
            logger.warning("vehicles.fetch_failed", vehicle_id=vehicle_id, reason="not_found")
            raise VehicleNotFoundError(vehicle_id)

        logger.info("vehicles.fetch_completed", vehicle_id=vehicle_id)
        return VehicleResponse.model_validate(vehicle)

    async def list_vehicles(
        self,
        pagination: PaginationParams,
        *,
        search: str | None = None,
        vehicle_type: str | None = None,
        status: str | None = None,
        active_only: bool = True,
    ) -> PaginatedResponse[VehicleResponse]:
        """List vehicles with pagination and optional filtering.

        Args:
            pagination: Page and page_size parameters.
            search: Case-insensitive search on fleet_number, license_plate, manufacturer, model_name.
            vehicle_type: Filter by vehicle type.
            status: Filter by vehicle status.
            active_only: If True, only return active vehicles.

        Returns:
            Paginated list of VehicleResponse items.
        """
        logger.info(
            "vehicles.list_started",
            page=pagination.page,
            page_size=pagination.page_size,
            search=search,
            vehicle_type=vehicle_type,
            status=status,
        )

        vehicles = await self.vehicle_repo.list(
            offset=pagination.offset,
            limit=pagination.page_size,
            search=search,
            vehicle_type=vehicle_type,
            status=status,
            active_only=active_only,
        )
        total = await self.vehicle_repo.count(
            search=search,
            vehicle_type=vehicle_type,
            status=status,
            active_only=active_only,
        )

        items = [VehicleResponse.model_validate(v) for v in vehicles]

        logger.info("vehicles.list_completed", result_count=len(items), total=total)

        return PaginatedResponse[VehicleResponse](
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    async def create_vehicle(self, data: VehicleCreate) -> VehicleResponse:
        """Create a new vehicle.

        Args:
            data: Vehicle creation data.

        Returns:
            VehicleResponse for the created vehicle.

        Raises:
            VehicleAlreadyExistsError: If fleet_number already exists.
        """
        logger.info("vehicles.create_started", fleet_number=data.fleet_number)

        existing = await self.vehicle_repo.get_by_fleet_number(data.fleet_number)
        if existing:
            logger.warning(
                "vehicles.create_failed",
                fleet_number=data.fleet_number,
                reason="duplicate",
            )
            raise VehicleAlreadyExistsError(data.fleet_number)

        vehicle = await self.vehicle_repo.create(data)
        logger.info(
            "vehicles.create_completed",
            vehicle_id=vehicle.id,
            fleet_number=vehicle.fleet_number,
        )

        return VehicleResponse.model_validate(vehicle)

    async def update_vehicle(self, vehicle_id: int, data: VehicleUpdate) -> VehicleResponse:
        """Update an existing vehicle.

        Args:
            vehicle_id: The vehicle's database ID.
            data: Fields to update.

        Returns:
            VehicleResponse for the updated vehicle.

        Raises:
            VehicleNotFoundError: If vehicle does not exist.
            VehicleAlreadyExistsError: If updating fleet_number to a duplicate.
            DriverAssignmentError: If assigning a non-existent or already-assigned driver.
        """
        logger.info("vehicles.update_started", vehicle_id=vehicle_id)

        vehicle = await self.vehicle_repo.get(vehicle_id)
        if not vehicle:
            logger.warning("vehicles.update_failed", vehicle_id=vehicle_id, reason="not_found")
            raise VehicleNotFoundError(vehicle_id)

        update_fields = data.model_dump(exclude_unset=True)

        # Check for duplicate fleet_number if it's being changed
        new_fleet = update_fields.get("fleet_number")
        if isinstance(new_fleet, str) and new_fleet != vehicle.fleet_number:
            existing = await self.vehicle_repo.get_by_fleet_number(new_fleet)
            if existing:
                logger.warning(
                    "vehicles.update_failed",
                    vehicle_id=vehicle_id,
                    fleet_number=new_fleet,
                    reason="duplicate",
                )
                raise VehicleAlreadyExistsError(new_fleet)

        # Validate driver assignment if being set
        new_driver_id = update_fields.get("current_driver_id")
        if new_driver_id is not None and isinstance(new_driver_id, int):
            await self._validate_driver_assignment(new_driver_id, vehicle_id)

        vehicle = await self.vehicle_repo.update(vehicle, data)
        logger.info("vehicles.update_completed", vehicle_id=vehicle.id)

        return VehicleResponse.model_validate(vehicle)

    async def delete_vehicle(self, vehicle_id: int) -> None:
        """Delete a vehicle by ID.

        Args:
            vehicle_id: The vehicle's database ID.

        Raises:
            VehicleNotFoundError: If vehicle does not exist.
        """
        logger.info("vehicles.delete_started", vehicle_id=vehicle_id)

        vehicle = await self.vehicle_repo.get(vehicle_id)
        if not vehicle:
            logger.warning("vehicles.delete_failed", vehicle_id=vehicle_id, reason="not_found")
            raise VehicleNotFoundError(vehicle_id)

        await self.vehicle_repo.delete(vehicle)
        logger.info("vehicles.delete_completed", vehicle_id=vehicle_id)

    async def assign_driver(self, vehicle_id: int, driver_id: int | None) -> VehicleResponse:
        """Assign or unassign a driver to/from a vehicle.

        Args:
            vehicle_id: The vehicle's database ID.
            driver_id: Driver ID to assign, or None to unassign.

        Returns:
            VehicleResponse for the updated vehicle.

        Raises:
            VehicleNotFoundError: If vehicle does not exist.
            DriverAssignmentError: If driver not found or already assigned.
        """
        logger.info("vehicles.driver_assign_started", vehicle_id=vehicle_id, driver_id=driver_id)

        vehicle = await self.vehicle_repo.get(vehicle_id)
        if not vehicle:
            logger.warning(
                "vehicles.driver_assign_failed", vehicle_id=vehicle_id, reason="vehicle_not_found"
            )
            raise VehicleNotFoundError(vehicle_id)

        if driver_id is not None:
            await self._validate_driver_assignment(driver_id, vehicle_id)

        vehicle.current_driver_id = driver_id
        await self.db.commit()
        await self.db.refresh(vehicle)

        logger.info("vehicles.driver_assign_completed", vehicle_id=vehicle_id, driver_id=driver_id)
        return VehicleResponse.model_validate(vehicle)

    async def add_maintenance_record(
        self, vehicle_id: int, data: MaintenanceRecordCreate
    ) -> MaintenanceRecordResponse:
        """Add a maintenance record to a vehicle.

        Args:
            vehicle_id: The vehicle's database ID.
            data: Maintenance record creation data.

        Returns:
            MaintenanceRecordResponse for the created record.

        Raises:
            VehicleNotFoundError: If vehicle does not exist.
        """
        logger.info("vehicles.maintenance_create_started", vehicle_id=vehicle_id)

        vehicle = await self.vehicle_repo.get(vehicle_id)
        if not vehicle:
            logger.warning(
                "vehicles.maintenance_create_failed",
                vehicle_id=vehicle_id,
                reason="vehicle_not_found",
            )
            raise VehicleNotFoundError(vehicle_id)

        record = await self.maintenance_repo.create(vehicle_id, data)

        # Update vehicle mileage if maintenance mileage is higher
        if data.mileage_at_service is not None and data.mileage_at_service > vehicle.mileage_km:
            vehicle.mileage_km = data.mileage_at_service

        # Update next maintenance date if provided
        if data.next_scheduled_date is not None:
            vehicle.next_maintenance_date = data.next_scheduled_date

        # Single commit for both record creation and vehicle side-effects
        await self.db.commit()
        await self.db.refresh(record)
        await self.db.refresh(vehicle)

        logger.info(
            "vehicles.maintenance_create_completed",
            vehicle_id=vehicle_id,
            record_id=record.id,
        )
        return MaintenanceRecordResponse.model_validate(record)

    async def get_maintenance_history(
        self, vehicle_id: int, pagination: PaginationParams
    ) -> PaginatedResponse[MaintenanceRecordResponse]:
        """Get maintenance history for a vehicle.

        Args:
            vehicle_id: The vehicle's database ID.
            pagination: Page and page_size parameters.

        Returns:
            Paginated list of MaintenanceRecordResponse items.

        Raises:
            VehicleNotFoundError: If vehicle does not exist.
        """
        logger.info("vehicles.maintenance_list_started", vehicle_id=vehicle_id)

        vehicle = await self.vehicle_repo.get(vehicle_id)
        if not vehicle:
            logger.warning(
                "vehicles.maintenance_list_failed",
                vehicle_id=vehicle_id,
                reason="vehicle_not_found",
            )
            raise VehicleNotFoundError(vehicle_id)

        records = await self.maintenance_repo.list_by_vehicle(
            vehicle_id, offset=pagination.offset, limit=pagination.page_size
        )
        total = await self.maintenance_repo.count_by_vehicle(vehicle_id)

        items = [MaintenanceRecordResponse.model_validate(r) for r in records]

        return PaginatedResponse[MaintenanceRecordResponse](
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    async def _validate_driver_assignment(self, driver_id: int, vehicle_id: int) -> None:
        """Validate that a driver can be assigned to a vehicle.

        Args:
            driver_id: The driver's database ID.
            vehicle_id: The vehicle's database ID (excluded from conflict check).

        Raises:
            DriverAssignmentError: If driver not found or already assigned.
        """
        driver_repo = DriverRepository(self.db)
        driver = await driver_repo.get(driver_id)
        if driver is None:
            logger.warning(
                "vehicles.driver_assign_failed",
                driver_id=driver_id,
                reason="driver_not_found",
            )
            raise DriverAssignmentError(f"Driver with id {driver_id} not found")

        # Check no other vehicle has this driver assigned
        conflicting = await self.vehicle_repo.get_vehicles_by_driver(
            driver_id, exclude_vehicle_id=vehicle_id
        )
        if conflicting:
            logger.warning(
                "vehicles.driver_assign_failed",
                driver_id=driver_id,
                conflicting_vehicle_id=conflicting[0].id,
                reason="already_assigned",
            )
            raise DriverAssignmentError(
                f"Driver {driver_id} is already assigned to vehicle {conflicting[0].id}"
            )
