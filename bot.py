# bot.py
import types, sys
# Monkey-patch imghdr stub for Python 3.13 compatibility
if 'imghdr' not in sys.modules:
    mod = types.ModuleType('imghdr')
    mod.what = lambda *args, **kwargs: None
    sys.modules['imghdr'] = mod

import os
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv
import requests
from zoneinfo import ZoneInfo
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes
)
import time

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# Emoji mappings
CATEGORY_EMOJI = {
    "seeds": "🌱", "gear": "🧰", "egg": "🥚", "cosmetic": "💄", "weather": "☁️"
}
ITEM_EMOJI = {
    # Seeds
    "carrot": "🥕", "strawberry": "🍓", "blueberry": "🫐", "orange_tulip": "🌷", "tomato": "🍅",
    "daffodil": "🌼", "watermelon": "🍉", "pumpkin": "🎃", "apple": "🍎", "bamboo": "🎍",
    "coconut": "🥥", "cactus": "🌵", "dragon_fruit": "🐲", "mango": "🥭", "grape": "🍇",
    "mushroom": "🍄", "pepper": "🌶️", "cacao": "🍫", "beanstalk": "🌿", "ember_lily": "🌸",
    "sugar_apple": "🍏", "burning_bud": "🔥", "giant_pinecone_seed": "🌰",
    # Gear
    "cleaning_spray": "🧴", "trowel": "⛏️", "watering_can": "🚿", "recall_wrench": "🔧",
    "basic_sprinkler": "🌦️", "advanced_sprinkler": "💦", "godly_sprinkler": "⚡", "master_sprinkler": "🌧️",
    "magnifying_glass": "🔍", "tanning_mirror": "🪞", "favorite_tool": "❤️", "harvest_tool": "🧲", "friendship_pot": "🤝",
    # Eggs
    "common_egg": "🥚", "mythical_egg": "🐣", "bug_egg": "🐣", "common_summer_egg": "🥚", "rare_summer_egg": "🥚", "paradise_egg": "🐣", "bee_egg": "🐣",
    # Cosmetics
    "sign_crate": "📦", "medium_wood_flooring": "🪵", "market_cart": "🛒",
    "yellow_umbrella": "☂️", "hay_bale": "🌾", "brick_stack": "🧱",
    "torch": "🔥", "stone_lantern": "🏮", "brown_bench": "🪑", "red_cooler_chest": "📦", "log_bench": "🛋️", "light_on_ground": "💡", "small_circle_tile": "⚪", "beach_crate": "📦", "blue_cooler_chest": "🧊", "large_wood_flooring": "🪚", "medium_stone_table": "🪨", "wood_pile": "🪵", "medium_path_tile": "🛤️", "shovel_grave": "⛏️", "frog_fountain": "🐸", "small_stone_lantern": "🕯️", "small_wood_table": "🪑", "medium_circle_tile": "🔘", "small_path_tile": "🔹", "mini_tv": "📺", "rock_pile": "🗿", "brown_stone_pillar": "🧱", "bookshelf": "📚"
}

WEATHER_EMOJI = {
    "rain": "🌧️", "heatwave": "🔥", "summerharvest": "☀️",
    "tornado": "🌪️", "windy": "🌬️", "auroraborealis": "🌌",
    "tropicalrain": "🌴🌧️", "nightevent": "🌙", "sungod": "☀️",
    "megaharvest": "🌾", "gale": "🌬️", "thunderstorm": "⛈️",
    "bloodmoonevent": "🌕🩸", "meteorshower": "☄️", "spacetravel": "🪐",
    "disco": "💃", "djjhai": "🎵", "blackhole": "🕳️",
    "jandelstorm": "🌩️", "sandstorm": "🏜️"
}

NOTIFY_ITEMS = ["beanstalk", "ember_lily", "sugar_apple", "burning_bud","giant_pinecone_seed", "master_sprinkler"]
STOCK_API = "https://api.joshlei.com/v2/growagarden/stock"
WEATHER_API = "https://api.joshlei.com/v2/growagarden/weather"

# Fetchers
async def fetch_all_stock():
    try:
        r = requests.get(STOCK_API, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logging.error(f"Stock fetch error: {e}")
        return {}

async def fetch_weather():
    try:
        r = requests.get(WEATHER_API, timeout=10)
        r.raise_for_status()
        return r.json().get("weather", [])
    except Exception as e:
        logging.error(f"Weather fetch error: {e}")
        return []

# Formatters
def format_block(key: str, items: list) -> str:
    if not items:
        return ""
    emoji = CATEGORY_EMOJI.get(key.replace("_stock", ""), "•")
    title = key.replace("_stock", "").capitalize()
    lines = [f"━ {emoji} *{title}* ━"]
    for it in items:
        em = ITEM_EMOJI.get(it.get("item_id"), "•")
        lines.append(f"   {em} {it.get('display_name')}: x{it.get('quantity',0)}")
    return "\n".join(lines) + "\n\n"

def format_weather_block(weather_list: list) -> str:
    active = next((w for w in weather_list if w.get("active")), None)
    if not active:
        return "━ ☁️ *Погода* ━\nНет активных погодных событий"
    name = active.get("weather_name")
    eid = active.get("weather_id")
    emoji = WEATHER_EMOJI.get(eid, "☁️")
    end_ts = active.get("end_duration_unix", 0)
    ends = datetime.fromtimestamp(end_ts, tz=ZoneInfo("Europe/Moscow")).strftime("%H:%M MSK") if end_ts else "--"
    dur = active.get("duration", 0)
    return (
        f"━ {emoji} *Погода* ━\n"
        f"*Текущая:* {name}\n"
        f"*Заканчивается в:* {ends}\n"
        f"*Длительность:* {dur} сек"
    )

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📦 Стоки", callback_data="show_stock")],
        [InlineKeyboardButton("💄 Косметика", callback_data="show_cosmetic")],
        [InlineKeyboardButton("☁️ Погода", callback_data="show_weather")]
    ]
    await update.message.reply_text("Привет! Выбери действие:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    last = context.user_data.get("last_stock", 0)
    if time.time() - last < 10:
        await update.callback_query.answer("⏳ Подожди немного", show_alert=True)
        return
    context.user_data["last_stock"] = time.time()
    if update.callback_query:
        await update.callback_query.answer()
        tgt = update.callback_query.message
    else:
        tgt = update.message
    data = await fetch_all_stock()
    now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y %H:%M:%S MSK")
    text = f"*🕒 {now}*\n\n"
    for sec in ["seed_stock", "gear_stock", "egg_stock"]:
        text += format_block(sec, data.get(sec, []))
    await tgt.reply_markdown(text)

async def handle_cosmetic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    last = context.user_data.get("last_cosmetic", 0)
    if time.time() - last < 10:
        await update.callback_query.answer("⏳ Подожди немного", show_alert=True)
        return
    context.user_data["last_cosmetic"] = time.time()
    if update.callback_query:
        await update.callback_query.answer()
        tgt = update.callback_query.message
    else:
        tgt = update.message
    data = await fetch_all_stock()
    now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y %H:%M:%S MSK")
    text = f"*🕒 {now}*\n\n" + format_block("cosmetic_stock", data.get("cosmetic_stock", []))
    await tgt.reply_markdown(text)

async def handle_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    last = context.user_data.get("last_weather", 0)
    if time.time() - last < 10:
        await update.callback_query.answer("⏳ Подожди немного", show_alert=True)
        return
    context.user_data["last_weather"] = time.time()
    if update.callback_query:
        await update.callback_query.answer()
        tgt = update.callback_query.message
    else:
        tgt = update.message
    weather = await fetch_weather()
    await tgt.reply_markdown(format_weather_block(weather))

# Command wrappers
async def stock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_stock(update, context)

async def cosmetic_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_cosmetic(update, context)

async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_weather(update, context)

# Notification Task
async def monitor_stock(app):
    while True:
        await asyncio.sleep(compute_delay())
        data = await fetch_all_stock()
        ts = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y %H:%M:%S MSK")
        for section in ["seed_stock", "gear_stock", "egg_stock", "cosmetic_stock"]:
            for it in data.get(section, []):
                if it["item_id"] in NOTIFY_ITEMS and it.get("quantity", 0) > 0:
                    msg = f"*{ITEM_EMOJI[it['item_id']]} {it['display_name']}: x{it['quantity']} в стоке!*\n🕒 {ts}\n\n*@GrowAGarden*"
                    await app.bot.send_message(chat_id=CHANNEL_ID, text=msg, parse_mode="Markdown")

# Delay calculator
def compute_delay():
    now = datetime.now(tz=ZoneInfo("Europe/Moscow"))
    next_min = ((now.minute // 5) + 1) * 5
    next_hour = now.hour + (1 if next_min >= 60 else 0)
    next_min %= 60
    next_run = now.replace(hour=next_hour % 24, minute=next_min, second=7, microsecond=0)
    delta = (next_run - now).total_seconds()
    return delta if delta >= 0 else delta + 86400

# Application setup
async def post_init(app):
    asyncio.create_task(monitor_stock(app))

app = ApplicationBuilder().token(BOT_TOKEN).build()
# Register handlers
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("stock", stock_command))
app.add_handler(CommandHandler("cosmetic", cosmetic_command))
app.add_handler(CommandHandler("weather", weather_command))
app.add_handler(CallbackQueryHandler(handle_stock, pattern="show_stock"))
app.add_handler(CallbackQueryHandler(handle_cosmetic, pattern="show_cosmetic"))
app.add_handler(CallbackQueryHandler(handle_weather, pattern="show_weather"))

if __name__ == "__main__":
    async def main():
        await app.initialize()
        await post_init(app)
        await app.start()
        await app.bot.set_webhook(f"https://{os.getenv('DOMAIN')}/webhook/{BOT_TOKEN}")
        print("Webhook listening...")
        await app.updater.start_webhook(
            listen="0.0.0.0",
            port=int(os.getenv("PORT", 5000)),
            webhook_url=None
        )
        await app.updater.idle()

    asyncio.run(main())