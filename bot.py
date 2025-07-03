import os
import threading
import time
import requests
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from zoneinfo import ZoneInfo

# Load environment
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_KEY   = os.getenv("API_KEY")  # Supabase key for stock fallback

# Endpoints
JOSH_URL     = "https://api.joshlei.com/v2/growagarden/stock"
WEATHER_URL  = "https://growagardenstock.com/api/stock/weather"

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
    "carrot": "🥕", "strawberry": "🍓", "blueberry": "🫐", "tomato": "🍅",
    # Gear
    "cleaning_spray": "🧴", "trowel": "⛏️", "watering_can": "🚿", "recall_wrench": "🔧",
    "favorite_tool": "❤️", "harvest_tool": "🧲", "advanced_sprinkler": "💦",
    # Eggs
    "common_egg": "🥚", "paradise_egg": "🐣",
    # Event
    "delphinium": "🌸", "summer_seed_pack": "🌞", "mutation_spray_burnt": "🔥"
}

# Fetch all stock
def fetch_all_stock():
    r = requests.get(JOSH_URL)
    return r.json() if r.ok else {}

# Format a stock category block
def format_block(category: str, items: list) -> str:
    if not items:
        return ""
    emoji = CATEGORY_EMOJI.get(category, "📦")
    title = category.capitalize() + " Stock"
    text = f"**━ {emoji} {title} ━**\n"
    for it in items:
        key = it.get("item_id", "").lower()
        name = it.get("display_name", key.title())
        qty  = it.get("quantity", 0)
        em   = ITEM_EMOJI.get(key, "•")
        text += f"   {em} {name}: x{qty}\n"
    return text + "\n"

# Fetch weather from new API
def fetch_weather():
    ts = int(time.time() * 1000)
    params = {"ts": ts, "_": ts}
    r = requests.get(WEATHER_URL, params=params)
    return r.json() if r.ok else {}

# Format weather block
def format_weather(data: dict) -> str:
    if not data or "description" not in data:
        return "**☁️ Weather отсутствует**"
    icon        = data.get("icon", "☁️")
    description = data.get("description", "")
    # description already contains markdown
    header = f"**━ {icon} Weather ━**"
    return f"{header}\n{description}"

# Keyboard layout
def get_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Показать стоки", callback_data="show_stock")],
        [InlineKeyboardButton("☁️ Показать погоду", callback_data="show_weather")]
    ])

# Handlers
tz = ZoneInfo("Europe/Moscow")
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Выбери действие:", reply_markup=get_keyboard())

async def handle_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        target = update.callback_query.message
    else:
        target = update.message
    stock = fetch_all_stock()
    dt = datetime.now(tz=tz)
    now = f"**🕒 {dt.strftime('%d.%m.%Y %H:%M:%S MSK')}**\n\n"
    text = now + "**📊 Стоки Grow a Garden:**\n\n"
    for cat in ["seeds","gear","egg","event"]:
        text += format_block(cat, stock.get(f"{cat}_stock", []))
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
def healthcheck():
    return "Bot is alive!"

# Main
if __name__ == "__main__":
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=int(os.getenv("PORT",10000))), daemon=True
    ).start()
    bot = ApplicationBuilder().token(BOT_TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("stock", handle_stock))
    bot.add_handler(CallbackQueryHandler(handle_stock, pattern="show_stock"))
    bot.add_handler(CommandHandler("weather", handle_weather))
    bot.add_handler(CallbackQueryHandler(handle_weather, pattern="show_weather"))
    print("✅ Bot is running…")
    bot.run_polling()