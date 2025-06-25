import logging
from typing import Any, cast

import aiohttp  # type: ignore

logger = logging.getLogger(__name__)


async def get_weather_data(lat: float, lon: float) -> dict[str, Any] | None:
    """Fetch weather data from Open-Meteo API"""
    base_url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": (
            "temperature_2m,relative_humidity_2m,apparent_temperature,"
            "precipitation_probability,weather_code,wind_speed_10m,"
            "wind_direction_10m,uv_index"
        ),
        "daily": (
            "temperature_2m_max,temperature_2m_min,"
            "precipitation_probability_max,weather_code"
        ),
        "timezone": "auto",
        "forecast_days": 7,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(base_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return cast(dict[str, Any], data)
                else:
                    logger.error(f"Open-Meteo API error: {response.status}")
                    return None
    except Exception as e:
        logger.error(f"Error fetching weather data: {e}")
        return None


async def get_uv_forecast(lat: float, lon: float) -> dict[str, Any] | None:
    """Get UV index forecast from Open-Meteo"""
    base_url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "uv_index_max",
        "timezone": "auto",
        "forecast_days": 7,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(base_url, params=params) as response:
                if response.status == 200:
                    return cast(dict[str, Any], await response.json())
                return None
    except Exception as e:
        logger.error(f"Error fetching UV data: {e}")
        return None


async def get_hourly_weather_data(lat: float, lon: float) -> dict[str, Any] | None:
    """Fetch hourly weather_code and time from Open-Meteo API for the next 24 hours."""
    base_url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "weather_code",
        "timezone": "auto",
        "forecast_days": 2,  # To ensure we get at least 24 hours
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(base_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return cast(dict[str, Any], data)
                else:
                    logger.error(f"Open-Meteo API error (hourly): {response.status}")
                    return None
    except Exception as e:
        logger.error(f"Error fetching hourly weather data: {e}")
        return None
