import asyncio
import aiohttp
import logging
import os
import json
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Set
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
from telegram.constants import ParseMode
from dotenv import load_dotenv
from flask import Flask
import pytz

# Загружаем переменные окружения
load_dotenv()

# ========== КОНФИГУРАЦИЯ ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@GroowAGarden")
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://tcsmfiixhflzrxkrbslk.supabase.co")
SUPABASE_API_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRjc21maWl4aGZsenJ4a3Jic2xrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjA1MDUzOTYsImV4cCI6MjA3NjA4MTM5Nn0.VcAK7QYvUFuKd96OgOdadS2s_9N08pYt9mMIu73Jeiw")

AUTOSTOCKS_URL = f"{SUPABASE_URL}/rest/v1/user_autostocks"

# API игры
GAG_API_BASE = "https://gagapi.onrender.com"
SEEDS_API = f"{GAG_API_BASE}/seeds"
GEAR_API = f"{GAG_API_BASE}/gear"
COSMETICS_API = f"{GAG_API_BASE}/cosmetics"
EGGS_API = f"{GAG_API_BASE}/eggs"
WEATHER_API = f"{GAG_API_BASE}/weather"

CHECK_INTERVAL_MINUTES = 5
AUTOSTOCK_CACHE_TTL = 60

# Два самых редких семена для уведомлений в канал
RAREST_SEEDS = ["Crimson Thorn", "Great Pumpkin"]

# ========== ДАННЫЕ ПРЕДМЕТОВ ==========
SEEDS_DATA = {
    "Carrot": {"emoji": "🥕", "price": "10"},
    "Strawberry": {"emoji": "🍓", "price": "50"},
    "Blueberry": {"emoji": "🫐", "price": "400"},
    "Orange Tulip": {"emoji": "🧡", "price": "600"},
    "Tomato": {"emoji": "🍅", "price": "800"},
    "Corn": {"emoji": "🌽", "price": "1,300"},
    "Daffodil": {"emoji": "🌼", "price": "1,000"},
    "Watermelon": {"emoji": "🍉", "price": "2,500"},
    "Pumpkin": {"emoji": "🎃", "price": "3,000"},
    "Apple": {"emoji": "🍎", "price": "3,250"},
    "Bamboo": {"emoji": "🎋", "price": "4,000"},
    "Coconut": {"emoji": "🥥", "price": "6,000"},
    "Cactus": {"emoji": "🌵", "price": "15,000"},
    "Dragon Fruit": {"emoji": "🐉", "price": "50,000"},
    "Mango": {"emoji": "🥭", "price": "100,000"},
    "Grape": {"emoji": "🍇", "price": "850,000"},
    "Mushroom": {"emoji": "🍄", "price": "150,000"},
    "Pepper": {"emoji": "🌶️", "price": "1,000,000"},
    "Cacao": {"emoji": "🍫", "price": "2,500,000"},
    "Beanstalk": {"emoji": "🪜", "price": "10,000,000"},
    "Ember Lily": {"emoji": "🔥", "price": "15,000,000"},
    "Sugar Apple": {"emoji": "🍎", "price": "25,000,000"},
    "Burning Bud": {"emoji": "🔥", "price": "40,000,000"},
    "Giant Pinecone": {"emoji": "🌲", "price": "55,000,000"},
    "Elder Strawberry": {"emoji": "🍓", "price": "70,000,000"},
    "Romanesco": {"emoji": "🥦", "price": "88,000,000"},
    "Crimson Thorn": {"emoji": "🌹", "price": "10,000,000,000"},
    "Great Pumpkin": {"emoji": "🎃", "price": "15,000,000,000"},
}

GEAR_DATA = {
    "Watering Can": {"emoji": "💧", "price": "50,000"},
    "Trowel": {"emoji": "🔨", "price": "100,000"},
    "Trading Ticket": {"emoji": "🎫", "price": "100,000"},
    "Recall Wrench": {"emoji": "🔧", "price": "150,000"},
    "Basic Sprinkler": {"emoji": "💦", "price": "25,000"},
    "Advanced Sprinkler": {"emoji": "💦", "price": "50,000"},
    "Medium Treat": {"emoji": "🍖", "price": "4,000,000"},
    "Medium Toy": {"emoji": "🎮", "price": "4,000,000"},
    "Godly Sprinkler": {"emoji": "✨", "price": "120,000"},
    "Magnifying Glass": {"emoji": "🔍", "price": "10,000,000"},
    "Master Sprinkler": {"emoji": "👑", "price": "10,000,000"},
    "Cleaning Spray": {"emoji": "🧼", "price": "15,000,000"},
    "Favorite Tool": {"emoji": "⭐", "price": "20,000,000"},
    "Harvest Tool": {"emoji": "✂️", "price": "30,000,000"},
    "Friendship Pot": {"emoji": "🪴", "price": "15,000,000"},
    "Level Up Lollipop": {"emoji": "🍭", "price": "10,000,000,000"},
    "Grandmaster Sprinkler": {"emoji": "🏆", "price": "1,000,000,000"},
}

EGGS_DATA = {
    "Common Egg": {"emoji": "🥚", "price": "50,000"},
    "Uncommon Egg": {"emoji": "🟡", "price": "150,000"},
    "Rare Egg": {"emoji": "🔵", "price": "600,000"},
    "Legendary Egg": {"emoji": "💜", "price": "3,000,000"},
    "Mythical Egg": {"emoji": "🌈", "price": "8,000,000"},
    "Bug Egg": {"emoji": "🐛", "price": "50,000,000"},
    "Jungle Egg": {"emoji": "🦜", "price": "60,000,000"},
}

# ========== КЭШИРОВАНИЕ ==========
user_autostocks_cache: Dict[int, Set[str]] = {}
user_autostocks_time: Dict[int, datetime] = {}
last_stock_state: Dict[str, int] = {}

# ========== ЛОГИРОВАНИЕ ==========
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== FLASK ДЛЯ UPTIME ROBOT ==========
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is running!", 200

@flask_app.route('/health')
def health():
    return "OK", 200

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    flask_app.run(host='0.0.0.0', port=port)

# ========== УТИЛИТЫ ==========
def get_moscow_time() -> datetime:
    """Получить текущее московское время"""
    return datetime.now(pytz.timezone('Europe/Moscow'))

def format_moscow_time() -> str:
    """Форматировать московское время"""
    return get_moscow_time().strftime('%H:%M:%S')

class SupabaseDB:
    """Работа с Supabase для автостоков"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.headers = {
            "apikey": SUPABASE_API_KEY,
            "Authorization": f"Bearer {SUPABASE_API_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
    
    async def init_session(self):
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=20, connect=10, sock_read=10)
            )
    
    async def close_session(self):
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def load_user_autostocks(self, user_id: int, use_cache: bool = True) -> Set[str]:
        """Загрузка автостоков с кэшированием (TTL 60 сек)"""
        if use_cache and user_id in user_autostocks_cache:
            cache_time = user_autostocks_time.get(user_id)
            if cache_time:
                now = get_moscow_time()
                if (now - cache_time).total_seconds() < AUTOSTOCK_CACHE_TTL:
                    return user_autostocks_cache[user_id].copy()
        
        try:
            await self.init_session()
            params = {"user_id": f"eq.{user_id}", "select": "item_name"}
            
            async with self.session.get(AUTOSTOCKS_URL, headers=self.headers, params=params, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    items_set = {item['item_name'] for item in data}
                    
                    user_autostocks_cache[user_id] = items_set
                    user_autostocks_time[user_id] = get_moscow_time()
                    
                    return items_set
                return set()
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки автостоков: {e}")
            return set()
    
    async def save_user_autostock(self, user_id: int, item_name: str) -> bool:
        """Сохранение автостока"""
        if user_id not in user_autostocks_cache:
            user_autostocks_cache[user_id] = set()
        user_autostocks_cache[user_id].add(item_name)
        user_autostocks_time[user_id] = get_moscow_time()
        
        try:
            await self.init_session()
            data = {"user_id": user_id, "item_name": item_name}
            
            async with self.session.post(AUTOSTOCKS_URL, json=data, headers=self.headers, timeout=5) as response:
                return response.status in [200, 201]
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения: {e}")
            return False
    
    async def remove_user_autostock(self, user_id: int, item_name: str) -> bool:
        """Удаление автостока"""
        if user_id in user_autostocks_cache:
            user_autostocks_cache[user_id].discard(item_name)
            user_autostocks_time[user_id] = get_moscow_time()
        
        try:
            await self.init_session()
            params = {"user_id": f"eq.{user_id}", "item_name": f"eq.{item_name}"}
            
            async with self.session.delete(AUTOSTOCKS_URL, headers=self.headers, params=params, timeout=5) as response:
                return response.status in [200, 204]
        except Exception as e:
            logger.error(f"❌ Ошибка удаления: {e}")
            return False
    
    async def get_users_tracking_item(self, item_name: str) -> List[int]:
        """Получить пользователей, отслеживающих предмет"""
        try:
            await self.init_session()
            params = {"item_name": f"eq.{item_name}", "select": "user_id"}
            
            async with self.session.get(AUTOSTOCKS_URL, headers=self.headers, params=params, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    return [item['user_id'] for item in data]
                return []
        except Exception as e:
            logger.error(f"❌ Ошибка получения пользователей: {e}")
            return []

class StockTracker:
    """Отслеживание стока игры"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.db = SupabaseDB()
    
    async def init_session(self):
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()
    
    async def close_session(self):
        if self.session and not self.session.closed:
            await self.session.close()
        await self.db.close_session()
    
    async def fetch_api(self, url: str) -> Optional[List[Dict]]:
        """Запрос к API игры"""
        try:
            await self.init_session()
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    return await response.json()
                return None
        except Exception as e:
            logger.error(f"❌ Ошибка API: {e}")
            return None
    
    async def fetch_seeds(self) -> Optional[List[Dict]]:
        """Получение стока семян"""
        return await self.fetch_api(SEEDS_API)
    
    async def fetch_gear(self) -> Optional[List[Dict]]:
        """Получение стока гира"""
        return await self.fetch_api(GEAR_API)
    
    async def fetch_cosmetics(self) -> Optional[List[Dict]]:
        """Получение стока косметики"""
        return await self.fetch_api(COSMETICS_API)
    
    async def fetch_eggs(self) -> Optional[List[Dict]]:
        """Получение стока яиц"""
        return await self.fetch_api(EGGS_API)
    
    async def fetch_weather(self) -> Optional[Dict]:
        """Получение погоды"""
        try:
            await self.init_session()
            async with self.session.get(WEATHER_API, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    # Возвращаем весь объект, а не список
                    return data
                return None
        except Exception as e:
            logger.error(f"❌ Ошибка API погоды: {e}")
            return None

tracker = StockTracker()
db = SupabaseDB()

# ========== КОМАНДЫ БОТА ==========

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    welcome = (
        "🌱 *Добро пожаловать в GAG Stock Tracker\\!*\n\n"
        "Я помогу вам отслеживать сток семян, гира, косметики и яиц\\.\n\n"
        "📖 *Доступные команды:*\n"
        "🌱 /stock \\- Текущий сток\n"
        "✨ /cosmetic \\- Косметика\n"
        "🌤️ /weather \\- Погода\n"
        "🔔 /autostock \\- Управление автостоками\n"
        "❓ /help \\- Справка"
    )
    await update.message.reply_text(welcome, parse_mode="MarkdownV2")

async def stock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stock - просмотр текущего стока"""
    seeds = await tracker.fetch_seeds()
    gear = await tracker.fetch_gear()
    eggs = await tracker.fetch_eggs()
    
    current_time = format_moscow_time()
    message = "📊 *ТЕКУЩИЙ СТОК*\n\n"
    
    # Семена
    if seeds:
        message += "🌱 *СЕМЕНА:*\n"
        for item in seeds:
            name = item.get('name', '')
            quantity = item.get('quantity', 0)
            if name in SEEDS_DATA:
                data = SEEDS_DATA[name]
                message += f"{data['emoji']} {name} x{quantity}\n"
        message += "\n"
    else:
        message += "🌱 *СЕМЕНА:* _Пусто_\n\n"
    
    # Гиры
    if gear:
        message += "⚔️ *ГИРЫ:*\n"
        for item in gear:
            name = item.get('name', '')
            quantity = item.get('quantity', 0)
            if name in GEAR_DATA:
                data = GEAR_DATA[name]
                message += f"{data['emoji']} {name} x{quantity}\n"
        message += "\n"
    else:
        message += "⚔️ *ГИРЫ:* _Пусто_\n\n"
    
    # Яйца
    if eggs:
        message += "🥚 *ЯЙЦА:*\n"
        for item in eggs:
            name = item.get('name', '')
            quantity = item.get('quantity', 0)
            if name in EGGS_DATA:
                data = EGGS_DATA[name]
                message += f"{data['emoji']} {name} x{quantity}\n"
    else:
        message += "🥚 *ЯЙЦА:* _Пусто_"
    
    message += f"\n\n🕒 {current_time} МСК"
    
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

async def cosmetic_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /cosmetic - просмотр косметики"""
    cosmetics = await tracker.fetch_cosmetics()
    current_time = format_moscow_time()
    
    message = "✨ *СТОК КОСМЕТИКИ*\n\n"
    
    if cosmetics:
        for item in cosmetics:
            name = item.get('name', '')
            quantity = item.get('quantity', 0)
            message += f"🎨 {name} x{quantity}\n"
    else:
        message += "_Пусто_"
    
    message += f"\n\n🕒 {current_time} МСК"
    
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /weather - просмотр погоды"""
    weather = await tracker.fetch_weather()
    current_time = format_moscow_time()
    
    message = "🌤️ *ПОГОДА В ИГРЕ*\n\n"
    
    if weather and isinstance(weather, dict):
        current = weather.get('current', 'Неизвестно')
        upcoming = weather.get('upcoming', 'Неизвестно')
        message += f"Текущая: {current}\n"
        message += f"Следующая: {upcoming}"
    else:
        message += "_Данные недоступны_"
    
    message += f"\n\n🕒 {current_time} МСК"
    
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

async def autostock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /autostock - управление автостоками с кнопками"""
    user_id = update.effective_user.id
    user_items = await db.load_user_autostocks(user_id, use_cache=False)
    
    # Создаем кнопки для семян
    keyboard = []
    for name, data in sorted(SEEDS_DATA.items()):
        is_selected = name in user_items
        symbol = "✅" if is_selected else "➕"
        keyboard.append([InlineKeyboardButton(
            f"{symbol} {data['emoji']} {name}",
            callback_data=f"autostock_seed_{name}"
        )])
    
    # Добавляем переключатель на гиры
    keyboard.append([InlineKeyboardButton("⚔️ ГИРЫ →", callback_data="autostock_show_gear")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        "🔔 *УПРАВЛЕНИЕ АВТОСТОКАМИ*\n\n"
        "🌱 *СЕМЕНА*\n"
        "Выберите предметы для отслеживания:\n"
        "➕ - добавить\n"
        "✅ - уже отслеживается"
    )
    
    await update.message.reply_text(message, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def autostock_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий на кнопки автостоков"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "autostock_show_gear":
        # Показать гиры
        user_items = await db.load_user_autostocks(user_id, use_cache=False)
        keyboard = []
        for name, gear_data in sorted(GEAR_DATA.items()):
            is_selected = name in user_items
            symbol = "✅" if is_selected else "➕"
            keyboard.append([InlineKeyboardButton(
                f"{symbol} {gear_data['emoji']} {name}",
                callback_data=f"autostock_gear_{name}"
            )])
        
        keyboard.append([InlineKeyboardButton("🥚 ЯЙЦА →", callback_data="autostock_show_eggs")])
        keyboard.append([InlineKeyboardButton("← 🌱 СЕМЕНА", callback_data="autostock_show_seeds")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        message = (
            "🔔 *УПРАВЛЕНИЕ АВТОСТОКАМИ*\n\n"
            "⚔️ *ГИРЫ*\n"
            "Выберите предметы для отслеживания:\n"
            "➕ - добавить\n"
            "✅ - уже отслеживается"
        )
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    elif data == "autostock_show_eggs":
        # Показать яйца
        user_items = await db.load_user_autostocks(user_id, use_cache=False)
        keyboard = []
        for name, egg_data in sorted(EGGS_DATA.items()):
            is_selected = name in user_items
            symbol = "✅" if is_selected else "➕"
            keyboard.append([InlineKeyboardButton(
                f"{symbol} {egg_data['emoji']} {name}",
                callback_data=f"autostock_egg_{name}"
            )])
        
        keyboard.append([InlineKeyboardButton("← ⚔️ ГИРЫ", callback_data="autostock_show_gear")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        message = (
            "🔔 *УПРАВЛЕНИЕ АВТОСТОКАМИ*\n\n"
            "🥚 *ЯЙЦА*\n"
            "Выберите предметы для отслеживания:\n"
            "➕ - добавить\n"
            "✅ - уже отслеживается"
        )
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    elif data == "autostock_show_seeds":
        # Показать семена
        user_items = await db.load_user_autostocks(user_id, use_cache=False)
        keyboard = []
        for name, seed_data in sorted(SEEDS_DATA.items()):
            is_selected = name in user_items
            symbol = "✅" if is_selected else "➕"
            keyboard.append([InlineKeyboardButton(
                f"{symbol} {seed_data['emoji']} {name}",
                callback_data=f"autostock_seed_{name}"
            )])
        
        keyboard.append([InlineKeyboardButton("⚔️ ГИРЫ →", callback_data="autostock_show_gear")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        message = (
            "🔔 *УПРАВЛЕНИЕ АВТОСТОКАМИ*\n\n"
            "🌱 *СЕМЕНА*\n"
            "Выберите предметы для отслеживания:\n"
            "➕ - добавить\n"
            "✅ - уже отслеживается"
        )
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    elif data.startswith("autostock_seed_"):
        item_name = data.replace("autostock_seed_", "")
        await toggle_autostock(query, user_id, item_name, "seed")
    
    elif data.startswith("autostock_gear_"):
        item_name = data.replace("autostock_gear_", "")
        await toggle_autostock(query, user_id, item_name, "gear")
    
    elif data.startswith("autostock_egg_"):
        item_name = data.replace("autostock_egg_", "")
        await toggle_autostock(query, user_id, item_name, "egg")

async def toggle_autostock(query, user_id: int, item_name: str, item_type: str):
    """Переключение автостока (добавить/удалить)"""
    user_items = await db.load_user_autostocks(user_id, use_cache=False)
    
    if item_name in user_items:
        # Удалить
        await db.remove_user_autostock(user_id, item_name)
    else:
        # Добавить
        await db.save_user_autostock(user_id, item_name)
    
    # Обновляем кнопки
    user_items = await db.load_user_autostocks(user_id, use_cache=False)
    
    if item_type == "seed":
        keyboard = []
        for name, data in sorted(SEEDS_DATA.items()):
            is_selected = name in user_items
            symbol = "✅" if is_selected else "➕"
            keyboard.append([InlineKeyboardButton(
                f"{symbol} {data['emoji']} {name}",
                callback_data=f"autostock_seed_{name}"
            )])
        keyboard.append([InlineKeyboardButton("⚔️ ГИРЫ →", callback_data="autostock_show_gear")])
        message = (
            "🔔 *УПРАВЛЕНИЕ АВТОСТОКАМИ*\n\n"
            "🌱 *СЕМЕНА*\n"
            "Выберите предметы для отслеживания:\n"
            "➕ - добавить\n"
            "✅ - уже отслеживается"
        )
    elif item_type == "gear":
        keyboard = []
        for name, data in sorted(GEAR_DATA.items()):
            is_selected = name in user_items
            symbol = "✅" if is_selected else "➕"
            keyboard.append([InlineKeyboardButton(
                f"{symbol} {data['emoji']} {name}",
                callback_data=f"autostock_gear_{name}"
            )])
        keyboard.append([InlineKeyboardButton("🥚 ЯЙЦА →", callback_data="autostock_show_eggs")])
        keyboard.append([InlineKeyboardButton("← 🌱 СЕМЕНА", callback_data="autostock_show_seeds")])
        message = (
            "🔔 *УПРАВЛЕНИЕ АВТОСТОКАМИ*\n\n"
            "⚔️ *ГИРЫ*\n"
            "Выберите предметы для отслеживания:\n"
            "➕ - добавить\n"
            "✅ - уже отслеживается"
        )
    else:  # egg
        keyboard = []
        for name, data in sorted(EGGS_DATA.items()):
            is_selected = name in user_items
            symbol = "✅" if is_selected else "➕"
            keyboard.append([InlineKeyboardButton(
                f"{symbol} {data['emoji']} {name}",
                callback_data=f"autostock_egg_{name}"
            )])
        keyboard.append([InlineKeyboardButton("← ⚔️ ГИРЫ", callback_data="autostock_show_gear")])
        message = (
            "🔔 *УПРАВЛЕНИЕ АВТОСТОКАМИ*\n\n"
            "🥚 *ЯЙЦА*\n"
            "Выберите предметы для отслеживания:\n"
            "➕ - добавить\n"
            "✅ - уже отслеживается"
        )