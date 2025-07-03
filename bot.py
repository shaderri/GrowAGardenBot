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
API_KEY   = os.getenv("API_KEY")  # Supabase API key, not used for new source

# 2) API endpoints
SUPABASE_URL = "https://vextbzatpprnksyutbcp.supabase.co/rest/v1/growagarden_stock"
SUPABASE_HEADERS = {"apikey": API_KEY, "Authorization": f"Bearer {API_KEY}"}
JOSH_URL = "https://api.joshlei.com/v2/growagarden/stock"

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

# 4) Fetch stock from new source (excluding cosmetic)
def fetch_all_stock():
    resp = requests.get(JOSH_URL)
    if not resp.ok:
        return {}
    data = resp.json()
    # keys: seed_stock, gear_stock, egg_stock, eventshop_stock
    return {
        "seeds": data.get("seed_stock", []),
        "gear":  data.get("gear_stock", []),
        "egg":   data.get("egg_stock", []),
        "event": data.get("eventshop_stock", [])
    }

# 5) Format block
def format_block(category: str, items: list) -> str:
    if not items:
        return ""
    emoji = CATEGORY_EMOJI.get(category, "📦")
    title = category.capitalize() + " Stock"
    text = f"**━ {emoji} {title} ━**\n"
    for it in items:
        name = it.get("display_name", "Unknown")
        qty  = it.get("quantity", 0)
        icon_key = it.get("item_id", name).lower()
        em = ITEM_EMOJI.get(icon_key, "•")
        text += f"   {em} {name}: x{qty}\n"
    return text + "\n"

# 6) Keyboard
def get_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Показать стоки", callback_data="show_stock")],
        [InlineKeyboardButton("☁️ Показать погоду", callback_data="show_weather")]
    ])

# 7) Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Выбери действие:", reply_markup=get_keyboard())

async def handle_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        target = update.callback_query.message
    else:
        target = update.message
    stock = fetch_all_stock()
    now = datetime.utcnow().strftime("**🕒 %d.%m.%Y %H:%M:%S UTC**\n\n")
    text = now + "**📊 Стоки Grow a Garden:**\n\n"
    # in order seeds, gear, egg, event
    text += format_block("seeds", stock.get("seeds", []))
    text += format_block("gear",  stock.get("gear", []))
    text += format_block("egg",   stock.get("egg", []))
    text += format_block("event", stock.get("event", []))
    await target.reply_markdown(text)

async def handle_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # fallback to Supabase weather
    params = {"select":"*","type":"eq.weather","active":"eq.true","order":"date.desc","limit":1}
    resp = requests.get(SUPABASE_URL, headers=SUPABASE_HEADERS, params=params)
    item = resp.json()[0] if resp.ok and resp.json() else None
    # format weather
    if not item:
        text = "**☁️ Weather отсутствует**"
    else:
        iso = item.get("date")
        try:
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ZoneInfo("Europe/Moscow"))
            time_str = dt.strftime("%d.%m.%Y %H:%M:%S MSK")
        except:
            time_str = iso
        desc = item.get("display_name", "?")
        text = "**━ ☁️ Weather ━**\n"
        text += f"   🕒 {time_str}\n"
        text += f"   🌡️ {desc}\n"
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_markdown(text)
    else:
        await update.message.reply_markdown(text)

# 8) Flask healthcheck
app = Flask(__name__)
@app.route("/")
def healthcheck():
    return "Bot is alive!"

# 9) Main
if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host="0.0.0.0",port=int(os.getenv("PORT",10000))),daemon=True).start()
    bot = ApplicationBuilder().token(BOT_TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("stock", handle_stock))
    bot.add_handler(CallbackQueryHandler(handle_stock, pattern="show_stock"))
    bot.add_handler(CommandHandler("weather", handle_weather))
    bot.add_handler(CallbackQueryHandler(handle_weather, pattern="show_weather"))
    print("✅ Bot is running…")
    bot.run_polling()