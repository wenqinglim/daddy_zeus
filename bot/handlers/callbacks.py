import logging
from typing import Any

from telegram import Update  # type: ignore
from telegram.ext import Application, CallbackQueryHandler, ContextTypes  # type: ignore

from bot.utils.db import (
    deactivate_user_alerts,
    get_user_alerts,
    get_user_location,
    save_alert,
)

logger = logging.getLogger(__name__)


def register_callback_handlers(app: Application) -> None:
    app.add_handler(CallbackQueryHandler(button_callback))


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.callback_query is None:
        return
    query = update.callback_query
    await query.answer()
    if query.data is None or query.from_user is None:
        return
    data = query.data
    user_id = query.from_user.id
    if data == "share_location":
        await query.edit_message_text(
            "Please share your location using the "
            "📎 attachment button and selecting 'Location'."
        )
    elif data == "manual_location":
        await query.edit_message_text(
            "Please send me your location in the format:"
            "\n/location <latitude> <longitude>"
            "\n\nExample: /location 51.5074 -0.1278"
        )
    elif data == "alert_sunny":
        await setup_sunny_alert(query, user_id)
    elif data == "alert_rain_uv":
        await setup_rain_uv_alert(query, user_id)
    elif data == "alert_forecast_change":
        await setup_forecast_change_alert(query, user_id)
    elif data == "view_alerts":
        await show_user_alerts(query, user_id)
    elif data == "delete_alerts":
        await delete_user_alerts(query, user_id)


async def setup_sunny_alert(query: Any, user_id: int) -> None:
    location = get_user_location(user_id)
    if not location:
        await query.edit_message_text(
            "Please set your location first using /setlocation"
        )
        return
    save_alert(user_id, "sunny", "next_sunny_hour", "clear_sky")
    await query.edit_message_text(
        """
        ☀️ Sunny weather alert set!\n\n
        You'll receive a notification 2 hours before any sunny weather is forecast in your area.
        """  # noqa: E501
    )


async def setup_rain_uv_alert(query: Any, user_id: int) -> None:
    location = get_user_location(user_id)
    if not location:
        await query.edit_message_text(
            "Please set your location first using /setlocation"
        )
        return
    save_alert(user_id, "rain_uv", "08:00", "rain_or_high_uv")
    await query.edit_message_text(
        "🌂☀️ Rain/UV reminder set!\n\n"
        "You'll receive daily reminders at 8:00 AM about bringing an umbrella or "
        "applying sunscreen based on the forecast."
    )


async def setup_forecast_change_alert(query: Any, user_id: int) -> None:
    location = get_user_location(user_id)
    if not location:
        await query.edit_message_text(
            "Please set your location first using /setlocation"
        )
        return
    save_alert(user_id, "forecast_change", "18:00", "any_change")
    await query.edit_message_text(
        "📅 Forecast change alert set!\n\n"
        "You'll be notified at 6:00 PM about any significant changes to "
        "tomorrow's weather forecast."
    )


async def show_user_alerts(query: Any, user_id: int) -> None:
    alerts = get_user_alerts(user_id)
    if not alerts:
        await query.edit_message_text("You don't have any active alerts.")
        return
    alert_text = "📋 Your Active Alerts:\n\n"
    for alert_type, alert_time, _ in alerts:
        if alert_type == "sunny":
            alert_text += "☀️ Sunny weather alert (2 hours before forecast)\n"
        elif alert_type == "rain_uv":
            alert_text += f"🌂☀️ Rain/UV reminder at {alert_time}\n"
        elif alert_type == "forecast_change":
            alert_text += f"📅 Forecast change alert at {alert_time}\n"
    await query.edit_message_text(alert_text)


async def delete_user_alerts(query: Any, user_id: int) -> None:
    deactivate_user_alerts(user_id)
    await query.edit_message_text("🗑️ All your alerts have been deleted.")
