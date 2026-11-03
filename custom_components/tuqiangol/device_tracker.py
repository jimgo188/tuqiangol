"""GPS device tracker entities."""

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity

from .entity import TuqiangEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data["tuqiangol"][entry.entry_id]
    async_add_entities([TuqiangTracker(coordinator, imei) for imei in coordinator.device_imeis])


class TuqiangTracker(TuqiangEntity, TrackerEntity):
    _attr_name = "位置"
    _attr_source_type = SourceType.GPS

    @property
    def latitude(self):
        return self.data.get("latitude")

    @property
    def longitude(self):
        return self.data.get("longitude")

    def _handle_coordinator_update(self) -> None:
        """Expose the platform address without overriding deprecated APIs."""
        self._attr_location_name = self.data.get("address")
        super()._handle_coordinator_update()

    @property
    def available(self):
        return bool(self.data)

    @property
    def extra_state_attributes(self):
        return {
            "address": self.data.get("address"),
            "gps_time": self.data.get("gps_time"),
            "heartbeat_time": self.data.get("heartbeat_time"),
            "position_type": self.data.get("position_type"),
        }
