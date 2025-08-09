# bot_render_safe.py
import os
import sys
import signal
import logging
import threading
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Tuple

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

# ====== Настройка логов ======
logging.basicConfig(
    format="%(asctime)s %(levelname)s:%(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("growagarden-bot")

# ====== Переменные окружения ======
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID_ENV = os.getenv("CHANNEL_ID")
KEEPALIVE_PORT = int(os.getenv("PORT", 10000))
JSTUDIO_KEY = os.getenv("JSTUDIO_KEY")

def parse_channel_id(val: str):
    if val is None:
        return None
    s = val.strip()
    if s.startswith("@"):
        return s
    try:
        return int(s)
    except Exception:
        return s

CHANNEL_ID = parse_channel_id(CHANNEL_ID_ENV)

# ====== Конфигурация API и карты ======
STOCK_API = "https://api.joshlei.com/v2/growagarden/stock"

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

# ====== Flask keepalive ======
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Bot is running", 200

# ====== Lock (PID file) ======
LOCK_FILE = "/tmp/growagarden_bot.lock"

def is_pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False
    return True

def acquire_lock_or_exit():
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r") as f:
                data = f.read().strip()
                pid = int(data) if data else None
        except Exception:
            pid = None

        if pid and is_pid_running(pid):
            logger.warning("Lock file %s exists and PID %s is running -> второй экземпляр не будет запущен.", LOCK_FILE, pid)
            sys.exit(0)
        else:
            logger.info("Lock file %s existed but PID not running -> удаляем stale lock.", LOCK_FILE)
            try:
                os.remove(LOCK_FILE)
            except Exception:
                pass

    try:
        with open(LOCK_FILE, "w") as f:
            f.write(str(os.getpid()))
        logger.info("Создан lock с PID %s", os.getpid())
    except Exception as e:
        logger.exception("Не удалось создать lock file: %s", e)
        sys.exit(1)

def remove_lock():
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
            logger.info("Lock %s удалён", LOCK_FILE)
    except Exception as e:
        logger.exception("Ошибка при удалении lock: %s", e)

# ====== Сетевые вызовы ======
def _sync_fetch_stock_once() -> Dict[str, Any]:
    headers = {"jstudio-key": JSTUDIO_KEY} if JSTUDIO_KEY else {}
    resp = requests.get(STOCK_API, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()

def _sync_fetch_stock_with_retries(retries: int = 2) -> Dict[str, Any]:
    last_exc = None
    for i in range(retries + 1):
        try:
            return _sync_fetch_stock_once()
        except Exception as e:
            last_exc = e
            logger.warning("fetch attempt %d failed: %s", i+1, e)
    logger.exception("All fetch attempts failed: %s", last_exc)
    return {}

async def fetch_all_stock() -> Dict[str, Any]:
    return await asyncio.to_thread(_sync_fetch_stock_with_retries)

# ====== Форматирование ======
def format_block(key: str, items: list) -> str:
    if not items:
        return ""
    emoji = CATEGORY_EMOJI.get(key, "•")
    title = key.replace("_stock", "").capitalize()
    lines = [f"━ {emoji} <b>{title}</b> ━"]
    for it in items:
        em = ITEM_EMOJI.get(it.get("item_id"), "•")
        display = it.get("display_name") or it.get("item_id") or "Unknown"
        qty = it.get("quantity", 0)
        lines.append(f"   {em} {display}: x{qty}")
    return "\n".join(lines) + "\n\n"

# ====== Очередь сообщений и состояние ======
messages_queue: List[Tuple[str, int, str]] = []
recently_sent: Dict[str, int] = {}
last_qty: Dict[str, int] = {}
last_in_stock: Dict[str, bool] = {}
monitor_lock = asyncio.Lock()

# ====== Handlers ======
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("📦 Стоки", callback_data="show_stock")],
        [InlineKeyboardButton("💄 Косметика", callback_data="show_cosmetic")],
    ]
    try:
        await update.message.reply_text("Бот запущен. Используй /stock для ручного запроса.", reply_markup=InlineKeyboardMarkup(kb))
    except Exception:
        pass

async def handle_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tgt = update.callback_query.message if update.callback_query else update.message
    if update.callback_query:
        await update.callback_query.answer()
    data = await fetch_all_stock()
    now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime("%H:%M:%S MSK")
    text = f"🕒 <b>{now}</b>\n\n"
    for sec in ["seed_stock", "gear_stock", "egg_stock", "cosmetic_stock"]:
        text += format_block(sec, data.get(sec, []))
    await tgt.reply_text(text, parse_mode="HTML")

# ====== Отправка с fallback ======
async def send_with_retries_and_fallback(bot, chat_id, text_html: str, attempts: int = 3):
    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            await bot.send_message(chat_id=chat_id, text=text_html, parse_mode="HTML")
            return True
        except Exception as e:
            last_exc = e
            logger.warning("send attempt %d failed: %s", attempt, e)
            if attempt == attempts:
                try:
                    await bot.send_message(chat_id=chat_id, text=text_html)
                    return True
                except Exception as e2:
                    logger.exception("Final fallback send also failed: %s", e2)
                    return False
            await asyncio.sleep(0.5 * attempt)
    logger.exception("All send attempts failed, last error: %s", last_exc)
    return False

# ====== monitor_job (кладёт в очередь) ======
async def monitor_job(context: ContextTypes.DEFAULT_TYPE):
    if monitor_lock.locked():
        logger.info("monitor_job пропущен: предыдущий ещё выполняется")
        return

    async with monitor_lock:
        try:
            data = await fetch_all_stock()
            if not data:
                logger.debug("fetch_all_stock вернул пусто — пропускаем")
                return

            now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime("%H:%M:%S MSK")
            new_messages: List[Tuple[str, int, str]] = []
            local_qty_updates: Dict[str, int] = {}
            local_instock_updates: Dict[str, bool] = {}

            for sec in ["seed_stock", "gear_stock", "egg_stock", "cosmetic_stock"]:
                for it in data.get(sec, []):
                    iid = it.get("item_id")
                    if iid is None:
                        continue
                    try:
                        qty = int(it.get("quantity", 0))
                    except Exception:
                        qty = 0
                    prev_qty = last_qty.get(iid, 0)
                    was_in = last_in_stock.get(iid, False)
                    now_in = qty > 0

                    if iid in NOTIFY_ITEMS and ((now_in and not was_in) or (qty > prev_qty)):
                        name_ru = ITEM_NAME_RU.get(iid, it.get('display_name') or iid)
                        emoji = ITEM_EMOJI.get(iid, "")
                        price = PRICE_MAP.get(iid, 0)
                        price_str = f"{price:,}" if isinstance(price, int) else str(price)
                        text_html = (
                            f"<b>{emoji} {name_ru}: x{qty} в стоке!</b>\n"
                            f"💰 Цена — {price_str}¢\n"
                            f"🕒 {now}\n\n@GroowAGarden"
                        )
                        last_sent_qty = recently_sent.get(iid)
                        if last_sent_qty is not None and last_sent_qty == qty:
                            logger.info("Дубликат по количеству для %s (qty=%s) — пропускаем enqueue", iid, qty)
                        else:
                            new_messages.append((iid, qty, text_html))
                            logger.info("Enqueue: %s qty=%s (prev=%s, was_in=%s->now_in=%s)", iid, qty, prev_qty, was_in, now_in)

                    local_qty_updates[iid] = qty
                    local_instock_updates[iid] = now_in

            last_qty.update(local_qty_updates)
            last_in_stock.update(local_instock_updates)

            if new_messages:
                before = len(messages_queue)
                messages_queue.extend(new_messages)
                logger.info("Добавлено %d сообщений в очередь (до=%d, после=%d)", len(new_messages), before, len(messages_queue))
        except Exception as e:
            logger.exception("Ошибка в monitor_job: %s", e)

# ====== sender_job (отправляет очередь) ======
async def sender_job(context: ContextTypes.DEFAULT_TYPE):
    if not messages_queue:
        return
    MAX_PER_PASS = 20
    to_send = []
    while messages_queue and len(to_send) < MAX_PER_PASS:
        to_send.append(messages_queue.pop(0))

    logger.info("Sender job: отправляем %d сообщений (оставшихся в очереди: %d)", len(to_send), len(messages_queue))
    for iid, qty, text_html in to_send:
        try:
            ok = await send_with_retries_and_fallback(context.bot, CHANNEL_ID, text_html, attempts=3)
            if ok:
                recently_sent[iid] = qty
                logger.info("Sent: %s qty=%s", iid, qty)
            else:
                messages_queue.append((iid, qty, text_html))
                logger.warning("Не удалось отправить %s — возвращаем в очередь (длина сейчас %d)", iid, len(messages_queue))
            await asyncio.sleep(0.25)
        except Exception as e:
            logger.exception("Ошибка при отправке %s: %s — возвращаем в очередь", iid, e)
            messages_queue.append((iid, qty, text_html))

# ====== Функция запуска бота (в отдельном потоке) ======
def run_bot():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не задан — выходим.")
        return

    # Создаём и привязываем event loop к этому потоку
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    logger.info("New event loop created for bot thread: %s", loop)

    # Будем пытаться перезапускать polling, если он упадёт
    while True:
        try:
            app = ApplicationBuilder().token(BOT_TOKEN).build()
            app.add_handler(CommandHandler("start", start_handler))
            app.add_handler(CommandHandler("stock", handle_stock))
            app.add_handler(CallbackQueryHandler(handle_stock, pattern="show_stock"))
            app.add_handler(CallbackQueryHandler(handle_stock, pattern="show_cosmetic"))

            # job_queue
            app.job_queue.run_repeating(monitor_job, interval=10, first=5)
            app.job_queue.run_repeating(sender_job, interval=1, first=7)

            logger.info("Запуск polling в background thread...")
            # blocking call; если он будет падать, перейдём в except и перезапустим через паузу
            app.run_polling()
            # Если run_polling вернул (корректно завершился), выходим из цикла
            logger.info("app.run_polling() завершился корректно — выходим из run_bot loop")
            break
        except Exception as e:
            logger.exception("Ошибка в run_polling: %s", e)
            logger.info("Пробуем перезапустить polling через 5 секунд...")
            try:
                # небольшая пауза перед повторной попыткой
                import time
                time.sleep(5)
            except Exception:
                pass
    # НЕ удаляем lock здесь — main() удалит lock при завершении всего процесса

# ====== Обработка сигналов ======
def handle_termination(signum, frame):
    logger.info("Получен сигнал %s — завершаем процесс.", signum)
    remove_lock()
    os._exit(0)

signal.signal(signal.SIGINT, handle_termination)
signal.signal(signal.SIGTERM, handle_termination)

# ====== Main: acquire lock, стартуем bot в потоке, запускаем flask (главный поток) ======
def main():
    acquire_lock_or_exit()

    # старт бота в фоновом потоке
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    logger.info("Bot thread started (daemon). Запускаем Flask в основном потоке на порту %s", KEEPALIVE_PORT)

    # Запуск Flask в основном потоке (Render ожидает работающий web service)
    try:
        flask_app.run(host="0.0.0.0", port=KEEPALIVE_PORT)
    except Exception as e:
        logger.exception("Flask stopped with error: %s", e)
    finally:
        remove_lock()

if __name__ == "__main__":
    main()