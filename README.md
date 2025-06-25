# daddy_zeus
Telegram bot for weather alerts

# Setup Instructions

## 1. Prerequisites
- [pyenv](https://github.com/pyenv/pyenv) (the setup script will install it if missing)
- [curl](https://curl.se/) (for downloading pyenv)

## 2. Environment Setup (Recommended)

Run the provided setup script to automatically:
- Install pyenv (if not present)
- Install Python 3.11.x
- Create a new virtual environment
- Install [uv](https://github.com/astral-sh/uv) (if not present)
- Install all dependencies from `pyproject.toml`

```bash
bash setup.sh
```

After setup, activate your environment with:
```bash
pyenv activate daddy_zeus_env
```

## 3. Configuration

Edit the bot file and replace:
- `YOUR_TELEGRAM_BOT_TOKEN` with your actual bot token

## 4. Running the Bot

```bash
uv run weather_bot.py
```

# Telegram Weather Bot Features

### ✅ Live Weather Data
- Fetches real-time weather data from Open-Meteo
- Shows temperature, conditions, rain probability, wind, humidity
- Displays UV index forecast

### ✅ Sunscreen/Umbrella Reminders
- Daily alerts at 8:00 AM
- Recommends umbrella based on rain probability
- Recommends sunscreen based on UV index

### ✅ Location-Based Weather
- Users can share location or set coordinates manually
- Stores user preferences in SQLite database
- Shows weather stats for user's location

### ✅ Sunny Weather Alerts
- Configurable alerts for sunny weather
- Morning notifications when sunny weather is forecast
- Based on WMO weather codes

### ✅ Forecast Change Notifications
- Evening alerts about forecast changes
- Notifies users about updates to tomorrow's weather
- Helps users stay informed about changing conditions

## Bot Commands

- `/start` - Welcome message and instructions
- `/weather` - Get current weather for your location
- `/setlocation` - Set your location (GPS or manual)
- `/location <lat> <lon>` - Set location with coordinates
- `/alerts` - Manage weather alerts
