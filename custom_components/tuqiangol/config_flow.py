"""Config flow for 途强在线."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig, SelectSelectorMode

from .api import TuqiangApi, TuqiangApiError
from .const import CONF_DEVICE_IMEIS, CONF_HIGH_PRECISION_ADDRESS, DEFAULT_SCAN_INTERVAL, DOMAIN, NAME


@config_entries.HANDLERS.register(DOMAIN)
class TuqiangConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self._devices: list[dict] = []

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input:
            await self.async_set_unique_id(user_input[CONF_USERNAME])
            self._abort_if_unique_id_configured()
            api = TuqiangApi(async_get_clientsession(self.hass), user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
            try:
                self._devices = await api.list_devices()
            except TuqiangApiError:
                errors["base"] = "cannot_connect"
            else:
                self._data = user_input
                if not self._devices:
                    errors["base"] = "no_devices"
                else:
                    return await self.async_step_devices()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )

    async def async_step_devices(self, user_input=None) -> ConfigFlowResult:
        if user_input:
            return self.async_create_entry(
                title=NAME,
                data=self._data,
                options={
                    CONF_DEVICE_IMEIS: user_input[CONF_DEVICE_IMEIS],
                    "scan_interval": user_input["scan_interval"],
                    CONF_HIGH_PRECISION_ADDRESS: user_input.get(CONF_HIGH_PRECISION_ADDRESS, False),
                },
            )
        choices = {str(device.get("imei")): f"{device.get('deviceName') or device.get('imei')} ({device.get('imei')})" for device in self._devices if device.get("imei")}
        return self.async_show_form(
            step_id="devices",
            data_schema=vol.Schema({
                vol.Required(CONF_DEVICE_IMEIS, default=list(choices)): SelectSelector(SelectSelectorConfig(options=list(choices), multiple=True, mode=SelectSelectorMode.DROPDOWN)),
                vol.Required("scan_interval", default=DEFAULT_SCAN_INTERVAL): vol.All(vol.Coerce(int), vol.Range(min=20, max=3600)),
                vol.Optional(CONF_HIGH_PRECISION_ADDRESS, default=False): bool,
            }),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return TuqiangOptionsFlow(config_entry)


class TuqiangOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self.entry = entry

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        if user_input:
            return self.async_create_entry(title="", data=user_input)
        api = TuqiangApi(async_get_clientsession(self.hass), self.entry.data[CONF_USERNAME], self.entry.data[CONF_PASSWORD])
        try:
            devices = await api.list_devices()
        except TuqiangApiError:
            devices = []
        choices = {str(device.get("imei")): f"{device.get('deviceName') or device.get('imei')} ({device.get('imei')})" for device in devices if device.get("imei")}
        current = self.entry.options.get(CONF_DEVICE_IMEIS, list(choices))
        return self.async_show_form(step_id="init", data_schema=vol.Schema({
            vol.Required(CONF_DEVICE_IMEIS, default=current): SelectSelector(SelectSelectorConfig(options=list(choices), multiple=True, mode=SelectSelectorMode.DROPDOWN)),
            vol.Required("scan_interval", default=self.entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)): vol.All(vol.Coerce(int), vol.Range(min=20, max=3600)),
            vol.Optional(CONF_HIGH_PRECISION_ADDRESS, default=self.entry.options.get(CONF_HIGH_PRECISION_ADDRESS, False)): bool,
        }))
