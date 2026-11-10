"""Shared helpers for the Open-Meteo forecast API."""

import asyncio
import json
import math

import httpx

BASE_URL = "https://api.open-meteo.com/v1/forecast"
USER_AGENT = "WeatherStream-Education/0.3"
WEATHER_VARIABLES = "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation"
REQUEST_TIMEOUT_SECONDS = 12


def number(value, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Invalid weather number")
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError("Weather number out of range")
    return value


def hourly_series(payload, expected, error_cls=ValueError):
    try:
        block = payload["hourly"]
        units = payload["hourly_units"]
        times = block["time"]
        if not isinstance(times, list) or not times:
            raise error_cls("Empty forecast")
        if any(type(value) is not int for value in times):
            raise error_cls("Invalid forecast timestamps")
        for key, unit in expected.items():
            if units.get(key) != unit:
                raise error_cls("Unexpected forecast units")
            values = block[key]
            if not isinstance(values, list) or len(values) != len(times):
                raise error_cls("Mismatched forecast arrays")
        return times, block
    except error_cls:
        raise
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise error_cls("Invalid forecast") from exc


async def fetch_json(
    client: httpx.AsyncClient,
    params: dict,
    *,
    max_bytes: int,
    error_cls: type[ValueError],
) -> dict:
    """Fetch a bounded JSON object, translating failures to ``error_cls``."""
    try:
        body = await _read_body(client, params, max_bytes, error_cls)
    except error_cls:
        raise
    except (httpx.HTTPError, TimeoutError, ValueError, TypeError) as exc:
        raise error_cls("Provider request failed") from exc
    try:
        payload = json.loads(body)
    except (TypeError, ValueError) as exc:
        raise error_cls("Provider response is invalid") from exc
    if not isinstance(payload, dict):
        raise error_cls("Provider response is invalid")
    return payload


async def _read_body(
    client: httpx.AsyncClient,
    params: dict,
    max_bytes: int,
    error_cls: type[ValueError],
) -> bytes:
    async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
        async with client.stream(
            "GET", BASE_URL, params=params, headers={"User-Agent": USER_AGENT}
        ) as response:
            response.raise_for_status()
            body = bytearray()
            async for chunk in response.aiter_bytes():
                if len(body) + len(chunk) > max_bytes:
                    raise error_cls("Provider response is too large")
                body.extend(chunk)
    return bytes(body)
