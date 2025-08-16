import os
import requests
import time
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from zoneinfo import ZoneInfo
import threading

# Load environment
# authors: Shaderri
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
JSTUDIO_KEY = os.getenv("JSTUDIO_KEY")

# New stock endpoint
STOCK_API = "https://api.joshlei.com/v2/growagarden/stock"
WEATHER_API = "https://api.joshlei.com/v2/growagarden/weather"

# Cooldown settings
COOLDOWN_SECONDS = 5
last_invocation = {}  # {user_id: timestamp}

# Emoji mappings
CATEGORY_EMOJI = {
    "seed_stock": "🌱",
    "gear_stock": "🧰",
    "egg_stock": "🥚",
    "eventshop_stock": "🫛",  # новая категория
}

ITEM_EMOJI = {
    # Seeds
    "carrot": "🥕", "strawberry": "🍓", "blueberry": "🫐", "orange_tulip": "🌷", "tomato": "🍅", "corn": "🌽",
    "daffodil": "🌼", "watermelon": "🍉", "pumpkin": "🎃", "apple": "🍎", "bamboo": "🎍",
    "coconut": "🥥", "cactus": "🌵", "dragon_fruit": "🐲", "mango": "🥭", "grape": "🍇",
    "mushroom": "🍄", "pepper": "🌶️", "cacao": "🍫", "beanstalk": "🌿", "ember_lily": "🌸",
    "sugar_apple": "🍏", "burning_bud": "🔥", "giant_pinecone": "🌰", "elder_strawberry": "🍓",
    "romanesco": "🥦",

    # Gear
    "cleaning_spray": "🧴", "trowel": "⛏️", "watering_can": "🚿", "recall_wrench": "🔧",
    "basic_sprinkler": "🌦️", "advanced_sprinkler": "💦", "godly_sprinkler": "⚡", "master_sprinkler": "🌧️",
    "magnifying_glass": "🔍", "tanning_mirror": "🪞", "favorite_tool": "❤️", "harvest_tool": "🧲", "friendship_pot": "🤝", "levelup_lollipop": "🍭", "trading_ticket": "🎟️", "grandmaster_sprinkler": "💦",

    # Eggs
    "common_egg": "🥚", "mythical_egg": "🐣", "bug_egg": "🐣", "common_summer_egg": "🥚", "rare_summer_egg": "🥚", "paradise_egg": "🐣", "bee_egg": "🐣",

    # Cosmetics
    "sign_crate": "📦", "medium_wood_flooring": "🪵", "market_cart": "🛒",
    "yellow_umbrella": "☂️", "hay_bale": "🌾", "brick_stack": "🧱",
    "torch": "🔥", "stone_lantern": "🏮", "brown_bench": "🪑", "red_cooler_chest": "📦", "log_bench": "🛋️", "light_on_ground": "💡", "small_circle_tile": "⚪", "beach_crate": "📦", "blue_cooler_chest": "🧊", "large_wood_flooring": "🪚", "medium_stone_table": "🪨", "wood_pile": "🪵", "medium_path_tile": "🛤️", "shovel_grave": "⛏️", "frog_fountain": "🐸", "small_stone_lantern": "🕯️", "small_wood_table": "🪑", "medium_circle_tile": "🔘", "small_path_tile": "🔹", "mini_tv": "📺", "rock_pile": "🗿", "brown_stone_pillar": "🧱", "red_cooler_chest": "🧊", "bookshelf": "📚", "brown_bench": "🪑", "log_bench": "🪵", "large_path_tile": "◼️", "axe_stump": "🪵", "shovel": "⛏️", "flat_canopy": "🏕️", "large_wood_table": "🪵", "small_wood_flooring": "🪵", "small_stone_pad": "◽️", "long_stone_table": "🪨",

    # Event shop items
    "zen_seed_pack": "🌱", "zen_egg": "🥚", "hot_spring": "♨️", "zen_sand": "🏖️", "zenflare": "✨",
    "zen_crate": "📦", "soft_sunshine": "☀️", "koi": "🐟", "zen_gnome_crate": "🧙", "spiked_mango": "🥭", "pet_shard_tranquil": "💠", "tranquil_radar": "🔫", "sakura_bush": "🌸", "corrupt_radar": "🧿", "raiju": "⚡", "pet_shard_corrupted": "🧩",

    # New Event items
    "sprout_seed_pack": "🌱",
    "sprout_egg": "🥚",
    "mandrake_seed": "🧙‍♂️🌱",
    "sprout_crate": "📦",
    "silver_fertilizer": "⚪🌱",
    "canary_melon_seed": "🍈",
    "amberheart": "💛",
    "spriggan": "🌿🧚",
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

TITLE_MAP = {
    "seed_stock": "*Seeds*",
    "gear_stock": "*Gear*",
    "egg_stock": "*Eggs*",
    "eventshop_stock": "*Event*",
}

# Fetchers (с ключом в заголовке)
def fetch_all_stock():
    try:
        r = requests.get(
            STOCK_API,
            headers={"jstudio-key": JSTUDIO_KEY},
            timeout=10
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return {}

def fetch_weather():
    try:
        r = requests.get(
            WEATHER_API,
            headers={"jstudio-key": JSTUDIO_KEY},
            timeout=10
        )
        r.raise_for_status()
        return r.json().get("weather", [])
    except Exception:
        return []

# Cooldown checker
def check_cooldown(user_id: int) -> bool:
    now = time.time()
    last = last_invocation.get(user_id, 0)
    if now - last < COOLDOWN_SECONDS:
        return False
    last_invocation[user_id] = now
    return True

# Formatters
def format_block(key, items):
    if not items:
        return ""
    emoji = CATEGORY_EMOJI.get(key, "•")
    title = TITLE_MAP.get(key, key.replace("_stock", "").capitalize())
    lines = [f"━ {emoji} {title} ━"]
    for it in items:
        em = ITEM_EMOJI.get(it.get("item_id"), "•")
        lines.append(f"   {em} {it.get('display_name')} x{it.get('quantity', 0)}")
    return "\n".join(lines) + "\n\n"

def format_weather(weather_list):
    active = next((w for w in weather_list if w.get("active")), None)
    if not active:
        return "━ ☁️ *Погода* ━\nНет активных погодных событий"
    eid = active.get("weather_id")
    ends = datetime.fromtimestamp(active.get("end_duration_unix", 0), tz=ZoneInfo("Europe/Moscow")).strftime("%H:%M MSK")
    return (
        f"━ {WEATHER_EMOJI.get(eid, '☁️')} *Погода* ━\n"
        f"*Текущая:* {active.get('weather_name')}\n"
        f"*Заканчивается в:* {ends}\n"
        f"*Длительность:* {active.get('duration')} сек"
    )

# Keyboard builder
def get_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Стоки", callback_data="show_stock")],
        [InlineKeyboardButton("💄 Косметика", callback_data="show_cosmetic")],
        [InlineKeyboardButton("☁️ Погода", callback_data="show_weather")]
    ])

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Выбери действие:", reply_markup=get_keyboard())

async def handle_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tgt = update.callback_query.message if update.callback_query else update.message
    if not check_cooldown(user_id):
        return await tgt.reply_text("⏳ Подождите 5 сек перед повторным запросом.")
    if update.callback_query:
        await update.callback_query.answer()
    data = fetch_all_stock()
    now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime('%d.%m.%Y %H:%M:%S MSK')
    text = f"*🕒 {now}*\n\n" + "".join(
        format_block(sec, data.get(sec, []))
        for sec in ["seed_stock", "gear_stock", "egg_stock", "eventshop_stock"]
    )
    await tgt.reply_markdown(text)

async def handle_cosmetic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tgt = update.callback_query.message if update.callback_query else update.message
    if not check_cooldown(user_id):
        return await tgt.reply_text("⏳ Подождите 5 сек перед повторным запросом.")
    if update.callback_query:
        await update.callback_query.answer()
    data = fetch_all_stock()
    now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime('%d.%m.%Y %H:%M:%S MSK')
    await tgt.reply_markdown(f"*🕒 {now}*\n\n" +
        format_block("cosmetic_stock", data.get("cosmetic_stock", []))
    )

async def handle_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tgt = update.callback_query.message if update.callback_query else update.message
    if not check_cooldown(user_id):
        return await tgt.reply_text("⏳ Под ждите 5 сек перед повторным запросом.")
    if update.callback_query:
        await update.callback_query.answer()
    weather = fetch_weather()
    await tgt.reply_markdown(format_weather(weather))

# Healthcheck & bot setup
app = Flask(__name__)
@app.route("/")
def healthcheck():
    return "OK"

if __name__ == "__main__":
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000))),
        daemon=True
    ).start()
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    for cmd, fn in [
        ("start", start),
        ("stock", handle_stock),
        ("cosmetic", handle_cosmetic),
        ("weather", handle_weather)
    ]:
        app_bot.add_handler(CommandHandler(cmd, fn))
    app_bot.add_handler(CallbackQueryHandler(handle_stock, pattern="show_stock"))
    app_bot.add_handler(CallbackQueryHandler(handle_cosmetic, pattern="show_cosmetic"))
    app_bot.add_handler(CallbackQueryHandler(handle_weather, pattern="show_weather"))
    app_bot.run_polling(drop_pending_updates=True)