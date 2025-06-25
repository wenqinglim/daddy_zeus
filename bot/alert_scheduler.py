import asyncio
import logging
import sqlite3
from datetime import UTC, datetime, timedelta

from telegram import Bot  # type: ignore

from bot.config import BOT_TOKEN
from bot.utils.db import DB_PATH, get_sunny_alert_users
from bot.utils.weather import get_hourly_weather_data

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger("alert_scheduler")

# Table to track sent sunny alerts (user_id, alert_time, sent_at)
SENT_ALERTS_TABLE = "sent_sunny_alerts"


def ensure_sent_alerts_table(db_path: str = DB_PATH) -> None:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {SENT_ALERTS_TABLE} (
                user_id INTEGER,
                alert_time TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, alert_time)
            )
            """
        )
        conn.commit()


def has_sent_alert(user_id: int, alert_time: str, db_path: str = DB_PATH) -> bool:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT 1 FROM {SENT_ALERTS_TABLE} WHERE user_id = ? AND alert_time = ?",
            (user_id, alert_time),
        )
        return cursor.fetchone() is not None


def mark_alert_sent(user_id: int, alert_time: str, db_path: str = DB_PATH) -> None:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""INSERT OR IGNORE INTO {SENT_ALERTS_TABLE} (user_id, alert_time) VALUES (?, ?)""",  # noqa: E501
            (user_id, alert_time),
        )
        conn.commit()


def has_sent_alert_in_past_n_hours(
    user_id: int, alert_time: str, n: int = 2, db_path: str = DB_PATH
) -> bool:
    """Check if an alert has been sent for this user and alert_time
    in the past n hours."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT sent_at FROM {SENT_ALERTS_TABLE} WHERE user_id = ? AND alert_time = ?",  # noqa: E501
            (user_id, alert_time),
        )
        row = cursor.fetchone()
        if row is None:
            return False
        sent_at_str = row[0]
        try:
            sent_at = datetime.fromisoformat(sent_at_str)
        except Exception:
            return False
        now = datetime.now(UTC)
        if sent_at.tzinfo is None:
            sent_at = sent_at.replace(tzinfo=UTC)
        return (now - sent_at).total_seconds() < n * 60 * 60


async def send_sunny_alert(
    bot: Bot, user_id: int, location_name: str, alert_time: str
) -> None:
    try:
        message = (
            f"☀️ Sunny weather is forecast for {location_name} at {alert_time}!\n"
            f"This is your reminder 2 hours before sunny weather."
        )
        await bot.send_message(chat_id=user_id, text=message)
        logger.info(f"Sent sunny alert to user {user_id} for {alert_time}")
    except Exception as e:
        logger.error(f"Failed to send alert to user {user_id}: {e}")


async def process_sunny_alerts() -> None:
    ensure_sent_alerts_table()
    bot = Bot(BOT_TOKEN)
    users = get_sunny_alert_users()
    now = datetime.now(UTC)
    for user_id, lat, lon, location_name in users:
        weather = await get_hourly_weather_data(lat, lon)
        if not weather or "hourly" not in weather:
            logger.warning(f"No hourly weather for user {user_id}")
            continue
        times = weather["hourly"].get("time", [])
        codes = weather["hourly"].get("weather_code", [])
        for t_str, code in zip(times, codes, strict=False):
            try:
                t = datetime.fromisoformat(t_str)
                if t.tzinfo is None:
                    t = t.replace(tzinfo=UTC)
            except Exception:
                continue
            # Only consider times in the future
            if t <= now:
                continue
            # If clear sky (code 0), and 2 hour before is within the next 2 hours
            if code == 0:
                alert_time = t - timedelta(hours=2)
                # If alert_time is within the next 2 hours
                if 0 <= (alert_time - now).total_seconds() <= 7200:
                    alert_time_str = t.strftime("%Y-%m-%d %H:00")
                    if not has_sent_alert_in_past_n_hours(user_id, alert_time_str):
                        await send_sunny_alert(
                            bot, user_id, location_name, t.strftime("%H:%M")
                        )
                        mark_alert_sent(user_id, alert_time_str)


def main() -> None:
    asyncio.run(process_sunny_alerts())


if __name__ == "__main__":
    main()
