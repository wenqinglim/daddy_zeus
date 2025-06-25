import logging
import sqlite3  # type: ignore
from typing import Any

logger = logging.getLogger(__name__)

DB_PATH = "weather_bot.db"


def init_database(db_path: str = DB_PATH) -> None:
    """Initialize SQLite database for user preferences and alerts."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                location_lat REAL,
                location_lon REAL,
                location_name TEXT
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                alert_type TEXT,
                alert_time TEXT,
                conditions TEXT,
                active BOOLEAN DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS forecast_cache (
                location_key TEXT PRIMARY KEY,
                forecast_data TEXT,
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        conn.commit()


def save_user_location(
    user_id: int,
    username: str,
    lat: float,
    lon: float,
    location_name: str,
    db_path: str = DB_PATH,
) -> None:
    """Save user location to database."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO users (
                user_id, username, location_lat, location_lon, location_name
            )
            VALUES (?, ?, ?, ?, ?)
        """,
            (user_id, username, lat, lon, location_name),
        )
        conn.commit()


def get_user_location(
    user_id: int, db_path: str = DB_PATH
) -> tuple[float, float, str] | None:
    """Get user location from database."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT location_lat, location_lon, location_name FROM users "
            "WHERE user_id = ?",
            (user_id,),
        )
        result = cursor.fetchone()
        if result is None:
            return None
        lat, lon, location_name = result
        return (float(lat), float(lon), str(location_name))


def save_alert(
    user_id: int,
    alert_type: str,
    alert_time: str,
    conditions: str,
    db_path: str = DB_PATH,
) -> None:
    """Save user alert to database."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO alerts (user_id, alert_type, alert_time, conditions)
            VALUES (?, ?, ?, ?)
        """,
            (user_id, alert_type, alert_time, conditions),
        )
        conn.commit()


def get_user_alerts(user_id: int, db_path: str = DB_PATH) -> list[tuple[str, str, str]]:
    """Get all active alerts for a user."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT alert_type, alert_time, conditions FROM alerts
            WHERE user_id = ? AND active = 1
        """,
            (user_id,),
        )
        return cursor.fetchall()


def deactivate_user_alerts(user_id: int, db_path: str = DB_PATH) -> None:
    """Deactivate all alerts for a user."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE alerts SET active = 0 WHERE user_id = ?", (user_id,))
        conn.commit()


def get_alerts_to_send(
    current_time: str, db_path: str = DB_PATH
) -> list[tuple[Any, ...]]:
    """Get all alerts to send at the current time."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT DISTINCT u.user_id, u.location_lat, u.location_lon,
                u.location_name, a.alert_type
            FROM users u
            JOIN alerts a ON u.user_id = a.user_id
            WHERE a.alert_time = ? AND a.active = 1
        """,
            (current_time,),
        )
        return cursor.fetchall()


def get_sunny_alert_users(
    db_path: str = DB_PATH,
) -> list[tuple[int, float, float, str]]:
    """Get all users with an active sunny alert."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT DISTINCT u.user_id, u.location_lat, u.location_lon, u.location_name
            FROM users u
            JOIN alerts a ON u.user_id = a.user_id
            WHERE a.alert_type = 'sunny' AND a.active = 1
            """
        )
        return cursor.fetchall()
