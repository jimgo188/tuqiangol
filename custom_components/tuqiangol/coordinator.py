"""Coordinator and normalized device data."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from aiohttp import ClientSession
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TuqiangApi, TuqiangApiError
from .const import CONF_DEVICE_IMEIS, CONF_HIGH_PRECISION_ADDRESS, DOMAIN

_LOGGER = logging.getLogger(__name__)


class TuqiangCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, update_interval) -> None:
        self.entry = entry
        self._session: ClientSession = async_get_clientsession(hass)
        self.api = TuqiangApi(self._session, entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
        self._address_cache: dict[str, str] = {}
        self._last_motion_data: dict[str, dict[str, Any]] = {}
        self._device_imeis = entry.options.get(CONF_DEVICE_IMEIS, entry.data.get(CONF_DEVICE_IMEIS, []))
        self._high_precision_address = entry.options.get(CONF_HIGH_PRECISION_ADDRESS, False)
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    @property
    def device_imeis(self) -> list[str]:
        """Return configured devices, even while the first refresh is unavailable."""
        return [str(imei) for imei in self._device_imeis]

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            result: dict[str, dict[str, Any]] = {}
            for imei in self._device_imeis:
                raw = await self.api.get_device(str(imei))
                if not raw:
                    continue
                result[str(imei)] = await self._normalize(raw)
            return result
        except TuqiangApiError as err:
            raise UpdateFailed(str(err)) from err

    async def _normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        imei = str(raw.get("imei", ""))
        try:
            latitude = float(raw.get("lat"))
            longitude = float(raw.get("lng"))
        except (TypeError, ValueError):
            latitude = longitude = None
        address = self._address_cache.get(imei, "未知")
        last_coords = getattr(self, "_last_coords", {}).get(imei)
        if latitude is not None and longitude is not None and (imei not in self._address_cache or (latitude, longitude) != last_coords):
            try:
                address = await self.api.get_address(
                    latitude,
                    longitude,
                    imei=imei,
                    high_precision=self._high_precision_address,
                )
                self._address_cache[imei] = address
            except TuqiangApiError:
                _LOGGER.debug("无法获取 %s 地址", imei, exc_info=True)
        if not hasattr(self, "_last_coords"):
            self._last_coords = {}
        self._last_coords[imei] = (latitude, longitude)
        gps_time = _first_value(
            raw,
            "gpsTime",
            "gps_time",
            "gpsTimeStr",
            "lastGpsTime",
            "lastGpsTimeStr",
            "gpsDate",
            "gpsDateStr",
            "locationTime",
            "locationTimeStr",
            "lastLocationTime",
            "lastLocationTimeStr",
            "positionTime",
            "positionTimeStr",
            "lastPositionTime",
            "lastPositionTimeStr",
            "locateTime",
            "locateTimeStr",
            "positionDate",
        )
        heartbeat_time = _first_value(
            raw,
            "hbTime",
            "heartbeatTime",
            "heartbeat_time",
            "hb_time",
            "communicationTime",
            "communicationTimeStr",
            "communicateTime",
            "communicateTimeStr",
            "commTime",
            "lastCommunicationTime",
            "lastCommunicateTime",
            "uploadTime",
            "lastUploadTime",
            "onlineTime",
            "lastOnlineTime",
            "reportTime",
        )
        previous = self._last_motion_data.setdefault(imei, {})
        gps_time_text = str(gps_time) if gps_time not in (None, "", "未知") else previous.get("gps_time")
        heartbeat_time_text = str(heartbeat_time) if heartbeat_time not in (None, "", "未知") else previous.get("heartbeat_time")
        speed = _number(_first_value(raw, "speed", "speedValue", "speedStr", "velocity"))
        direction = _number(_first_value(raw, "direction", "directionValue", "directionStr", "course"))
        if speed is None:
            speed = previous.get("speed")
        else:
            previous["speed"] = speed
        if direction is None:
            direction = previous.get("direction")
        else:
            previous["direction"] = direction
        if gps_time_text is not None:
            previous["gps_time"] = gps_time_text
        if heartbeat_time_text is not None:
            previous["heartbeat_time"] = heartbeat_time_text
        return {
            "imei": imei,
            "name": raw.get("deviceName") or imei,
            "latitude": latitude,
            "longitude": longitude,
            "address": address,
            "available": raw.get("status") not in {"OFFLINE", "SLEEP"},
            "status": raw.get("statusStr") or raw.get("statusAbstract") or raw.get("status"),
            "gps_time": gps_time_text,
            "heartbeat_time": heartbeat_time_text,
            "position_type": raw.get("positionType"),
            "speed": speed,
            "direction": direction,
            "battery": _number(raw.get("elecQuantity")),
            "gps_signal": _number(raw.get("gPSSignal")),
            "acc": raw.get("acc") == "1",
            "power_status": raw.get("powerStatus") == "1",
            "external_voltage": _number(raw.get("voltage")),
            "total_mileage": _number(raw.get("totalKm")),
            "raw": raw,
        }


def _number(value: Any) -> float | None:
    if value in (None, "", "暂无速度", "未知"):
        return None
    try:
        text = str(value).strip().replace("%", "").replace("V", "").replace("Km", "")
        return float(text)
    except (TypeError, ValueError):
        return None


def _first_value(data: dict[str, Any], *keys: str) -> Any:
    """Read a field from the payload, including nested location/detail objects."""
    wanted = {key.lower() for key in keys}

    def walk(value: Any, depth: int = 0) -> Any:
        if depth > 5:
            return None
        if isinstance(value, dict):
            for key, item in value.items():
                if str(key).lower() in wanted and item not in (None, ""):
                    if isinstance(item, dict):
                        return item.get("value") or item.get("time") or item.get("text")
                    return item
            for item in value.values():
                found = walk(item, depth + 1)
                if found not in (None, ""):
                    return found
        elif isinstance(value, list):
            for item in value:
                found = walk(item, depth + 1)
                if found not in (None, ""):
                    return found
        return None

    value = walk(data)
    if value not in (None, ""):
        return value
    return None

