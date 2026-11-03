"""Common entities."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TuqiangCoordinator


class TuqiangEntity(CoordinatorEntity[TuqiangCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: TuqiangCoordinator, imei: str) -> None:
        super().__init__(coordinator)
        self.imei = imei
        self._attr_unique_id = f"{imei}_{self.__class__.__name__}".lower()

    @property
    def device_info(self) -> DeviceInfo:
        data = self.coordinator.data.get(self.imei, {})
        return DeviceInfo(identifiers={(DOMAIN, self.imei)}, name=data.get("name", self.imei), manufacturer="途强在线", model="GPS")

    @property
    def data(self) -> dict:
        return self.coordinator.data.get(self.imei, {})
