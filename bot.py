import os
import threading
import requests
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from zoneinfo import ZoneInfo

# 1) Load environment
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_KEY   = os.getenv("API_KEY")

# 2) Supabase endpoint
BASE_URL = "https://vextbzatpprnksyutbcp.supabase.co/rest/v1/growagarden_stock"
HEADERS = {"apikey": API_KEY, "Authorization": f"Bearer {API_KEY}"}

# 3) Emoji mappings
CATEGORY_EMOJI = {
    "seeds_stock":    "🌱",
    "cosmetic_stock": "💎",
    "gear_stock":     "🧰",
    "egg_stock":      "🥚",
    "weather":        "☁️"
}
ITEM_EMOJI = {
    "Feijoa":"🥝", "Kiwi":"🥝", "Avocado":"🥑", "Sugar Apple":"🍏", "Tomato":"🍅",
    "Bell Pepper":"🌶️", "Pitcher Plant":"🌱", "Prickly Pear":"🌵", "Cauliflower":"🥦",
    "Blueberry":"🫐", "Carrot":"🥕", "Loquat":"🍑", "Green Apple":"🍏", "Strawberry":"🍓",
    "Watermelon":"🍉", "Banana":"🍌", "Rafflesia":"🌺", "Pineapple":"🍍",
    "Green Tractor":"🚜", "Large Wood Flooring":"🪵", "Sign Crate":"📦", "Small Wood Table":"🪑",
    "Large Path Tile":"🛤️", "Medium Path Tile":"⬛", "Wood Fence":"🪵", "Axe Stump":"🪨", "Shovel":"🪓",
    "Advanced Sprinkler":"💦", "Master Sprinkler":"💧", "Basic Sprinkler":"🌦️", "Godly Sprinkler":"⚡",
    "Trowel":"⛏️", "Harvest Tool":"🧲", "Cleaning Spray":"🧴", "Recall Wrench":"🔧",
    "Favorite Tool":"❤️", "Watering Can":"🚿", "Magnifying Glass":"🔍", "Tanning Mirror":"🪞", "Friendship Pot":"🌻",
    "Common Egg":"🥚", "Common Summer Egg":"🥚", "Paradise Egg":"🐣"
}

# 4) Fetch stock
def fetch_stock(stock_type: str):
    params = {
        "select": "*",
        "type": f"eq.{stock_type}",
        "active": "eq.true",
        "order": "created_at.desc"
    }
    resp = requests.get(BASE_URL, headers=HEADERS, params=params)
    return resp.json() if resp.ok else []

# 5) Fetch weather
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

# 6) Format stock block
def format_block(key: str, emoji: str, items: list) -> str:
    if not items:
        return ""
    title = key.replace("_stock", "").replace("_", " ").title()
    text = f"**━ {emoji} {title} Stock ━**\n"
    for it in items:
        name = it.get("display_name", "Unknown")
        qty  = it.get("multiplier", 0)
        em   = ITEM_EMOJI.get(name, "•")
        text += f"   {em} {name}: x{qty}\n"
    return text + "\n"

# 7) Format weather block
def format_weather(item: dict) -> str:
    if not item:
        return "**☁️ Weather отсутствует**"
    iso = item.get("date")
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ZoneInfo("Europe/Moscow"))
        time_str = dt.strftime("%d.%m.%Y %H:%M:%S MSK")
    except:
        time_str = iso
    desc = item.get("display_name", "?")
    lines = [
        "**━ ☁️ Weather ━**",
        f"   🕒 {time_str}",
        f"   🌡️ {desc}"
    ]
    return "\n".join(lines)

# 8) Keyboard
def get_keyboard():
     return InlineKeyboardMarkup([
         [InlineKeyboardButton("📦 Показать стоки", callback_data="show_stock")],
         [InlineKeyboardButton("☁️ Показать погоду", callback_data="show_weather")]
     ])

# 9) Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
     await update.message.reply_text("Привет! Выбери действие:", reply_markup=get_keyboard())

async def handle_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
     # handle callback or command
     if update.callback_query:
         await update.callback_query.answer()
         target = update.callback_query.message
     else:
         target = update.message
     data = {k: fetch_stock(k) for k in ["seeds_stock","cosmetic_stock","gear_stock","egg_stock"]}
     now = datetime.utcnow().strftime("**🕒 %d.%m.%Y %H:%M:%S UTC**\n\n")
     text = now + "**📊 Стоки Grow a Garden:**\n\n"
     for k, items in data.items():
         text += format_block(k, CATEGORY_EMOJI.get(k, "📦"), items)
     await target.reply_markdown(text)

async def handle_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
     if update.callback_query:
         await update.callback_query.answer()
         target = update.callback_query.message
     else:
         target = update.message
     arr = fetch_weather()
     item = arr[0] if arr else None
     text = format_weather(item)
     await target.reply_markdown(text)

# 10) Flask healthcheck
app = Flask(__name__)
@app.route("/")
def healthcheck():
     return "Bot is alive!"

# 11) Main
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