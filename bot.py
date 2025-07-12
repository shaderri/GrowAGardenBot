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

# Patch imghdr stub for Python 3.13
import types, sys
if 'imghdr' not in sys.modules:
    stub = types.ModuleType('imghdr')
    stub.what = lambda *args, **kwargs: None
    sys.modules['imghdr'] = stub

# Logging
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# Load environment
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # e.g. "-1001234567890"

# Emoji mappings
CATEGORY_EMOJI = {"seeds": "🌱", "gear": "🧰", "egg": "🥚", "cosmetic": "💄", "weather": "☁️"}
ITEM_EMOJI = {
    "carrot": "🥕", "strawberry": "🍓", "blueberry": "🫐", "orange_tulip": "🌷", "tomato": "🍅",
    "daffodil": "🌼", "watermelon": "🍉", "pumpkin": "🎃", "apple": "🍎", "bamboo": "🎍",
    "coconut": "🥥", "cactus": "🌵", "dragon_fruit": "🐲", "mango": "🥭", "grape": "🍇",
    "mushroom": "🍄", "pepper": "🌶️", "cacao": "🍫", "beanstalk": "🌿", "ember_lily": "🌸",
    "sugar_apple": "🍏", "burning_bud": "🔥",
    "cleaning_spray": "🧴", "trowel": "⛏️", "watering_can": "🚿", "recall_wrench": "🔧",
    "basic_sprinkler": "🌦️", "advanced_sprinkler": "💦", "godly_sprinkler": "⚡", "master_sprinkler": "🌧️",
    "magnifying_glass": "🔍", "tanning_mirror": "🪞", "favorite_tool": "❤️", "harvest_tool": "🧲", "friendship_pot": "🤝",
    "common_egg": "🥚", "mythical_egg": "🐣", "bug_egg": "🐣", "common_summer_egg": "🥚", "rare_summer_egg": "🥚", "paradise_egg": "🐣", "bee_egg": "🐣",
    "sign_crate": "📦", "medium_wood_flooring": "🪵", "market_cart": "🛒",
    "yellow_umbrella": "☂️", "hay_bale": "🌾", "brick_stack": "🧱",
    "torch": "🔥", "stone_lantern": "🏮", "brown_bench": "🪑", "red_cooler_chest": "📦", "log_bench": "🛋️", "light_on_ground": "💡", "small_circle_tile": "⚪", "beach_crate": "📦", "blue_cooler_chest": "🧊", "large_wood_flooring": "🪚", "medium_stone_table": "🪨", "wood_pile": "🪵", "medium_path_tile": "🛤️", "shovel_grave": "⛏️", "frog_fountain": "🐸", "small_stone_lantern": "🕯️", "small_wood_table": "🪑", "medium_circle_tile": "🔘", "small_path_tile": "🔹", "mini_tv": "📺", "rock_pile": "🗿", "brown_stone_pillar": "🧱", "bookshelf": "📚"
}

WATCH_ITEMS = [
    "beanstalk",
    "ember_lily",
    "sugar_apple",
    "burning_bud",
    "master_sprinkler",
    "carrot"
]

WEATHER_EMOJI = {
    "rain": "🌧️", "heatwave": "🔥", "summerharvest": "☀️",
    "tornado": "🌪️", "windy": "🌬️", "auroraborealis": "🌌",
    "tropicalrain": "🌴🌧️", "nightevent": "🌙", "sungod": "☀️",
    "megaharvest": "🌾", "gale": "🌬️", "thunderstorm": "⛈️",
    "bloodmoonevent": "🌕🩸", "meteorshower": "☄️", "spacetravel": "🪐",
    "disco": "💃", "djjhai": "🎵", "blackhole": "🕳️",
    "jandelstorm": "🌩️", "sandstorm": "🏜️"
}

last_seen = {item: None for item in WATCH_ITEMS}

# APIs
STOCK_API = "https://api.joshlei.com/v2/growagarden/stock"
WEATHER_API = "https://api.joshlei.com/v2/growagarden/weather"

# Fetchers
def fetch_all_stock():
    try:
        resp = requests.get(STOCK_API, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logging.error(f"Stock fetch error: {e}")
        return {}


def fetch_weather():
    try:
        resp = requests.get(WEATHER_API, timeout=10)
        resp.raise_for_status()
        return resp.json().get("weather", [])
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
    return (f"━ {emoji} *Погода* ━\n"
            f"*Текущая:* {name}\n"
            f"*Заканчивается в:* {ends}\n"
            f"*Длительность:* {dur} сек")

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📦 Стоки", callback_data="show_stock")],
        [InlineKeyboardButton("💄 Косметика", callback_data="show_cosmetic")],
        [InlineKeyboardButton("☁️ Погода", callback_data="show_weather")]
    ]
    await update.message.reply_text("Привет! Выбери действие:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        tgt = update.callback_query.message
    else:
        tgt = update.message
    data = fetch_all_stock()
    now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y %H:%M:%S MSK")
    text = f"*🕒 {now}*\n\n"
    for section in ["seed_stock","gear_stock","egg_stock"]:
        text += format_block(section, data.get(section, []))
    await tgt.reply_markdown(text)

async def handle_cosmetic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        tgt = update.callback_query.message
    else:
        tgt = update.message
    data = fetch_all_stock()
    now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y %H:%M:%S MSK")
    text = f"*🕒 {now}*\n\n" + format_block("cosmetic_stock", data.get("cosmetic_stock", []))
    await tgt.reply_markdown(text)

async def handle_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        tgt = update.callback_query.message
    else:
        tgt = update.message
    weather = fetch_weather()
    await tgt.reply_markdown(format_weather_block(weather))

# Notification Task
async def monitor_stock(app):
    # monitoring loop every 5 minutes for items in stock
    while True:
        data = fetch_all_stock()
        now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y %H:%M MSK")
        for sec in ["seed_stock","gear_stock","egg_stock","cosmetic_stock"]:
            for it in data.get(sec, []):
                iid, qty = it["item_id"], it.get("quantity", 0)
                if iid in WATCH_ITEMS and qty > 0:
                    em = ITEM_EMOJI.get(iid, "•")
                    name = it.get("display_name")
                    msg = (
                        f"*{em} {name}: x{qty} в стоке!*"
                        f"*🕒 {now}*"
                        f"[Grow a Garden News. Подписаться](https://t.me/GroowAGarden)"
                    )
                    await app.bot.send_message(chat_id=CHANNEL_ID, text=msg, parse_mode="Markdown")
        await asyncio.sleep(307)  # 5 minutes

# Initialization
async def post_init(app):
    await monitor_stock(app)

app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(handle_stock, pattern="show_stock"))
app.add_handler(CallbackQueryHandler(handle_cosmetic, pattern="show_cosmetic"))
app.add_handler(CallbackQueryHandler(handle_weather, pattern="show_weather"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run_webhook(listen="0.0.0.0", port=port,
                    webhook_url=f"https://{os.getenv('DOMAIN')}/webhook/{BOT_TOKEN}")
    print(f"Listening on port {port}")