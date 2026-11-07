"""Sensors exposed by the 途强 device."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfLength, UnitOfSpeed, UnitOfElectricPotential
from homeassistant.helpers.entity import EntityCategory

from .entity import TuqiangEntity


@dataclass(frozen=True)
class SensorSpec:
    key: str
    name: str
    icon: str
    unit: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None


SENSORS = (
    SensorSpec("battery", "电池电量", "mdi:battery", PERCENTAGE, SensorDeviceClass.BATTERY),
    SensorSpec("speed", "速度", "mdi:speedometer", UnitOfSpeed.KILOMETERS_PER_HOUR),
    SensorSpec("external_voltage", "外接电压", "mdi:car-battery", UnitOfElectricPotential.VOLT),
    SensorSpec("total_mileage", "总里程", "mdi:counter", UnitOfLength.KILOMETERS, SensorDeviceClass.DISTANCE, SensorStateClass.TOTAL_INCREASING),
    SensorSpec("gps_signal", "GPS信号", "mdi:signal-cellular-3-bar"),
    SensorSpec("address", "地址", "mdi:map-marker"),
    SensorSpec("status", "设备状态", "mdi:car-connected"),
    SensorSpec("position_type", "定位类型", "mdi:crosshairs-gps"),
    SensorSpec("gps_time", "定位时间", "mdi:clock-outline"),
    SensorSpec("heartbeat_time", "通讯时间", "mdi:access-point"),
    SensorSpec("direction", "方向", "mdi:compass-outline", "°"),
    SensorSpec("acc", "ACC", "mdi:key-variant"),
    SensorSpec("power_status", "外接电源", "mdi:power"),
)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data["tuqiangol"][entry.entry_id]
    async_add_entities([TuqiangSensor(coordinator, imei, spec) for imei in coordinator.device_imeis for spec in SENSORS])


class TuqiangSensor(TuqiangEntity, SensorEntity):
    def __init__(self, coordinator, imei, spec: SensorSpec):
        super().__init__(coordinator, imei)
        self.spec = spec
        self._attr_name = spec.name
        self._attr_icon = spec.icon
        self._attr_native_unit_of_measurement = spec.unit
        self._attr_device_class = spec.device_class
        self._attr_state_class = spec.state_class
        self._attr_entity_category = EntityCategory.DIAGNOSTIC if spec.key in {"gps_signal", "position_type", "gps_time", "heartbeat_time"} else None
        self._attr_unique_id = f"{imei}_{spec.key}"

    @property
    def native_value(self):
        value = self.data.get(self.spec.key)
        if self.spec.key in {"acc", "power_status"}:
            return "开启" if value else "关闭"
        if self.spec.key == "battery" and value is not None:
            return round(value, 1)
        if self.spec.key == "speed" and value in (None, ""):
            return "暂无速度"
        if value in (None, ""):
            return "未知" if self.spec.key in {"gps_time", "heartbeat_time", "address", "status", "position_type", "acc", "power_status"} else None
        return value

    @property
    def native_unit_of_measurement(self):
        """Hide the numeric unit while the website reports no speed."""
        if self.spec.key == "speed" and self.data.get("speed") in (None, ""):
            return None
        return self.spec.unit

