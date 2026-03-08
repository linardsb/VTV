"""Business logic for fleet device management."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.fleet.exceptions import (
    DeviceAlreadyExistsError,
    DeviceNotFoundError,
    DeviceValidationError,
)
from app.fleet.repository import FleetRepository
from app.fleet.schemas import (
    TrackedDeviceCreate,
    TrackedDeviceResponse,
    TrackedDeviceUpdate,
)
from app.shared.schemas import PaginatedResponse, PaginationParams
from app.vehicles.repository import VehicleRepository

logger = get_logger(__name__)


class FleetService:
    """Business logic for fleet device management."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with database session.

        Args:
            db: SQLAlchemy async session.
        """
        self.db = db
        self.fleet_repo = FleetRepository(db)
        self.vehicle_repo = VehicleRepository(db)

    async def get_device(self, device_id: int) -> TrackedDeviceResponse:
        """Get a tracked device by ID.

        Args:
            device_id: The device's database ID.

        Returns:
            TrackedDeviceResponse for the found device.

        Raises:
            DeviceNotFoundError: If device does not exist.
        """
        logger.info("fleet.device.fetch_started", device_id=device_id)

        device = await self.fleet_repo.get(device_id)
        if not device:
            logger.warning("fleet.device.fetch_failed", device_id=device_id, reason="not_found")
            raise DeviceNotFoundError(device_id)

        logger.info("fleet.device.fetch_completed", device_id=device_id)
        return TrackedDeviceResponse.model_validate(device)

    async def list_devices(
        self,
        pagination: PaginationParams,
        *,
        search: str | None = None,
        status: str | None = None,
        vehicle_linked: bool | None = None,
    ) -> PaginatedResponse[TrackedDeviceResponse]:
        """List tracked devices with pagination and filtering.

        Args:
            pagination: Page and page_size parameters.
            search: Case-insensitive search on imei, device_name, sim_number.
            status: Filter by device status.
            vehicle_linked: True=linked, False=unlinked, None=all.

        Returns:
            Paginated list of TrackedDeviceResponse items.
        """
        logger.info(
            "fleet.device.list_started",
            page=pagination.page,
            page_size=pagination.page_size,
            search=search,
        )

        devices = await self.fleet_repo.list(
            offset=pagination.offset,
            limit=pagination.page_size,
            search=search,
            status=status,
            vehicle_linked=vehicle_linked,
        )
        total = await self.fleet_repo.count(
            search=search,
            status=status,
            vehicle_linked=vehicle_linked,
        )

        items = [TrackedDeviceResponse.model_validate(d) for d in devices]

        logger.info("fleet.device.list_completed", result_count=len(items), total=total)

        return PaginatedResponse[TrackedDeviceResponse](
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    async def create_device(self, data: TrackedDeviceCreate) -> TrackedDeviceResponse:
        """Create a new tracked device.

        Args:
            data: Device creation data.

        Returns:
            TrackedDeviceResponse for the created device.

        Raises:
            DeviceAlreadyExistsError: If IMEI already registered.
            DeviceValidationError: If vehicle_id invalid or already linked.
        """
        logger.info("fleet.device.create_started", imei=data.imei)

        # Check IMEI uniqueness
        existing = await self.fleet_repo.get_by_imei(data.imei)
        if existing:
            logger.warning("fleet.device.create_failed", imei=data.imei, reason="duplicate_imei")
            raise DeviceAlreadyExistsError(data.imei)

        # Validate vehicle link if provided
        if data.vehicle_id is not None:
            await self._validate_vehicle_link(data.vehicle_id)

        device = await self.fleet_repo.create(data)
        logger.info(
            "fleet.device.create_completed",
            device_id=device.id,
            imei=device.imei,
        )

        return TrackedDeviceResponse.model_validate(device)

    async def update_device(
        self, device_id: int, data: TrackedDeviceUpdate
    ) -> TrackedDeviceResponse:
        """Update an existing tracked device.

        Args:
            device_id: The device's database ID.
            data: Fields to update.

        Returns:
            TrackedDeviceResponse for the updated device.

        Raises:
            DeviceNotFoundError: If device does not exist.
            DeviceAlreadyExistsError: If updating IMEI to a duplicate.
            DeviceValidationError: If vehicle_id invalid or already linked.
        """
        logger.info("fleet.device.update_started", device_id=device_id)

        device = await self.fleet_repo.get(device_id)
        if not device:
            logger.warning("fleet.device.update_failed", device_id=device_id, reason="not_found")
            raise DeviceNotFoundError(device_id)

        update_fields = data.model_dump(exclude_unset=True)

        # Check IMEI uniqueness if being changed
        new_imei = update_fields.get("imei")
        if isinstance(new_imei, str) and new_imei != device.imei:
            existing = await self.fleet_repo.get_by_imei(new_imei)
            if existing:
                logger.warning(
                    "fleet.device.update_failed",
                    device_id=device_id,
                    imei=new_imei,
                    reason="duplicate_imei",
                )
                raise DeviceAlreadyExistsError(new_imei)

        # Validate vehicle link if being changed
        new_vehicle_id = update_fields.get("vehicle_id")
        if new_vehicle_id is not None and isinstance(new_vehicle_id, int):
            await self._validate_vehicle_link(new_vehicle_id, exclude_device_id=device_id)

        device = await self.fleet_repo.update(device, data)
        logger.info("fleet.device.update_completed", device_id=device.id)

        return TrackedDeviceResponse.model_validate(device)

    async def delete_device(self, device_id: int) -> None:
        """Delete a tracked device by ID.

        Args:
            device_id: The device's database ID.

        Raises:
            DeviceNotFoundError: If device does not exist.
        """
        logger.info("fleet.device.delete_started", device_id=device_id)

        device = await self.fleet_repo.get(device_id)
        if not device:
            logger.warning("fleet.device.delete_failed", device_id=device_id, reason="not_found")
            raise DeviceNotFoundError(device_id)

        await self.fleet_repo.delete(device)
        logger.info("fleet.device.delete_completed", device_id=device_id)

    async def _validate_vehicle_link(
        self, vehicle_id: int, *, exclude_device_id: int | None = None
    ) -> None:
        """Validate that a vehicle exists and is not already linked to another device.

        Args:
            vehicle_id: The vehicle's database ID.
            exclude_device_id: Device ID to exclude from conflict check (for updates).

        Raises:
            DeviceValidationError: If vehicle not found or already linked.
        """
        vehicle = await self.vehicle_repo.get(vehicle_id)
        if vehicle is None:
            raise DeviceValidationError(f"Vehicle with id {vehicle_id} not found")

        existing_device = await self.fleet_repo.get_by_vehicle_id(vehicle_id)
        if existing_device and (
            exclude_device_id is None or existing_device.id != exclude_device_id
        ):
            raise DeviceValidationError(
                f"Vehicle {vehicle_id} is already linked to device {existing_device.id}"
            )
