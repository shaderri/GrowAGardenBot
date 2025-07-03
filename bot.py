import os
import threading
import requests
import time
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from zoneinfo import ZoneInfo

# Load environment
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Endpoints
JOSH_URL    = "https://api.joshlei.com/v2/growagarden/stock"
WEATHER_URL = "https://growagardenstock.com/api/stock/weather"

# Emoji mappings
CATEGORY_EMOJI = {
    "seeds":   "🌱",
    "gear":    "🧰",
    "egg":     "🥚",
    "event":   "🎉",
    "weather": "☁️"
}
ITEM_EMOJI = {
    # Seeds
    "carrot": "🥕", "strawberry": "🍓", "blueberry": "🫐", "tomato": "🍅", "banana": "🍌",
    # Gear
    "cleaning_spray": "🧴", "trowel": "⛏️", "watering_can": "🚿", "recall_wrench": "🔧",
    "favorite_tool": "❤️", "harvest_tool": "🧲", "advanced_sprinkler": "💦",
    # Eggs
    "common_egg": "🥚", "paradise_egg": "🐣",
    # Event
    "delphinium": "🌸", "summer_seed_pack": "🌞", "mutation_spray_burnt": "🔥"
}

def fetch_all_stock():
    # Fetch JSON once
    r = requests.get(JOSH_URL)
    if not r.ok:
        return {"seeds":[],"gear":[],"egg":[],"event":[]}
    data = r.json()
    return {
        "seeds": data.get("seed_stock", []),
        "gear":  data.get("gear_stock", []),
        "egg":   data.get("egg_stock", []),
        "event": data.get("eventshop_stock", [])
    }

def format_block(category: str, items: list) -> str:
    if not items:
        return ""
    emoji = CATEGORY_EMOJI[category]
    title = category.capitalize() + " Stock"
    lines = [f"**━ {emoji} {title} ━**"]
    for it in items:
        key = it.get("item_id", "").lower()
        name = it.get("display_name", key.title())
        qty  = it.get("quantity", 0)
        em   = ITEM_EMOJI.get(key, "•")
        lines.append(f"   {em} {name}: x{qty}")
    return "\n".join(lines) + "\n\n"

# Weather fetch and format

def fetch_weather():
    ts = int(time.time() * 1000)
    r = requests.get(WEATHER_URL, params={"ts": ts, "_": ts})
    return r.json() if r.ok else {}

def format_weather(data: dict) -> str:
    icon = data.get("icon", "☁️")
    current = data.get("currentWeather", "Unknown")
    desc = data.get("description", "").strip()
    # Convert timestamp to MSK
    updated = data.get("updatedAt")
    try:
        dt = datetime.fromtimestamp(updated/1000, tz=ZoneInfo("Europe/Moscow"))
        time_str = dt.strftime("%d.%m.%Y %H:%M:%S MSK")
    except:
        time_str = ""
    lines = [
        f"**━ {icon} Weather ━**",
        f"**Current:** {current}",
        f"**Updated:** {time_str}",
        desc
    ]
    return "\n".join(lines)

# Keyboard
def get_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Показать стоки", callback_data="show_stock")],
        [InlineKeyboardButton("☁️ Показать погоду", callback_data="show_weather")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Выбери действие:", reply_markup=get_keyboard())

async def handle_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        target = update.callback_query.message
    else:
        target = update.message
    stock = fetch_all_stock()
    dt = datetime.now(tz=ZoneInfo("Europe/Moscow"))
    header = f"**🕒 {dt.strftime('%d.%m.%Y %H:%M:%S MSK')}**\n\n**📊 Стоки Grow a Garden:**\n\n"
    text = header
    for cat in ["seeds","gear","egg","event"]:
        text += format_block(cat, stock[cat])
    await target.reply_markdown(text)

async def handle_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        target = update.callback_query.message
    else:
        target = update.message
    data = fetch_weather()
    text = format_weather(data)
    await target.reply_markdown(text)

# Flask healthcheck
app = Flask(__name__)
@app.route("/")
def healthcheck(): return "Bot is alive!"

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.getenv("PORT",10000))), daemon=True).start()
    bot = ApplicationBuilder().token(BOT_TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("stock", handle_stock))
    bot.add_handler(CallbackQueryHandler(handle_stock, pattern="show_stock"))
    bot.add_handler(CommandHandler("weather", handle_weather))
    bot.add_handler(CallbackQueryHandler(handle_weather, pattern="show_weather"))
    print("✅ Bot is running…")
    bot.run_polling()