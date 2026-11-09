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
        position_type = _first_value(raw, "positionType", "position_type", "locationType", "locateType")
        position_type_text = str(position_type or "").upper()
        position_specific_time_keys = {
            "WIFI": ("wifiTime", "wifiGpsTime", "wifiLocationTime", "wifiPositionTime"),
            "LBS": ("lbsTime", "lbsGpsTime", "baseStationTime", "baseStationGpsTime", "cellTime", "cellLocationTime"),
            "BEACON": ("beaconTime", "beaconGpsTime", "beaconLocationTime"),
        }.get(position_type_text, ())
        gps_time = _first_value(
            raw,
            *position_specific_time_keys,
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
        other_position_time = _first_value(raw, "otherPosTime", "other_pos_time", "otherPositionTime")
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
        gps_time_text = _latest_time(gps_time, other_position_time) or previous.get("gps_time")
        heartbeat_time_text = str(heartbeat_time) if heartbeat_time not in (None, "", "未知") else previous.get("heartbeat_time")
        speed = _number(_first_value(raw, "speed", "speedValue", "speedStr", "velocity"))
        direction = _number(_first_value(raw, "direction", "directionValue", "directionStr", "course"))
        # The website only supplies a heading with some GPS reports. Keep the
        # last valid heading when the current WIFI/LBS report has no heading.
        if direction is not None:
            previous["direction"] = direction
        else:
            direction = previous.get("direction")
        # Match the website: only a moving device exposes a speed. A static
        # device must show "暂无速度", rather than the previous speed value.
        if str(raw.get("status", "")).upper() not in {"MOVE", "ARREARSOL"}:
            speed = None
        elif speed is not None:
            previous["speed"] = speed
        if gps_time_text is not None:
            previous["gps_time"] = gps_time_text
        if heartbeat_time_text is not None:
            previous["heartbeat_time"] = heartbeat_time_text
        battery = _number(_first_value(raw, "elecQuantity", "electricQuantity", "battery", "batteryLevel", "batteryPercent"))
        gps_signal = _number(_first_value(raw, "gPSSignal", "gpsSignal", "gps_signal", "gpsLevel", "signal"))
        total_mileage = _number(_first_value(raw, "totalKm", "totalMileage", "mileage", "mileageValue", "totalMileageKm"))
        if battery is not None:
            previous["battery"] = battery
        else:
            battery = previous.get("battery")
        if gps_signal is not None:
            previous["gps_signal"] = gps_signal
        else:
            gps_signal = previous.get("gps_signal")
        if total_mileage is not None:
            previous["total_mileage"] = total_mileage
        else:
            total_mileage = previous.get("total_mileage")
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
            "position_type": position_type,
            "speed": speed,
            "direction": direction,
            "battery": battery,
            "gps_signal": gps_signal,
            "acc": raw.get("acc") == "1",
            "power_status": raw.get("powerStatus") == "1",
            "external_voltage": _number(raw.get("voltage")),
            "total_mileage": total_mileage,
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


def _latest_time(*values: Any) -> str | None:
    """Match the website: use the newer GPS or non-GPS position time."""
    candidates = [_format_time(value) for value in values if value not in (None, "", "未知")]
    candidates = [value for value in candidates if value]
    if not candidates:
        return None
    return max(candidates, key=_time_sort_key)


def _format_time(value: Any) -> str | None:
    if value in (None, "", "未知"):
        return None
    text = str(value).strip()
    try:
        number = float(text)
        if number > 100_000_000_000:
            number /= 1000
        return datetime.fromtimestamp(number).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OverflowError, OSError):
        return text


def _time_sort_key(value: str) -> tuple[int, str]:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return (1, parsed.isoformat())
    except ValueError:
        return (0, value)


def _first_value(data: dict[str, Any], *keys: str) -> Any:
    """Read a field from the payload, including nested location/detail objects."""
    def walk(value: Any, depth: int = 0) -> Any:
        if depth > 5:
            return None
        if isinstance(value, dict):
            # Respect the caller's key order. This matters when the payload
            # contains an old generic gpsTime and a newer WIFI/LBS time.
            for wanted_key in keys:
                item = next((item for key, item in value.items() if str(key).lower() == wanted_key.lower()), None)
                if item not in (None, ""):
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

