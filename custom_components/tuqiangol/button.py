"""Immediate location button."""

from homeassistant.components.button import ButtonEntity

from .entity import TuqiangEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data["tuqiangol"][entry.entry_id]
    async_add_entities([TuqiangLocateButton(coordinator, imei) for imei in coordinator.device_imeis])


class TuqiangLocateButton(TuqiangEntity, ButtonEntity):
    _attr_name = "立即定位"
    _attr_icon = "mdi:crosshairs"

    async def async_press(self) -> None:
        await self.coordinator.api.send_immediate_location(self.imei)
        await self.coordinator.async_request_refresh()
