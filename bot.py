```python
# bot.py
import os
import threading
import requests
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# Загрузим переменные окружения
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_KEY   = os.getenv("API_KEY")

# Supabase REST endpoint Arcaiuz
BASE_URL = "https://vextbzatpprnksyutbcp.supabase.co/rest/v1/growagarden_stock"
HEADERS = {
    "apikey": API_KEY,
    "Authorization": f"Bearer {API_KEY}"
}

# Эмодзи по категориям
CATEGORY_EMOJI = {
    "seeds_stock":    "🌱",
    "cosmetic_stock": "💎",
    "gear_stock":     "🧰",
    "egg_stock":      "🥚",
    "weather":        "☁️"
}

# Эмодзи по названиям предметов
ITEM_EMOJI = {
    # Seeds
    "Feijoa": "🥝", "Kiwi": "🥝", "Avocado": "🥑", "Sugar Apple": "🍏", "Tomato": "🍅",
    "Bell Pepper": "🌶️", "Pitcher Plant": "🌱", "Prickly Pear": "🌵", "Cauliflower": "🥦",
    "Blueberry": "🫐", "Carrot": "🥕", "Loquat": "🍑", "Green Apple": "🍏", "Strawberry": "🍓",
    "Watermelon": "🍉", "Banana": "🍌", "Rafflesia": "🌺", "Pineapple": "🍍",
    # Cosmetic
    "Green Tractor": "🚜", "Large Wood Flooring": "🪵", "Sign Crate": "📦", "Small Wood Table": "🪑",
    "Large Path Tile": "🛤️", "Medium Path Tile": "⬛", "Wood Fence": "🪵", "Axe Stump": "🪨", "Shovel": "🪓",
    # Gear
    "Advanced Sprinkler": "💦", "Master Sprinkler": "💧", "Basic Sprinkler": "🌦️", "Godly Sprinkler": "⚡",
    "Trowel": "⛏️", "Harvest Tool": "🧲", "Cleaning Spray": "🧴", "Recall Wrench": "🔧",
    "Favorite Tool": "❤️", "Watering Can": "🚿", "Magnifying Glass": "🔍", "Tanning Mirror": "🪞", "Friendship Pot": "🌻",
    # Eggs
    "Common Egg": "🥚", "Common Summer Egg": "☀️🥚", "Paradise Egg": "🐣",
    # Weather
    # (handled separately)
}

# Функция запроса стока по типу
def fetch_stock(stock_type: str):
    params = {
        "select": "*",
        "type": f"eq.{stock_type}",
        "active": "eq.true",
        "order": "created_at.desc"
    }
    resp = requests.get(BASE_URL, headers=HEADERS, params=params)
    return resp.json() if resp.ok else []

# Функция запроса погоды
def fetch_weather():
    params = {
        "select": "*",
        "type": "eq.weather",
        "active": "eq.true",
        "order": "date.desc",
        "limit": 1
    }
    resp = requests.get(BASE_URL, headers=HEADERS, params=params)
    return resp.json() if resp.ok else []

# Форматирование блока стока
def format_block(title: str, emoji: str, items: list) -> str:
    if not items:
        return ""
    header = title.replace("_", " ").title().replace(" Stock", "")
    text = f"**━ {emoji} {header} Stock ━**\n"
    for it in items:
        name = it.get("display_name", "Unknown")
        qty  = it.get("multiplier", 0)
        em   = ITEM_EMOJI.get(name, "•")
        text += f"   {em} {name}: x{qty}\n"
    return text + "\n"

# Форматирование погоды
from zoneinfo import ZoneInfo

def format_weather(item: dict) -> str:
    if not item:
        return "**☁️ Weather отсутствует**"
    # Парсим дату UTC из API и конвертируем в MSK
    iso_date = item.get("date")
    try:
        dt_utc = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        dt_msk = dt_utc.astimezone(ZoneInfo("Europe/Moscow"))
        time_msk = dt_msk.strftime("%d.%m.%Y %H:%M:%S MSK")
    except Exception:
        time_msk = iso_date
    desc = item.get("display_name", "?")
    # Формируем текст построчно
    lines = [
        "**━ ☁️ Weather ━**",
        f"   🕒 {time_msk}",
        f"   🌡️ {desc}"
    ]
return "\n".join(lines)