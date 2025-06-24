# daddy_zeus
Telegram bot for weather alerts

# Telegram Weather Bot Setup

## Requirements (requirements.txt)

```
python-telegram-bot==20.7
aiohttp==3.9.1
schedule==1.2.0
sqlite3
```

## Setup Instructions

### 1. Get Required API Keys

#### Telegram Bot Token
1. Open Telegram and search for `@BotFather`
2. Send `/newbot` command
3. Follow the instructions to create your bot
4. Copy the bot token provided

#### Met Office API Key
1. Visit [Met Office API Developer Portal](https://developer.metoffice.gov.uk/)
2. Register for a free account
3. Subscribe to the required APIs:
   - **Weather Forecast API** (for daily forecasts)
   - **UV Index API** (for UV forecasts)
4. Copy your API key from the dashboard

### 2. Installation

```bash
# Install required packages
pip install -r requirements.txt

# Or install individually:
pip install python-telegram-bot aiohttp schedule
```

### 3. Configuration

Edit the bot file and replace:
- `YOUR_TELEGRAM_BOT_TOKEN` with your actual bot token
- `YOUR_MET_OFFICE_API_KEY` with your Met Office API key

### 4. Running the Bot

```bash
python weather_bot.py
```

## Features Implemented

### ✅ Live Weather Data
- Fetches real-time weather data from UK Met Office
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
- Based on Met Office weather codes

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
