import logging
from typing import Any

import aiohttp  # type: ignore
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update  # type: ignore
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.utils.db import get_user_location, save_user_location
from bot.utils.weather import get_uv_forecast, get_weather_data

logger = logging.getLogger(__name__)


def register_command_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("weather", weather_command))
    app.add_handler(CommandHandler("setlocation", setlocation_command))
    app.add_handler(CommandHandler("location", location_command))
    app.add_handler(CommandHandler("alerts", alerts_command))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command"""
    welcome_text = """
🌤️ Welcome to the UK Weather Bot!

I can help you with:
• Live weather data from the Met Office
• Sunscreen/umbrella reminders based on UV and rain forecasts
• Location-based weather stats
• Sunny weather alerts
• Weather forecast change notifications

To get started, please share your location or use /setlocation to set your location manually.

Commands:
/weather - Get current weather
/setlocation - Set your location
/alerts - Manage your weather alerts
/help - Show this help message
        """  # noqa: E501
    if update.message is not None:
        await update.message.reply_text(welcome_text)


async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /weather command"""
    if update.effective_user is None:
        return
    user_id = update.effective_user.id
    location = get_user_location(user_id)
    if not location:
        if update.message is not None:
            await update.message.reply_text(
                "Please set your location first using /setlocation or "
                "share your location."
            )
        return
    lat, lon, location_name = location
    weather_data = await get_weather_data(lat, lon)
    uv_data = await get_uv_forecast(lat, lon)
    if not weather_data:
        if update.message is not None:
            await update.message.reply_text(
                "Sorry, I couldn't fetch weather data at the moment."
            )
        return
    try:
        current_weather = format_weather_message(weather_data, uv_data, location_name)
        if update.message is not None:
            await update.message.reply_text(current_weather, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error formatting weather message: {e}")
        if update.message is not None:
            await update.message.reply_text("Error processing weather data.")


def format_weather_message(
    weather_data: dict[str, Any], uv_data: dict[str, Any] | None, location_name: str
) -> str:
    try:
        current = weather_data.get("current", {})
        daily = weather_data.get("daily", {})
        if not current or not daily:
            return "No weather data available."
        current_temp = current.get("temperature_2m", "N/A")
        apparent_temp = current.get("apparent_temperature", "N/A")
        humidity = current.get("relative_humidity_2m", "N/A")
        wind_speed = current.get("wind_speed_10m", "N/A")
        wind_direction = current.get("wind_direction_10m", "N/A")
        weather_code = current.get("weather_code", "N/A")
        uv_index = current.get("uv_index", "N/A")
        daily_temps = daily.get("temperature_2m_max", []) or []
        daily_mins = daily.get("temperature_2m_min", []) or []
        daily_precip = daily.get("precipitation_probability_max", []) or []
        daily_weather = daily.get("weather_code", []) or []
        max_temp = daily_temps[0] if daily_temps else "N/A"
        min_temp = daily_mins[0] if daily_mins else "N/A"
        today_precip = daily_precip[0] if daily_precip else "N/A"
        today_weather = daily_weather[0] if daily_weather else weather_code
        weather_descriptions = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Foggy",
            48: "Depositing rime fog",
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            56: "Light freezing drizzle",
            57: "Dense freezing drizzle",
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            66: "Light freezing rain",
            67: "Heavy freezing rain",
            71: "Slight snow fall",
            73: "Moderate snow fall",
            75: "Heavy snow fall",
            77: "Snow grains",
            80: "Slight rain showers",
            81: "Moderate rain showers",
            82: "Violent rain showers",
            85: "Slight snow showers",
            86: "Heavy snow showers",
            95: "Thunderstorm",
            96: "Thunderstorm with slight hail",
            99: "Thunderstorm with heavy hail",
        }
        weather_desc = weather_descriptions.get(today_weather, "Unknown")
        wind_dirs = {
            0: "N",
            45: "NE",
            90: "E",
            135: "SE",
            180: "S",
            225: "SW",
            270: "W",
            315: "NW",
        }
        wind_dir = (
            wind_dirs.get(round(wind_direction / 45) * 45, "N/A")
            if isinstance(wind_direction, int | float)
            else "N/A"
        )
        # Ensure today_weather and today_precip are int if possible
        try:
            today_weather_int = int(today_weather)
        except Exception:
            today_weather_int = -1
        try:
            today_precip_int = int(today_precip)
        except Exception:
            today_precip_int = 0
        try:
            uv_index_int = int(uv_index)
        except Exception:
            uv_index_int = 0
        message = (
            f"🌤️ <b>Weather for {location_name}</b>\n\n"
            f"🌡️ <b>Current:</b> {current_temp}°C (feels like {apparent_temp}°C)\n"
            f"🌡️ <b>Today:</b> {max_temp}°C / {min_temp}°C\n"
            f"☁️ <b>Conditions:</b> {weather_desc}\n"
            f"🌧️ <b>Rain Chance:</b> {today_precip}%\n"
            f"💨 <b>Wind:</b> {wind_speed} km/h {wind_dir}\n"
            f"💧 <b>Humidity:</b> {humidity}%\n"
            f"☀️ <b>UV Index:</b> {uv_index}\n\n"
            f"<b>Recommendations:</b>\n"
            f"{get_recommendations(today_weather_int, today_precip_int, uv_index_int)}"
        )
        return message.strip()
    except Exception as e:
        logger.error(f"Error in format_weather_message: {e}")
        return "Error formatting weather data."


def get_recommendations(weather_code: int, precip_prob: int, uv_index: int) -> str:
    recommendations = []
    if isinstance(precip_prob, int | float) and precip_prob > 60:
        recommendations.append("🌂 Take an umbrella")
    elif isinstance(precip_prob, int | float) and precip_prob > 30:
        recommendations.append("🌂 Consider bringing an umbrella")
    if isinstance(uv_index, int | float):
        if uv_index >= 6:
            recommendations.append("🧴 Apply sunscreen (high UV)")
        elif uv_index >= 3:
            recommendations.append("🧴 Consider sunscreen (moderate UV)")
    if weather_code in [45, 48]:
        recommendations.append("🚗 Drive carefully - reduced visibility")
    elif weather_code in [65, 67, 82]:
        recommendations.append("🏠 Stay indoors if possible")
    elif weather_code in [95, 96, 99]:
        recommendations.append("⚡ Avoid outdoor activities")
    elif weather_code in [71, 73, 75, 85, 86]:
        recommendations.append("❄️ Dress warmly and watch for ice")
    return (
        "\n".join(recommendations) if recommendations else "No special recommendations"
    )


async def setlocation_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if update.message is None:
        return
    keyboard = [
        [InlineKeyboardButton("Share Location", callback_data="share_location")],
        [InlineKeyboardButton("Enter Manually", callback_data="manual_location")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "How would you like to set your location?", reply_markup=reply_markup
    )


async def alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    keyboard = [
        [InlineKeyboardButton("☀️ Sunny Weather Alert", callback_data="alert_sunny")],
        [InlineKeyboardButton("🌂 Rain/UV Reminder", callback_data="alert_rain_uv")],
        [
            InlineKeyboardButton(
                "📅 Forecast Change Alert", callback_data="alert_forecast_change"
            )
        ],
        [InlineKeyboardButton("📋 View My Alerts", callback_data="view_alerts")],
        [InlineKeyboardButton("🗑️ Delete Alerts", callback_data="delete_alerts")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🔔 Weather Alerts\n\nWhat would you like to do?", reply_markup=reply_markup
    )


async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.message.location is None:
        return
    if update.effective_user is None:
        return
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    lat = update.message.location.latitude
    lon = update.message.location.longitude
    location_name = f"Lat: {lat:.2f}, Lon: {lon:.2f}"
    save_user_location(user_id, username, lat, lon, location_name)
    await update.message.reply_text(
        f"""📍 Location saved: {location_name}\n
        \nUse /weather to get your local weather forecast!"""
    )


async def geocode_city(city_name: str) -> tuple[float, float, str] | None:
    """
    Resolve a city name to (lat, lon, display_name) using Open-Meteo geocoding API.
    """
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": city_name, "count": 1, "language": "en"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results")
                    if results and len(results) > 0:
                        r = results[0]
                        lat = r["latitude"]
                        lon = r["longitude"]
                        name = r.get("name", city_name)
                        country = r.get("country", "")
                        display_name = f"{name}, {country}" if country else name
                        return float(lat), float(lon), display_name
    except Exception as e:
        logger.error(f"Geocoding error: {e}")
    return None


# TODO: test location command
async def location_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    if not context.args:
        await update.message.reply_text(
            """
            Please provide a city name or latitude and longitude:\n
            /location <city name>\n
            /location <latitude> <longitude>
            \n\nExamples: /location London or /location 51.5074 -0.1278"""
        )
        return
    # Try to parse as lat/lon first
    if len(context.args) == 2:
        try:
            lat = float(context.args[0])
            lon = float(context.args[1])
            if update.effective_user is None:
                return
            user_id = update.effective_user.id
            username = update.effective_user.username or "Unknown"
            location_name = f"Lat: {lat:.2f}, Lon: {lon:.2f}"
            save_user_location(user_id, username, lat, lon, location_name)
            await update.message.reply_text(
                f"""📍 Location saved: {location_name}\n
                \nUse /weather to get your local weather forecast!"""
            )
            return
        except ValueError:
            pass  # Fall through to city name
    # Otherwise, treat as city name
    city_name = " ".join(context.args)
    geocode = await geocode_city(city_name)
    if geocode is None:
        await update.message.reply_text(
            f"""Sorry, I couldn't find a location for '{city_name}'.
            Please try another city or use coordinates."""
        )
        return
    lat, lon, display_name = geocode
    if update.effective_user is None:
        return
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    save_user_location(user_id, username, lat, lon, display_name)
    await update.message.reply_text(
        f"""📍 Location saved: {display_name}\n\n
        Use /weather to get your local weather forecast!"""
    )
