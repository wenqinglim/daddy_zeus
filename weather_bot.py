import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import aiohttp
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import schedule
import threading
import time

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

class WeatherBot:
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.application = Application.builder().token(bot_token).build()
        self.db_path = "weather_bot.db"
        self.init_database()
        
    def init_database(self):
        """Initialize SQLite database for user preferences and alerts"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                location_lat REAL,
                location_lon REAL,
                location_name TEXT
            )
        ''')
        
        # Alerts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                alert_type TEXT,
                alert_time TEXT,
                conditions TEXT,
                active BOOLEAN DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Weather forecasts cache
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS forecast_cache (
                location_key TEXT PRIMARY KEY,
                forecast_data TEXT,
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()

    async def get_weather_data(self, lat: float, lon: float) -> Optional[Dict]:
        """Fetch weather data from Open-Meteo API"""
        base_url = "https://api.open-meteo.com/v1/forecast"
        
        params = {
            'latitude': lat,
            'longitude': lon,
            'current': 'temperature_2m,relative_humidity_2m,apparent_temperature,precipitation_probability,weather_code,wind_speed_10m,wind_direction_10m,uv_index',
            'daily': 'temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code',
            'timezone': 'auto',
            'forecast_days': 7
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(base_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
                    else:
                        logger.error(f"Open-Meteo API error: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error fetching weather data: {e}")
            return None

    async def get_uv_forecast(self, lat: float, lon: float) -> Optional[Dict]:
        """Get UV index forecast from Open-Meteo"""
        base_url = "https://api.open-meteo.com/v1/forecast"
        
        params = {
            'latitude': lat,
            'longitude': lon,
            'daily': 'uv_index_max',
            'timezone': 'auto',
            'forecast_days': 7
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(base_url, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    return None
        except Exception as e:
            logger.error(f"Error fetching UV data: {e}")
            return None

    def save_user_location(self, user_id: int, username: str, lat: float, lon: float, location_name: str):
        """Save user location to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username, location_lat, location_lon, location_name)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, lat, lon, location_name))
        
        conn.commit()
        conn.close()

    def get_user_location(self, user_id: int) -> Optional[tuple]:
        """Get user location from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT location_lat, location_lon, location_name FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        return result

    def save_alert(self, user_id: int, alert_type: str, alert_time: str, conditions: str):
        """Save user alert to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO alerts (user_id, alert_type, alert_time, conditions)
            VALUES (?, ?, ?, ?)
        ''', (user_id, alert_type, alert_time, conditions))
        
        conn.commit()
        conn.close()

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        """
        await update.message.reply_text(welcome_text)

    async def weather_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /weather command"""
        user_id = update.effective_user.id
        location = self.get_user_location(user_id)
        
        if not location:
            await update.message.reply_text("Please set your location first using /setlocation or share your location.")
            return
        
        lat, lon, location_name = location
        weather_data = await self.get_weather_data(lat, lon)
        uv_data = await self.get_uv_forecast(lat, lon)
        
        if not weather_data:
            await update.message.reply_text("Sorry, I couldn't fetch weather data at the moment.")
            return
        
        # Parse weather data
        try:
            current_weather = self.format_weather_message(weather_data, uv_data, location_name)
            await update.message.reply_text(current_weather, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error formatting weather message: {e}")
            await update.message.reply_text("Error processing weather data.")

    def format_weather_message(self, weather_data: Dict, uv_data: Dict, location_name: str) -> str:
        """Format weather data into a readable message"""
        try:
            # Extract current weather from Open-Meteo API response
            current = weather_data.get('current', {})
            daily = weather_data.get('daily', {})
            
            if not current or not daily:
                return "No weather data available."
            
            # Current weather
            current_temp = current.get('temperature_2m', 'N/A')
            apparent_temp = current.get('apparent_temperature', 'N/A')
            humidity = current.get('relative_humidity_2m', 'N/A')
            precip_prob = current.get('precipitation_probability', 'N/A')
            wind_speed = current.get('wind_speed_10m', 'N/A')
            wind_direction = current.get('wind_direction_10m', 'N/A')
            weather_code = current.get('weather_code', 'N/A')
            uv_index = current.get('uv_index', 'N/A')
            
            # Today's forecast
            daily_temps = daily.get('temperature_2m_max', [])
            daily_mins = daily.get('temperature_2m_min', [])
            daily_precip = daily.get('precipitation_probability_max', [])
            daily_weather = daily.get('weather_code', [])
            
            max_temp = daily_temps[0] if daily_temps else 'N/A'
            min_temp = daily_mins[0] if daily_mins else 'N/A'
            today_precip = daily_precip[0] if daily_precip else 'N/A'
            today_weather = daily_weather[0] if daily_weather else weather_code
            
            # Weather type descriptions (WMO codes)
            weather_descriptions = {
                0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
                45: "Foggy", 48: "Depositing rime fog",
                51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
                56: "Light freezing drizzle", 57: "Dense freezing drizzle",
                61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
                66: "Light freezing rain", 67: "Heavy freezing rain",
                71: "Slight snow fall", 73: "Moderate snow fall", 75: "Heavy snow fall",
                77: "Snow grains",
                80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
                85: "Slight snow showers", 86: "Heavy snow showers",
                95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail"
            }
            
            weather_desc = weather_descriptions.get(today_weather, "Unknown")
            
            # Wind direction
            wind_dirs = {
                0: "N", 45: "NE", 90: "E", 135: "SE", 180: "S", 225: "SW", 270: "W", 315: "NW"
            }
            wind_dir = wind_dirs.get(round(wind_direction / 45) * 45, "N/A") if isinstance(wind_direction, (int, float)) else "N/A"
            
            message = f"""
🌤️ <b>Weather for {location_name}</b>

🌡️ <b>Current:</b> {current_temp}°C (feels like {apparent_temp}°C)
🌡️ <b>Today:</b> {max_temp}°C / {min_temp}°C
☁️ <b>Conditions:</b> {weather_desc}
🌧️ <b>Rain Chance:</b> {today_precip}%
💨 <b>Wind:</b> {wind_speed} km/h {wind_dir}
💧 <b>Humidity:</b> {humidity}%
☀️ <b>UV Index:</b> {uv_index}

<b>Recommendations:</b>
{self.get_recommendations(today_weather, today_precip, uv_index)}
            """
            
            return message.strip()
            
        except Exception as e:
            logger.error(f"Error in format_weather_message: {e}")
            return "Error formatting weather data."

    def get_recommendations(self, weather_code: int, precip_prob: int, uv_index) -> str:
        """Generate weather-based recommendations"""
        recommendations = []
        
        # Rain recommendations
        if isinstance(precip_prob, (int, float)) and precip_prob > 60:
            recommendations.append("🌂 Take an umbrella")
        elif isinstance(precip_prob, (int, float)) and precip_prob > 30:
            recommendations.append("🌂 Consider bringing an umbrella")
        
        # UV recommendations
        if isinstance(uv_index, (int, float)):
            if uv_index >= 6:
                recommendations.append("🧴 Apply sunscreen (high UV)")
            elif uv_index >= 3:
                recommendations.append("🧴 Consider sunscreen (moderate UV)")
        
        # Weather-specific recommendations
        if weather_code in [45, 48]:  # Fog
            recommendations.append("🚗 Drive carefully - reduced visibility")
        elif weather_code in [65, 67, 82]:  # Heavy rain
            recommendations.append("🏠 Stay indoors if possible")
        elif weather_code in [95, 96, 99]:  # Thunderstorm
            recommendations.append("⚡ Avoid outdoor activities")
        elif weather_code in [71, 73, 75, 85, 86]:  # Snow
            recommendations.append("❄️ Dress warmly and watch for ice")
        
        return "\n".join(recommendations) if recommendations else "No special recommendations"

    async def setlocation_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /setlocation command"""
        keyboard = [
            [InlineKeyboardButton("Share Location", callback_data="share_location")],
            [InlineKeyboardButton("Enter Manually", callback_data="manual_location")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "How would you like to set your location?",
            reply_markup=reply_markup
        )

    async def alerts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /alerts command"""
        keyboard = [
            [InlineKeyboardButton("☀️ Sunny Weather Alert", callback_data="alert_sunny")],
            [InlineKeyboardButton("🌂 Rain/UV Reminder", callback_data="alert_rain_uv")],
            [InlineKeyboardButton("📅 Forecast Change Alert", callback_data="alert_forecast_change")],
            [InlineKeyboardButton("📋 View My Alerts", callback_data="view_alerts")],
            [InlineKeyboardButton("🗑️ Delete Alerts", callback_data="delete_alerts")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🔔 Weather Alerts\n\nWhat would you like to do?",
            reply_markup=reply_markup
        )

    async def handle_location(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle location sharing"""
        if update.message.location:
            user_id = update.effective_user.id
            username = update.effective_user.username or "Unknown"
            lat = update.message.location.latitude
            lon = update.message.location.longitude
            
            # Get location name from coordinates (reverse geocoding)
            location_name = f"Lat: {lat:.2f}, Lon: {lon:.2f}"
            
            self.save_user_location(user_id, username, lat, lon, location_name)
            
            await update.message.reply_text(
                f"📍 Location saved: {location_name}\n\n"
                "Use /weather to get your local weather forecast!"
            )

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        if data == "share_location":
            await query.edit_message_text(
                "Please share your location using the 📎 attachment button and selecting 'Location'."
            )
        
        elif data == "manual_location":
            await query.edit_message_text(
                "Please send me your location in the format:\n"
                "/location <latitude> <longitude>\n\n"
                "Example: /location 51.5074 -0.1278"
            )
        
        elif data == "alert_sunny":
            await self.setup_sunny_alert(query, user_id)
        
        elif data == "alert_rain_uv":
            await self.setup_rain_uv_alert(query, user_id)
        
        elif data == "alert_forecast_change":
            await self.setup_forecast_change_alert(query, user_id)
        
        elif data == "view_alerts":
            await self.show_user_alerts(query, user_id)
        
        elif data == "delete_alerts":
            await self.delete_user_alerts(query, user_id)

    async def setup_sunny_alert(self, query, user_id: int):
        """Setup sunny weather alert"""
        location = self.get_user_location(user_id)
        if not location:
            await query.edit_message_text("Please set your location first using /setlocation")
            return
        
        # Save alert
        self.save_alert(user_id, "sunny", "09:00", "clear_sky")
        
        await query.edit_message_text(
            "☀️ Sunny weather alert set!\n\n"
            "You'll receive a notification at 9:00 AM when sunny weather is forecast for today."
        )

    async def setup_rain_uv_alert(self, query, user_id: int):
        """Setup rain/UV reminder alert"""
        location = self.get_user_location(user_id)
        if not location:
            await query.edit_message_text("Please set your location first using /setlocation")
            return
        
        # Save alert
        self.save_alert(user_id, "rain_uv", "08:00", "rain_or_high_uv")
        
        await query.edit_message_text(
            "🌂☀️ Rain/UV reminder set!\n\n"
            "You'll receive daily reminders at 8:00 AM about bringing an umbrella or applying sunscreen based on the forecast."
        )

    async def setup_forecast_change_alert(self, query, user_id: int):
        """Setup forecast change alert"""
        location = self.get_user_location(user_id)
        if not location:
            await query.edit_message_text("Please set your location first using /setlocation")
            return
        
        # Save alert
        self.save_alert(user_id, "forecast_change", "18:00", "any_change")
        
        await query.edit_message_text(
            "📅 Forecast change alert set!\n\n"
            "You'll be notified at 6:00 PM about any significant changes to tomorrow's weather forecast."
        )

    async def show_user_alerts(self, query, user_id: int):
        """Show user's active alerts"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT alert_type, alert_time, conditions FROM alerts 
            WHERE user_id = ? AND active = 1
        ''', (user_id,))
        
        alerts = cursor.fetchall()
        conn.close()
        
        if not alerts:
            await query.edit_message_text("You don't have any active alerts.")
            return
        
        alert_text = "📋 Your Active Alerts:\n\n"
        for alert_type, alert_time, conditions in alerts:
            if alert_type == "sunny":
                alert_text += f"☀️ Sunny weather alert at {alert_time}\n"
            elif alert_type == "rain_uv":
                alert_text += f"🌂☀️ Rain/UV reminder at {alert_time}\n"
            elif alert_type == "forecast_change":
                alert_text += f"📅 Forecast change alert at {alert_time}\n"
        
        await query.edit_message_text(alert_text)

    async def delete_user_alerts(self, query, user_id: int):
        """Delete all user alerts"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('UPDATE alerts SET active = 0 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        await query.edit_message_text("🗑️ All your alerts have been deleted.")

    async def location_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /location command with coordinates"""
        if len(context.args) != 2:
            await update.message.reply_text(
                "Please provide latitude and longitude:\n"
                "/location <latitude> <longitude>\n\n"
                "Example: /location 51.5074 -0.1278"
            )
            return
        
        try:
            lat = float(context.args[0])
            lon = float(context.args[1])
            
            user_id = update.effective_user.id
            username = update.effective_user.username or "Unknown"
            location_name = f"Lat: {lat:.2f}, Lon: {lon:.2f}"
            
            self.save_user_location(user_id, username, lat, lon, location_name)
            
            await update.message.reply_text(
                f"📍 Location saved: {location_name}\n\n"
                "Use /weather to get your local weather forecast!"
            )
            
        except ValueError:
            await update.message.reply_text("Invalid coordinates. Please provide valid numbers.")

    def check_and_send_alerts(self):
        """Check and send scheduled alerts"""
        current_time = datetime.now().strftime("%H:%M")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT u.user_id, u.location_lat, u.location_lon, u.location_name, a.alert_type
            FROM users u
            JOIN alerts a ON u.user_id = a.user_id
            WHERE a.alert_time = ? AND a.active = 1
        ''', (current_time,))
        
        alerts_to_send = cursor.fetchall()
        conn.close()
        
        for user_id, lat, lon, location_name, alert_type in alerts_to_send:
            asyncio.create_task(self.send_alert(user_id, lat, lon, location_name, alert_type))

    async def send_alert(self, user_id: int, lat: float, lon: float, location_name: str, alert_type: str):
        """Send alert to user"""
        try:
            weather_data = await self.get_weather_data(lat, lon)
            uv_data = await self.get_uv_forecast(lat, lon)
            
            if not weather_data:
                return
            
            message = ""
            
            if alert_type == "sunny":
                message = self.generate_sunny_alert(weather_data, location_name)
            elif alert_type == "rain_uv":
                message = self.generate_rain_uv_alert(weather_data, uv_data, location_name)
            elif alert_type == "forecast_change":
                message = self.generate_forecast_change_alert(weather_data, location_name)
            
            if message:
                await self.application.bot.send_message(chat_id=user_id, text=message, parse_mode='HTML')
                
        except Exception as e:
            logger.error(f"Error sending alert to user {user_id}: {e}")

    def generate_sunny_alert(self, weather_data: Dict, location_name: str) -> str:
        """Generate sunny weather alert message"""
        try:
            daily = weather_data.get('daily', {})
            if not daily:
                return ""
            
            weather_codes = daily.get('weather_code', [])
            if not weather_codes:
                return ""
            
            today_weather = weather_codes[0]
            
            # Check if it's sunny (codes 0, 1, 2 are clear/partly cloudy)
            if today_weather in [0, 1, 2]:
                return f"☀️ <b>Sunny Weather Alert!</b>\n\nIt's going to be sunny in {location_name} today! Perfect weather to get outside and enjoy the sunshine! 🌞"
            
            return ""
            
        except Exception:
            return ""

    def generate_rain_uv_alert(self, weather_data: Dict, uv_data: Dict, location_name: str) -> str:
        """Generate rain/UV reminder alert"""
        try:
            current = weather_data.get('current', {})
            daily = weather_data.get('daily', {})
            
            if not current or not daily:
                return ""
            
            precip_prob = current.get('precipitation_probability', 0)
            uv_index = current.get('uv_index', 0)
            
            alerts = []
            
            if precip_prob > 60:
                alerts.append("🌂 High chance of rain - bring an umbrella!")
            elif precip_prob > 30:
                alerts.append("🌂 Possible rain - consider bringing an umbrella")
            
            if uv_index >= 6:
                alerts.append("🧴 High UV index - apply sunscreen!")
            elif uv_index >= 3:
                alerts.append("🧴 Moderate UV - consider sunscreen")
            
            if alerts:
                message = f"🌤️ <b>Daily Weather Reminder for {location_name}</b>\n\n"
                message += "\n".join(alerts)
                return message
            
            return ""
            
        except Exception:
            return ""

    def generate_forecast_change_alert(self, weather_data: Dict, location_name: str) -> str:
        """Generate forecast change alert (simplified version)"""
        # This would require storing previous forecasts and comparing
        # For now, return a simple message
        return f"📅 <b>Forecast Update for {location_name}</b>\n\nTomorrow's weather forecast has been updated. Check /weather for the latest information."

    def run_scheduler(self):
        """Run the scheduler in a separate thread"""
        schedule.every().minute.do(self.check_and_send_alerts)
        
        while True:
            schedule.run_pending()
            time.sleep(60)

    def setup_handlers(self):
        """Setup bot command and message handlers"""
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("weather", self.weather_command))
        self.application.add_handler(CommandHandler("setlocation", self.setlocation_command))
        self.application.add_handler(CommandHandler("location", self.location_command))
        self.application.add_handler(CommandHandler("alerts", self.alerts_command))
        
        # Callback handlers
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Location handler
        self.application.add_handler(MessageHandler(filters.LOCATION, self.handle_location))

    def run(self):
        """Start the bot"""
        self.setup_handlers()
        
        # Start scheduler in background thread
        scheduler_thread = threading.Thread(target=self.run_scheduler, daemon=True)
        scheduler_thread.start()
        
        # Start the bot
        logger.info("Starting Weather Bot...")
        self.application.run_polling()

# Configuration
BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"  # Get from @BotFather

if __name__ == "__main__":
    if BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        print("Please set your bot token!")
        print("1. Get bot token from @BotFather on Telegram")
        print("2. Update the BOT_TOKEN variable in the script")
    else:
        bot = WeatherBot(BOT_TOKEN)
        bot.run()
