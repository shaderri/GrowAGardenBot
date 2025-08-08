import types
import sys
import os
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
import threading
import asyncio

import requests
from flask import Flask
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s %(levelname)s:%(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

if "imghdr" not in sys.modules:
    mod = types.ModuleType("imghdr")
    mod.what = lambda *args, **kwargs: None
    sys.modules["imghdr"] = mod

load_dotenv()
BOT_TOKEN      = os.getenv("BOT_TOKEN")
CHANNEL_ID     = os.getenv("CHANNEL_ID")
KEEPALIVE_PORT = int(os.getenv("PORT", 10000))
JSTUDIO_KEY    = os.getenv("JSTUDIO_KEY")

STOCK_API   = "https://api.joshlei.com/v2/growagarden/stock"

CATEGORY_EMOJI = {
    "seed_stock":     "🌱",
    "gear_stock":     "🧰",
    "egg_stock":      "🥚",
    "cosmetic_stock": "💄",
}
ITEM_EMOJI = {
    "grape":"🍇","mushroom":"🍄","pepper":"🌶️","cacao":"🍫",
    "beanstalk":"🫛","ember_lily":"🌸","sugar_apple":"🍏",
    "burning_bud":"🔥","giant_pinecone":"🌰",
    "master_sprinkler":"🌧️","grandmaster_sprinkler":"💦",
    "levelup_lollipop":"🍭","elder_strawberry":"🍓",
    "paradise_egg":"🐣","bug_egg":"🐣",
}
ITEM_NAME_RU = {
    "paradise_egg":"Райское яйцо","bug_egg":"Яйцо жука",
    "grape":"Виноград","mushroom":"Грибы","pepper":"Перец",
    "cacao":"Какао","beanstalk":"Бобовый стебель",
    "ember_lily":"Эмбер лили","sugar_apple":"Сахарное яблоко",
    "burning_bud":"Горящий бутон","giant_pinecone":"Гигантская шишка",
    "master_sprinkler":"Мастер-спринклер",
    "grandmaster_sprinkler":"Грандмастер-спринклер",
    "levelup_lollipop":"Леденец уровня","elder_strawberry":"Бузинная клубника",
}
NOTIFY_ITEMS = list(ITEM_EMOJI.keys())
PRICE_MAP = {
    "paradise_egg":50_000_000,"bug_egg":50_000_000,
    "grape":850_000,"mushroom":150_000,"pepper":1_000_000,
    "cacao":2_500_000,"beanstalk":10_000_000,
    "ember_lily":15_000_000,"sugar_apple":25_000_000,
    "burning_bud":40_000_000,"giant_pinecone":55_000_000,
    "master_sprinkler":10_000_000,"grandmaster_sprinkler":1_000_000_000,
    "levelup_lollipop":10_000_000_000,"elder_strawberry":70_000_000
}

flask_app = Flask(__name__)
@flask_app.route("/")
def home():
    return "Bot is running", 200

def run_flask():
    flask_app.run(host="0.0.0.0", port=KEEPALIVE_PORT)

def fetch_all_stock():
    try:
        resp = requests.get(
            STOCK_API,
            headers={"jstudio-key": JSTUDIO_KEY},
            timeout=10
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Stock fetch error: {e}")
        return {}

def format_block(key: str, items: list) -> str:
    if not items:
        return ""
    emoji = CATEGORY_EMOJI.get(key, "•")
    title = key.replace("_stock", "").capitalize()
    lines = [f"━ {emoji} *{title}* ━"]
    for it in items:
        em = ITEM_EMOJI.get(it["item_id"], "•")
        lines.append(f"   {em} {it['display_name']}: x{it['quantity']}")
    return "\n".join(lines) + "\n\n"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("📦 Стоки",    callback_data="show_stock")],
        [InlineKeyboardButton("💄 Косметика", callback_data="show_cosmetic")],
    ]
    await update.message.reply_text("Привет! Выбери действие:", reply_markup=InlineKeyboardMarkup(kb))

async def handle_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tgt = update.callback_query.message if update.callback_query else update.message
    if update.callback_query:
        await update.callback_query.answer()
    data = fetch_all_stock()
    now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime("%H:%M:%S MSK")
    text = f"*🕒 {now}*\n\n"
    for sec in ["seed_stock", "gear_stock", "egg_stock", "cosmetic_stock"]:
        text += format_block(sec, data.get(sec, []))
    await tgt.reply_markdown(text)

last_qty = {}
last_in_stock = {}

async def monitor_job(context: ContextTypes.DEFAULT_TYPE):
    data = fetch_all_stock()
    if not data:
        return
    now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime("%H:%M:%S MSK")
    messages_to_send = []
    for sec in ["seed_stock", "gear_stock", "egg_stock", "cosmetic_stock"]:
        for it in data.get(sec, []):
            iid, qty = it['item_id'], it['quantity']
            prev_qty = last_qty.get(iid, 0)
            was_in = last_in_stock.get(iid, False)
            now_in = qty > 0
            if iid in NOTIFY_ITEMS and (now_in and not was_in or qty > prev_qty):
                name_ru = ITEM_NAME_RU.get(iid, it['display_name'])
                emoji = ITEM_EMOJI.get(iid, "")
                price = PRICE_MAP.get(iid, 0)
                msg = (
                    f"*{emoji} {name_ru}: x{qty} в стоке!*\n"
                    f"💰 Цена — {price:,}¢\n"
                    f"🕒 {now}\n\n*@GroowAGarden*"
                )
                messages_to_send.append(msg)
            last_qty[iid] = qty
            last_in_stock[iid] = now_in
    for msg in messages_to_send:
        await context.bot.send_message(chat_id=CHANNEL_ID, text=msg, parse_mode="Markdown")

app = (
    ApplicationBuilder()
    .token(BOT_TOKEN)
    .build()
)

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("stock", handle_stock))
app.add_handler(CallbackQueryHandler(handle_stock, pattern="show_stock"))

app.job_queue.run_repeating(monitor_job, interval=10, first=10)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    app.run_polling()