"""Async client for the 途强在线 web APIs."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
import logging
from typing import Any

from aiohttp import ClientSession

from .const import DEFAULT_HOST

_LOGGER = logging.getLogger(__name__)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"


class TuqiangApiError(Exception):
    """Raised when the platform returns an unusable response."""


class TuqiangApi:
    def __init__(self, session: ClientSession, username: str, password: str, host: str = DEFAULT_HOST) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._host = host.rstrip("/")
        self._user_id: str | None = None
        self._user_type: str | None = None

    @staticmethod
    def _encode_password(password: str) -> str:
        return "|".join(str(ord(char)) for char in password)

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        request_timeout = kwargs.pop("request_timeout", 20)
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{self._host}/console?viewFlag=2",
        }
        try:
            async with self._session.request(method, f"{self._host}{path}", headers=headers, timeout=request_timeout, **kwargs) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (OSError, asyncio.TimeoutError, ValueError) as err:
            raise TuqiangApiError(f"途强接口请求失败: {path}") from err
        if not isinstance(payload, dict):
            raise TuqiangApiError(f"途强接口返回格式错误: {path}")
        return payload

    async def login(self) -> None:
        result = await self._request(
            "POST",
            "/api/regdc",
            data={"ver": "1", "method": "login", "account": self._username, "password": self._encode_password(self._password), "language": "zh"},
        )
        if result.get("code") != 0:
            raise TuqiangApiError(result.get("msg", "途强登录失败"))
        provider = await self._request("POST", "/customer/getProviderList")
        user = provider.get("data", {}).get("user", {})
        self._user_id = str(user.get("userId", ""))
        self._user_type = str(user.get("type", ""))
        if not self._user_id:
            raise TuqiangApiError("途强登录成功但没有取得用户编号")

    async def ensure_login(self) -> None:
        if self._user_id is None or self._user_type is None:
            await self.login()

    async def list_devices(self) -> list[dict[str, Any]]:
        await self.ensure_login()
        result = await self._request("POST", "/device/list", data={"dateType": "activation", "equipment.userId": self._user_id})
        return result.get("data", {}).get("result", []) or []

    async def get_device(self, imei: str) -> dict[str, Any]:
        await self.ensure_login()
        result = await self._request(
            "POST",
            "/console/refresh",
            data={"choiceUserId": self._user_id, "normalImeis": imei, "userType": self._user_type, "followImeis": "", "userId": self._user_id, "stock": "2"},
        )
        devices = result.get("data", {}).get("normalList", []) or []
        for device in devices:
            if str(device.get("imei", "")) == str(imei):
                return device
        return devices[0] if devices else {}

    async def get_address(
        self,
        latitude: float,
        longitude: float,
        imei: str = "",
        high_precision: bool = False,
    ) -> str:
        await self.ensure_login()
        result = await self._request(
            "GET",
            "/getAddress",
            params={
                # The website uses this spelling (Hight) for the option.
                "isHightPrecision": "true" if high_precision else "false",
                "lat": latitude,
                "lng": longitude,
                "mapType": "baiduMap",
                "poiList": "",
                "imei": imei,
            },
        )
        return str(result.get("msg") or "未知")

    async def send_immediate_location(self, imei: str) -> dict[str, Any]:
        await self.ensure_login()
        return await self._request(
            "POST",
            "/device/sendIns",
            request_timeout=60,
            data={
                "imei": imei,
                "orderContent": "GPSON#",
                # 857 is the current typeId shown by the logged-in console
                # for the website's "立即定位" command.
                "instructionId": "857",
                "instructionName": "立即定位",
                "instructionPwd": "",
                "isUsePwd": "0",
                "isOffLine": "1",
                "formatStatus": "",
            },
        )
