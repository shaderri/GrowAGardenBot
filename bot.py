import os
import threading
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
API_KEY   = os.getenv("API_KEY")  # Supabase API key

# Endpoints
SUPABASE_URL     = "https://vextbzatpprnksyutbcp.supabase.co/rest/v1/growagarden_stock"
SUPABASE_HEADERS = {"apikey": API_KEY, "Authorization": f"Bearer {API_KEY}"}
JOSH_URL         = "https://api.joshlei.com/v2/growagarden/stock"

# Emoji mappings
CATEGORY_EMOJI = {
    "seeds": "🌱",
    "gear":  "🧰",
    "egg":   "🥚",
    "event": "🎉",
    "weather": "☁️"
}
ITEM_EMOJI = {
    # Seeds
    "carrot": "🥕", "strawberry": "🍓", "blueberry": "🫐", "tomato": "🍅",
    "banana": "🍌", "feijoa": "🥝", "kiwi": "🥝", "avocado": "🥑",
    # Gear
    "cleaning_spray": "🧴", "trowel": "⛏️", "watering_can": "🚿", "recall_wrench": "🔧",
    "favorite_tool": "❤️", "harvest_tool": "🧲", "advanced_sprinkler": "💦",
    # Eggs
    "common_egg": "🥚", "paradise_egg": "🐣",
    # Event (Summer)
    "delphinium": "🌸", "summer_seed_pack": "🌞", "mutation_spray_burnt": "🔥"
}

# Fetch all stock (excluding cosmetic)
def fetch_all_stock():
    r = requests.get(JOSH_URL)
    if not r.ok:
        return {}
    data = r.json()
    return {
        "seeds": data.get("seed_stock", []),
        "gear":  data.get("gear_stock", []),
        "egg":   data.get("egg_stock", []),
        "event": data.get("eventshop_stock", [])
    }

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

# Fetch weather fallback
def fetch_weather():
    params = {"select":"*","type":"eq.weather","active":"eq.true","order":"date.desc","limit":1}
    r = requests.get(SUPABASE_URL, headers=SUPABASE_HEADERS, params=params)
    return r.json() if r.ok else []

# Format weather block
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

# Keyboard layout
def get_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Показать стоки", callback_data="show_stock")],
        [InlineKeyboardButton("☁️ Показать погоду", callback_data="show_weather")]
    ])

# Handlers
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
    now = f"**🕒 {dt.strftime('%d.%m.%Y %H:%M:%S MSK')}**\n\n"
    text = now + "**📊 Стоки Grow a Garden:**\n\n"
    text += format_block("seeds", stock.get("seeds", []))
    text += format_block("gear",  stock.get("gear", []))
    text += format_block("egg",   stock.get("egg", []))
    text += format_block("event", stock.get("event", []))
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

# Flask healthcheck
app = Flask(__name__)
@app.route("/")
def healthcheck():
    return "Bot is alive!"

# Main
if __name__ == "__main__":
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=int(os.getenv("PORT",10000))),
        daemon=True
    ).start()
    bot = ApplicationBuilder().token(BOT_TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("stock", handle_stock))
    bot.add_handler(CallbackQueryHandler(handle_stock, pattern="show_stock"))
    bot.add_handler(CommandHandler("weather", handle_weather))
    bot.add_handler(CallbackQueryHandler(handle_weather, pattern="show_weather"))
    print("✅ Bot is running…")
    bot.run_polling()