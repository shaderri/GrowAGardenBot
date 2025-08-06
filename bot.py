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
import jstudio
from zoneinfo import ZoneInfo
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes
)
from flask import Flask
import threading

# Load environment variables
load_dotenv()
BOT_TOKEN    = os.getenv("BOT_TOKEN")
CHANNEL_ID   = os.getenv("CHANNEL_ID")
KEEPALIVE_PORT = int(os.getenv("PORT", 10000))
JSTUDIO_KEY  = os.getenv("JSTUDIO_KEY")

# Connect to JStudio API
client = jstudio.connect(
    api_key=JSTUDIO_KEY,
    # base_url="https://api.joshlei.com",  # опционально
    timeout=30,
    retries=3,
    retry_delay=1.0
)  # :contentReference[oaicite:1]{index=1}

# Flask app to keep bot alive
flask_app = Flask(__name__)
@flask_app.route('/')
def home():
    return 'Bot is running', 200

def run_flask():
    flask_app.run(host="0.0.0.0", port=KEEPALIVE_PORT)

# Emoji mappings
CATEGORY_EMOJI = {
    "seeds": "🌱", "gear": "🧰", "eggs": "🥚",
    "cosmetic": "💄", "weather": "☁️"
}
ITEM_EMOJI = {
    "grape": "🍇", "mushroom": "🍄", "pepper": "🌶️",
    "cacao": "🍫", "beanstalk": "🫛", "ember_lily": "🌸",
    "sugar_apple": "🍏", "burning_bud": "🔥",
    "giant_pinecone": "🌰", "master_sprinkler": "🌧️",
    "grandmaster_sprinkler": "💦",
    "levelup_lollipop": "🍭", "elder_strawberry": "🍓",
    "paradise_egg": "🐣", "bug_egg": "🐣"
}
ITEM_NAME_RU = {
    "paradise_egg": "Райское яйцо", "bug_egg": "Яйцо жука",
    "grape": "Виноград", "mushroom": "Грибы",
    "pepper": "Перец", "cacao": "Какао",
    "beanstalk": "Бобовый стебель", "ember_lily": "Эмбер лили",
    "sugar_apple": "Сахарное яблоко", "burning_bud": "Горящий бутон",
    "giant_pinecone": "Гигантская шишка",
    "master_sprinkler": "Мастер-спринклер",
    "grandmaster_sprinkler": "Грандмастер-спринклер",
    "levelup_lollipop": "Леденец уровня",
    "elder_strawberry": "Бузинная клубника"
}
NOTIFY_ITEMS = [
    "grape","mushroom","pepper","cacao","beanstalk","ember_lily",
    "sugar_apple","burning_bud","giant_pinecone",
    "master_sprinkler","grandmaster_sprinkler",
    "levelup_lollipop","elder_strawberry",
    "paradise_egg","bug_egg"
]
PRICE_MAP = {
    "paradise_egg":50_000_000,"bug_egg":50_000_000,
    "grape":850_000,"mushroom":150_000,"pepper":1_000_000,
    "cacao":2_500_000,"beanstalk":10_000_000,
    "ember_lily":15_000_000,"sugar_apple":25_000_000,
    "burning_bud":40_000_000,"giant_pinecone":55_000_000,
    "master_sprinkler":10_000_000,"grandmaster_sprinkler":1_000_000_000,
    "levelup_lollipop":10_000_000_000,"elder_strawberry":70_000_000
}

# Formatters
def format_block(key: str, items: list) -> str:
    if not items: return ""
    emoji = CATEGORY_EMOJI.get(key.replace("_stock",""), "•")
    title = key.replace("_stock","").capitalize()
    lines = [f"━ {emoji} *{title}* ━"]
    for it in items:
        em = ITEM_EMOJI.get(it["item_id"], "•")
        lines.append(f"   {em} {it['display_name']}: x{it['quantity']}")
    return "\n".join(lines) + "\n\n"

def format_weather_block() -> str:
    active = client.weather.active()
    if not active:
        return "━ ☁️ *Погода* ━\nНет активных погодных событий"
    w = active[0]
    ends = datetime.fromtimestamp(
        w.get("end_duration_unix",0),
        tz=ZoneInfo("Europe/Moscow")
    ).strftime("%H:%M:%S MSK") if w.get("end_duration_unix") else "--"
    return (f"━ ☁️ *Погода* ━\n"
            f"*Текущая:* {w['weather_name']}\n"
            f"*Заканчивается в:* {ends}\n"
            f"*Длительность:* {w.get('duration',0)} сек")

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("📦 Стоки",   callback_data="show_stock")],
        [InlineKeyboardButton("💄 Косметика", callback_data="show_cosmetic")],
        [InlineKeyboardButton("☁️ Погода",    callback_data="show_weather")]
    ]
    await update.message.reply_text("Привет! Выбери действие:",
                                    reply_markup=InlineKeyboardMarkup(kb))

async def handle_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        tgt = update.callback_query.message
    else:
        tgt = update.message
    data = client.stocks.all()
    now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime("%H:%M:%S MSK")
    text = f"*🕒 {now}*\n\n"
    for sec in ["seed_stock","gear_stock","egg_stock"]:
        text += format_block(sec, data.get(sec, []))
    await tgt.reply_markdown(text)

async def handle_cosmetic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        tgt = update.callback_query.message
    else:
        tgt = update.message
    data = client.stocks.cosmetics()
    now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime("%H:%M:%S MSK")
    text = f"*🕒 {now}*\n\n" + format_block("cosmetic_stock", data)
    await tgt.reply_markdown(text)

async def handle_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        tgt = update.callback_query.message
    else:
        tgt = update.message
    await tgt.reply_markdown(format_weather_block())

# Monitoring task
last_qty = {}

async def monitor_stock_changes(app):
    while True:
        await asyncio.sleep(10)
        data = client.stocks.all()
        now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime("%H:%M:%S MSK")
        for sec in ["seed_stock","gear_stock","cosmetic_stock","egg_stock"]:
            for it in data.get(sec, []):
                iid, qty = it["item_id"], it["quantity"]
                prev = last_qty.get(iid, 0)
                if qty > prev and iid in NOTIFY_ITEMS:
                    name_ru = ITEM_NAME_RU.get(iid, it["display_name"])
                    emoji   = ITEM_EMOJI.get(iid, "")
                    price   = PRICE_MAP.get(iid, 0)
                    msg = (f"*{emoji} {name_ru}: x{qty} в стоке!*\n"
                           f"💰 Цена — {price:,}¢\n"
                           f"🕒 {now}\n\n*@GrowAGarden*")
                    await app.bot.send_message(
                        chat_id=CHANNEL_ID,
                        text=msg,
                        parse_mode="Markdown"
                    )
                last_qty[iid] = qty

async def post_init(app):
    app.create_task(monitor_stock_changes(app))

# Application setup
app = ApplicationBuilder()\
      .token(BOT_TOKEN)\
      .post_init(post_init)\
      .build()

app.add_handler(CommandHandler("start",    start))
app.add_handler(CommandHandler("stock",    handle_stock))
app.add_handler(CommandHandler("cosmetic", handle_cosmetic))
app.add_handler(CommandHandler("weather",  handle_weather))
app.add_handler(CallbackQueryHandler(handle_stock,    pattern="show_stock"))
app.add_handler(CallbackQueryHandler(handle_cosmetic, pattern="show_cosmetic"))
app.add_handler(CallbackQueryHandler(handle_weather,  pattern="show_weather"))

if __name__ == "__main__":
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    app.run_polling()