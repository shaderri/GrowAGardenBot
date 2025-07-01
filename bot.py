import os
import requests
from datetime import datetime
from dotenv import load_dotenv
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
)

# Загрузим переменные окружения
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID")

# Новый API URL без необходимости в ключе
API_URL = "https://www.gamersberg.com/api/grow-a-garden/stock"

# Эмодзи по категориям
CATEGORY_EMOJI = {
    "seeds":    "🌱",
    "cosmetic": "💎",
    "gear":     "🧰",
    "event":    "🌴",
    "eggs":     "🥚",
}

# Эмодзи по названию предметов (расширяй по желанию)
ITEM_EMOJI = {
    # Seeds
    "Feijoa": "🥝",
    "Kiwi": "🥝",
    "Avocado": "🥑",
    "Sugar Apple": "🍏",
    "Tomato": "🍅",
    "Bell Pepper": "🌶️",
    "Pitcher Plant": "🌱",
    "Prickly Pear": "🌵",
    "Cauliflower": "🥦",
    "Blueberry": "🫐",
    "Carrot": "🥕",
    "Loquat": "🍑",
    "Green Apple": "🍏",
    "Strawberry": "🍓",
    "Watermelon": "🍉",
    "Banana": "🍌",
    "Rafflesia": "🌺",
    "Pineapple": "🍍",
    # Cosmetic
    "Green Tractor": "🚜",
    "Large Wood Flooring": "🪵",
    "Sign Crate": "📦",
    "Small Wood Table": "🪑",
    "Large Path Tile": "🛤️",
    "Medium Path Tile": "⬛",
    "Wood Fence": "🪵",
    "Axe Stump": "🪨",
    "Shovel": "🪓",
    # Gear
    "Advanced Sprinkler": "💦",
    "Master Sprinkler": "💧",
    "Basic Sprinkler": "🌦️",
    "Godly Sprinkler": "⚡",
    "Trowel": "⛏️",
    "Harvest Tool": "🧲",
    "Cleaning Spray": "🧴",
    "Recall Wrench": "🔧",
    "Favorite Tool": "❤️",
    "Watering Can": "🚿",
    "Magnifying Glass": "🔍",
    "Tanning Mirror": "🪞",
    "Friendship Pot": "🌻",
    # Event (Summer Stock)
    "Hamster": "🐹",
    "Summer Seed Pack": "🌞",
    "Oasis Crate": "🏝️",
    "Traveler's Fruit": "✈️",
    "Delphinium": "🌸",
    "Oasis Egg": "🥚",
    "Lily of the Valley": "💐",
    "Mutation Spray Burnt": "🔥",
    # Eggs list entries
    "Common Egg": "🥚",
    # Пропускаем "Location"
}

# Форматирование блока любой категории (кроме яиц)
def format_dict_block(name: str, data: dict) -> str:
    # Пропускаем нулевые количества
    filtered = {k: v for k, v in data.items() if int(v) > 0}
    if not filtered:
        return ""

    # Для event переименуем в Summer Stock
    title = "Summer Stock" if name == "event" else f"{name.capitalize()} Stock"
    text = f"━ {CATEGORY_EMOJI.get(name, '')} {title} ━\n"
    for item, qty in filtered.items():
        emoji = ITEM_EMOJI.get(item, "•")
        text += f"   {emoji} {item}: x{qty}\n"
    return text + "\n"

# Форматирование блока яиц (список словарей)
def format_eggs_block(eggs: list) -> str:
    # Пропуск "Location" и нулевых
    eggs_filtered = [e for e in eggs if e.get("name") != "Location" and int(e.get("quantity", 0)) > 0]
    if not eggs_filtered:
        return ""

    text = f"━ {CATEGORY_EMOJI.get('eggs')} Egg Stock ━\n"
    for egg in eggs_filtered:
        name = egg.get("name")
        qty  = egg.get("quantity")
        emoji = ITEM_EMOJI.get(name, "🥚")
        text += f"   {emoji} {name}: x{qty}\n"
    return text + "\n"

# Клавиатура для запроса стоков
def get_keyboard():
    button = InlineKeyboardButton("📦 Показать стоки", callback_data="show_stocks")
    return InlineKeyboardMarkup([[button]])

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Нажми кнопку ниже, чтобы получить актуальный сток:",
        reply_markup=get_keyboard()
    )

async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    # Получаем JSON
    resp = requests.get(API_URL)
    data = resp.json().get("data", [])
    if not data:
        await update.callback_query.message.reply_text("❌ Не удалось получить данные")
        return
    info = data[0]

    # Таймштамп из поля timestamp
    ts = int(info.get("timestamp", 0))
    now = datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M:%S")

    text = f"🕒 {now}\n\n"
    text += "📊 *Все стоки Grow a Garden:*\n\n"
    # Добавляем секции, пропуская пустые
    text += format_dict_block("seeds", info.get("seeds", {}))
    text += format_dict_block("cosmetic", info.get("cosmetic", {}))
    text += format_dict_block("gear", info.get("gear", {}))
    text += format_dict_block("event", info.get("event", {}))
    text += format_eggs_block(info.get("eggs", []))

    await update.callback_query.message.reply_markdown(text)

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(on_button, pattern="show_stocks"))
    print("Bot running…")
    app.run_polling()