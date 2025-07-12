# bot.py
import os
import threading
import time
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
from zoneinfo import ZoneInfo

# Setup logging\logr = logging.getLogger()
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # e.g. "-1001234567890" or "@YourChannel"

# Initialize bot and updater
bot = Bot(token=BOT_TOKEN)
updater = Updater(token=BOT_TOKEN, use_context=True)
dispatcher = updater.dispatcher

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
    "sugar_apple": "🍏", "burning_bud": "🔥",
    # Gear
    "cleaning_spray": "🧴", "trowel": "⛏️", "watering_can": "🚿", "recall_wrench": "🔧",
    "basic_sprinkler": "🌦️", "advanced_sprinkler": "💦", "godly_sprinkler": "⚡", "master_sprinkler": "🌧️",
    "magnifying_glass": "🔍", "tanning_mirror": "🪞", "favorite_tool": "❤️", "harvest_tool": "🧲", "friendship_pot": "🤝",
    # Eggs
    "common_egg": "🥚", "mythical_egg": "🐣", "bug_egg": "🐣", "common_summer_egg": "🥚", "rare_summer_egg": "🥚", "paradise_egg": "🐣", "bee_egg": "🐣",
    # Cosmetics
    "sign_crate": "📦", "medium_wood_flooring": "🪵", "market_cart": "🛒",
    "yellow_umbrella": "☂️", "hay_bale": "🌾", "brick_stack": "🧱",
    "torch": "🔥", "stone_lantern": "🏮", "brown_bench": "🪑", "red_cooler_chest": "📦", "log_bench": "🛋️", "light_on_ground": "💡", "small_circle_tile": "⚪", "beach_crate": "📦", "blue_cooler_chest": "🧊", "large_wood_flooring": "🪚", "medium_stone_table": "🪨", "wood_pile": "🪵", "medium_path_tile": "🛤️", "shovel_grave": "⛏️", "frog_fountain": "🐸", "small_stone_lantern": "🕯️", "small_wood_table": "🪑", "medium_circle_tile": "🔘", "small_path_tile": "🔹", "mini_tv": "📺", "rock_pile": "🗿", "brown_stone_pillar": "🧱", "red_cooler_chest": "🧊", "bookshelf": "📚", "brown_bench": "🪑", "log_bench": "🪵"
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

WATCH_ITEMS = list(ITEM_EMOJI.keys())
last_seen = {item: None for item in WATCH_ITEMS}

# API endpoints
STOCK_API = "https://api.joshlei.com/v2/growagarden/stock"
WEATHER_API = "https://api.joshlei.com/v2/growagarden/weather"

# Fetch functions
def fetch_all_stock():
    try:
        r = requests.get(STOCK_API, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logging.error("Error fetching stock: %s", e)
        return {}

def fetch_weather():
    try:
        r = requests.get(WEATHER_API, timeout=10)
        r.raise_for_status()
        return r.json().get("weather", [])
    except Exception as e:
        logging.error("Error fetching weather: %s", e)
        return []

# Format functions
def format_block(key: str, items: list) -> str:
    if not items:
        return ""
    emoji = CATEGORY_EMOJI.get(key.replace("_stock", ""), "•")
    title = key.replace("_stock", "").capitalize()
    lines = [f"━ {emoji} *{title}* ━"]
    for it in items:
        em = ITEM_EMOJI.get(it.get('item_id'), "•")
        lines.append(f"   {em} {it.get('display_name')}: x{it.get('quantity',0)}")
    return "\n".join(lines) + "\n\n"

def format_weather_block(weather_list: list) -> str:
    active = next((w for w in weather_list if w.get('active')), None)
    if not active:
        return "━ ☁️ *Погода* ━\nНет активных погодных событий"
    name = active.get('weather_name')
    eid = active.get('weather_id')
    emoji = WEATHER_EMOJI.get(eid, "☁️")
    end_ts = active.get('end_duration_unix', 0)
    ends = datetime.fromtimestamp(end_ts, tz=ZoneInfo('Europe/Moscow')).strftime('%H:%M MSK') if end_ts else "--"
    dur = active.get('duration', 0)
    return (f"━ {emoji} *Погода* ━\n"
            f"*Текущая:* {name}\n"
            f"*Заканчивается в:* {ends}\n"
            f"*Длительность:* {dur} сек")

# Handlers
def start(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("📦 Стоки", callback_data='show_stock')],
        [InlineKeyboardButton("💄 Косметика", callback_data='show_cosmetic')],
        [InlineKeyboardButton("☁️ Погода", callback_data='show_weather')]
    ]
    update.message.reply_text("Привет! Выбери действие:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


def handle_stock(update: Update, context: CallbackContext):
    query = update.callback_query
    if query:
        query.answer()
        tgt = query.message
    else:
        tgt = update.message
    data = fetch_all_stock()
    now = datetime.now(tz=ZoneInfo('Europe/Moscow')).strftime('%d.%m.%Y %H:%M:%S MSK')
    text = f"*🕒 {now}*\n\n"
    for section in ['seed_stock','gear_stock','egg_stock']:
        text += format_block(section, data.get(section, []))
    tgt.reply_markdown(text)


def handle_cosmetic(update: Update, context: CallbackContext):
    query = update.callback_query
    if query:
        query.answer()
        tgt = query.message
    else:
        tgt = update.message
    data = fetch_all_stock()
    now = datetime.now(tz=ZoneInfo('Europe/Moscow')).strftime('%d.%m.%Y %H:%M:%S MSK')
    text = f"*🕒 {now}*\n\n" + format_block('cosmetic_stock', data.get('cosmetic_stock', []))
    tgt.reply_markdown(text)


def handle_weather(update: Update, context: CallbackContext):
    query = update.callback_query
    if query:
        query.answer()
        tgt = query.message
    else:
        tgt = update.message
    weather = fetch_weather()
    tgt.reply_markdown(format_weather_block(weather))

# Notification thread
def monitor_stock():
    data = fetch_all_stock()
    # initialize
    for sec in ['seed_stock','gear_stock','egg_stock','cosmetic_stock']:
        for it in data.get(sec,[]):
            if it['item_id'] in last_seen:
                last_seen[it['item_id']] = it['quantity']
    logging.info("Initial last_seen: %s", last_seen)
    # loop
    while True:
        data = fetch_all_stock()
        for sec in ['seed_stock','gear_stock','egg_stock','cosmetic_stock']:
            for it in data.get(sec,[]):
                iid, qty = it['item_id'], it['quantity']
                prev = last_seen.get(iid)
                if prev is not None and qty > 0 and qty != prev:
                    # notify expensive seeds
                    if iid in WATCH_ITEMS:
                        em = ITEM_EMOJI.get(iid, '•')
                        name = it['display_name']
                        now = datetime.now(tz=ZoneInfo('Europe/Moscow')).strftime('%d.%m.%Y %H:%M MSK')
                        msg = f"*{em} {name} в стоке!*🕒 {now}*Grow a Garden News. Подписаться (https://t.me/GroowAGarden)*"
                        bot.send_message(chat_id=CHANNEL_ID, text=msg, parse_mode='Markdown')
                last_seen[iid] = qty
        time.sleep(60)

# Register handlers
dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CallbackQueryHandler(handle_stock, pattern='show_stock'))
dispatcher.add_handler(CallbackQueryHandler(handle_cosmetic, pattern='show_cosmetic'))
dispatcher.add_handler(CallbackQueryHandler(handle_weather, pattern='show_weather'))

# Start monitoring thread
th = threading.Thread(target=monitor_stock, daemon=True)
th.start()

# Start the bot
if __name__ == '__main__':
    updater.start_polling()
    updater.idle()