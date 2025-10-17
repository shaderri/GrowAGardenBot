import asyncio
import aiohttp
import logging
import os
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Set
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
from telegram.constants import ParseMode
from dotenv import load_dotenv
import pytz

load_dotenv()

# ========== КОНФИГУРАЦИЯ ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@GroowAGarden")
SUPABASE_URL_BASE = os.getenv("SUPABASE_URL", "https://your-project.supabase.co/rest/v1")
SUPABASE_API_KEY = os.getenv("SUPABASE_KEY", "your-key")

AUTOSTOCKS_URL = f"{SUPABASE_URL_BASE}/user_autostocks_gag"

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
    "Carrot": {"emoji": "🥕", "price": "10", "rarity": "1 in 1"},
    "Strawberry": {"emoji": "🍓", "price": "50", "rarity": "1 in 1"},
    "Blueberry": {"emoji": "🫐", "price": "400", "rarity": "1 in 1"},
    "Orange Tulip": {"emoji": "🧡", "price": "600", "rarity": "1 in 3"},
    "Tomato": {"emoji": "🍅", "price": "800", "rarity": "1 in 1"},
    "Corn": {"emoji": "🌽", "price": "1,300", "rarity": "1 in 6"},
    "Daffodil": {"emoji": "🌼", "price": "1,000", "rarity": "1 in 7"},
    "Watermelon": {"emoji": "🍉", "price": "2,500", "rarity": "1 in 8"},
    "Pumpkin": {"emoji": "🎃", "price": "3,000", "rarity": "1 in 10"},
    "Apple": {"emoji": "🍎", "price": "3,250", "rarity": "1 in 14"},
    "Bamboo": {"emoji": "🎋", "price": "4,000", "rarity": "1 in 5"},
    "Coconut": {"emoji": "🥥", "price": "6,000", "rarity": "1 in 20"},
    "Cactus": {"emoji": "🌵", "price": "15,000", "rarity": "1 in 30"},
    "Dragon Fruit": {"emoji": "🐉", "price": "50,000", "rarity": "1 in 50"},
    "Mango": {"emoji": "🥭", "price": "100,000", "rarity": "1 in 80"},
    "Grape": {"emoji": "🍇", "price": "850,000", "rarity": "1 in 100"},
    "Mushroom": {"emoji": "🍄", "price": "150,000", "rarity": "1 in 120"},
    "Pepper": {"emoji": "🌶️", "price": "1,000,000", "rarity": "1 in 140"},
    "Cacao": {"emoji": "🍫", "price": "2,500,000", "rarity": "1 in 160"},
    "Beanstalk": {"emoji": "🪜", "price": "10,000,000", "rarity": "1 in 210"},
    "Ember Lily": {"emoji": "🔥", "price": "15,000,000", "rarity": "1 in 240"},
    "Sugar Apple": {"emoji": "🍎", "price": "25,000,000", "rarity": "1 in 290"},
    "Burning Bud": {"emoji": "🔥", "price": "40,000,000", "rarity": "1 in 340"},
    "Giant Pinecone": {"emoji": "🌲", "price": "55,000,000", "rarity": "1 in 380"},
    "Elder Strawberry": {"emoji": "🍓", "price": "70,000,000", "rarity": "1 in 400"},
    "Romanesco": {"emoji": "🥦", "price": "88,000,000", "rarity": "1 in 440"},
    "Crimson Thorn": {"emoji": "🌹", "price": "10,000,000,000", "rarity": "1 in 777"},
    "Great Pumpkin": {"emoji": "🎃", "price": "15,000,000,000", "rarity": "LEGENDARY"},
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
        return await self.fetch_api(WEATHER_API)

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
                message += f"{data['emoji']} *{name}* x{quantity}\n"
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
                message += f"{data['emoji']} *{name}* x{quantity}\n"
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
                message += f"{data['emoji']} *{name}* x{quantity}\n"
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
            message += f"🎨 *{name}* x{quantity}\n"
    else:
        message += "_Пусто_"
    
    message += f"\n\n🕒 {current_time} МСК"
    
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /weather - просмотр погоды"""
    weather = await tracker.fetch_weather()
    current_time = format_moscow_time()
    
    message = "🌤️ *ПОГОДА В ИГРЕ*\n\n"
    
    if weather and isinstance(weather, list) and len(weather) > 0:
        weather_data = weather[0]
        current = weather_data.get('current', 'Неизвестно')
        upcoming = weather_data.get('upcoming', 'Неизвестно')
        message += f"*Текущая:* {current}\n"
        message += f"*Следующая:* {upcoming}"
    else:
        message += "_Данные недоступны_"
    
    message += f"\n\n🕒 {current_time} МСК"
    
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

async def autostock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /autostock - управление автостоками"""
    user_id = update.effective_user.id
    user_items = await db.load_user_autostocks(user_id, use_cache=True)
    current_time = format_moscow_time()
    
    message = "🔔 *УПРАВЛЕНИЕ АВТОСТОКАМИ*\n\n"
    
    if user_items:
        message += "📋 *Ваши отслеживаемые предметы:*\n"
        for item_name in sorted(user_items):
            if item_name in SEEDS_DATA:
                emoji = SEEDS_DATA[item_name]['emoji']
            elif item_name in GEAR_DATA:
                emoji = GEAR_DATA[item_name]['emoji']
            else:
                emoji = "📦"
            message += f"{emoji} {item_name}\n"
        message += "\n"
    else:
        message += "_Пусто - используйте команды ниже_\n\n"
    
    message += (
        "📝 *Команды:*\n"
        "/add\\_autostock название - Добавить\n"
        "/remove\\_autostock название - Удалить\n"
        "/list\\_autostock - Мой список\n\n"
        "⏰ Проверка: каждые 5 минут\n"
        "📢 Редкие предметы: уведомления в канал\n\n"
        f"🕒 {current_time} МСК"
    )
    
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

async def add_autostock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить предмет в автосток"""
    user_id = update.effective_user.id
    current_time = format_moscow_time()
    
    if not context.args:
        await update.message.reply_text(
            "❌ Укажите название предмета\n"
            f"Пример: /add\\_autostock Crimson Thorn\n\n"
            f"🕒 {current_time} МСК",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    item_name = ' '.join(context.args)
    
    if item_name not in SEEDS_DATA and item_name not in GEAR_DATA:
        await update.message.reply_text(
            f"❌ Предмет '{item_name}' не найден\n\n"
            f"🕒 {current_time} МСК",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    success = await db.save_user_autostock(user_id, item_name)
    
    if success:
        if item_name in SEEDS_DATA:
            info = SEEDS_DATA[item_name]
        else:
            info = GEAR_DATA[item_name]
        
        message = (
            f"✅ *ДОБАВЛЕНО В АВТОСТОК*\n\n"
            f"{info['emoji']} *{item_name}*\n"
            f"Цена: {info['price']} ¢\n\n"
            f"🕒 {current_time} МСК"
        )
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(
            f"❌ Ошибка при добавлении\n\n🕒 {current_time} МСК",
            parse_mode=ParseMode.MARKDOWN
        )

async def remove_autostock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить предмет из автостока"""
    user_id = update.effective_user.id
    current_time = format_moscow_time()
    
    if not context.args:
        await update.message.reply_text(
            "❌ Укажите название предмета\n"
            f"Пример: /remove\\_autostock Crimson Thorn\n\n"
            f"🕒 {current_time} МСК",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    item_name = ' '.join(context.args)
    success = await db.remove_user_autostock(user_id, item_name)
    
    if success:
        await update.message.reply_text(
            f"🗑️ *УДАЛЕНО ИЗ АВТОСТОКА*\n\n"
            f"*{item_name}* больше не отслеживается\n\n"
            f"🕒 {current_time} МСК",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            f"❌ Ошибка при удалении\n\n🕒 {current_time} МСК",
            parse_mode=ParseMode.MARKDOWN
        )

async def list_autostock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список автостоков пользователя"""
    user_id = update.effective_user.id
    user_items = await db.load_user_autostocks(user_id, use_cache=True)
    current_time = format_moscow_time()
    
    message = "📋 *МОИ АВТОСТОКИ*\n\n"
    
    if not user_items:
        message += "_Нет отслеживаемых предметов_"
    else:
        for item_name in sorted(user_items):
            if item_name in SEEDS_DATA:
                info = SEEDS_DATA[item_name]
            elif item_name in GEAR_DATA:
                info = GEAR_DATA[item_name]
            else:
                info = {"emoji": "📦", "price": "Unknown"}
            message += f"{info['emoji']} *{item_name}* ({info['price']} ¢)\n"
        message += f"\n_Всего: {len(user_items)} предметов_"
    
    message += f"\n\n🕒 {current_time} МСК"
    
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Справка"""
    current_time = format_moscow_time()
    help_text = (
        "❓ *СПРАВКА*\n\n"
        "📊 *Просмотр стока:*\n"
        "/stock - Текущий сток\n"
        "/cosmetic - Косметика\n"
        "/weather - Погода\n\n"
        "🔔 *Автостоки:*\n"
        "/autostock - Информация\n"
        "/add\\_autostock название - Добавить\n"
        "/remove\\_autostock название - Удалить\n"
        "/list\\_autostock - Мой список\n\n"
        "⏰ Проверка каждые 5 минут\n"
        "📢 Уведомления в канал: @GroowAGarden\n"
        f"📢 Личные уведомления: в личке бота\n\n"
        f"🕒 {current_time} МСК"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

# ========== ПЕРИОДИЧЕСКАЯ ПРОВЕРКА СТОКА ==========

async def stock_check(context: ContextTypes.DEFAULT_TYPE):
    """Периодическая проверка стока и отправка уведомлений"""
    global last_stock_state
    
    try:
        now = get_moscow_time()
        current_time = format_moscow_time()
        logger.info(f"🔍 Проверка стока - {current_time}")
        
        seeds = await tracker.fetch_seeds()
        
        if not seeds:
            return
        
        current_stock = {item['name']: item['quantity'] for item in seeds}
        
        # ===== УВЕДОМЛЕНИЯ В КАНАЛ (только 2 редких семена) =====
        for item_name in RAREST_SEEDS:
            current_count = current_stock.get(item_name, 0)
            previous_count = last_stock_state.get(item_name, 0)
            
            # Если предмет появился или количество увеличилось
            if current_count > 0 and previous_count == 0:
                if item_name in SEEDS_DATA:
                    info = SEEDS_DATA[item_name]
                    message = (
                        f"🚨 *РЕДКИЙ ПРЕДМЕТ В СТОКЕ\\!* 🚨\n\n"
                        f"{info['emoji']} *{item_name}*\n"
                        f"📦 Количество: *x{current_count}*\n"
                        f"💰 Цена: {info['price']} ¢\n"
                        f"⚡ Редкость: {info['rarity']}\n\n"
                        f"🕒 {current_time} МСК"
                    )
                    try:
                        await context.bot.send_message(
                            chat_id=CHANNEL_ID,
                            text=message,
                            parse_mode=ParseMode.MARKDOWN
                        )
                        logger.info(f"✅ Уведомление в канал: {item_name} x{current_count}")
                    except Exception as e:
                        logger.error(f"❌ Ошибка отправки в канал: {e}")
        
        # ===== ЛИЧНЫЕ УВЕДОМЛЕНИЯ (автостоки пользователей) =====
        for item_name, count in current_stock.items():
            previous_count = last_stock_state.get(item_name, 0)
            
            # Отправляем уведомление только если предмет появился
            if count > 0 and previous_count == 0:
                users = await db.get_users_tracking_item(item_name)
                for user_id in users:
                    try:
                        if item_name in SEEDS_DATA:
                            info = SEEDS_DATA[item_name]
                        elif item_name in GEAR_DATA:
                            info = GEAR_DATA[item_name]
                        else:
                            info = {"emoji": "📦", "price": "Unknown"}
                        
                        message = (
                            f"🔔 *АВТОСТОК - ПРЕДМЕТ ПОЯВИЛСЯ\\!*\n\n"
                            f"{info['emoji']} *{item_name}*\n"
                            f"📦 Количество: *x{count}*\n"
                            f"💰 Цена: {info['price']} ¢\n\n"
                            f"🕒 {current_time} МСК"
                        )
                        
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=message,
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except Exception as e:
                        logger.error(f"❌ Ошибка отправки пользователю {user_id}: {e}")
        
        # Обновляем состояние стока
        last_stock_state = current_stock.copy()
        
    except Exception as e:
        logger.error(f"❌ Ошибка stock_check: {e}")

# ========== ЗАПУСК БОТА ==========

def main():
    logger.info("="*60)
    logger.info("🌱 GAG Stock Tracker Bot (Telegram)")
    logger.info("="*60)
    
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не установлен!")
    
    logger.info(f"📢 Канал уведомлений: {CHANNEL_ID}")
    logger.info(f"🔔 Редкие семена для канала: {', '.join(RAREST_SEEDS)}")
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Команды
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("stock", stock_command))
    application.add_handler(CommandHandler("cosmetic", cosmetic_command))
    application.add_handler(CommandHandler("weather", weather_command))
    application.add_handler(CommandHandler("autostock", autostock_command))
    application.add_handler(CommandHandler("add_autostock", add_autostock_command))
    application.add_handler(CommandHandler("remove_autostock", remove_autostock_command))
    application.add_handler(CommandHandler("list_autostock", list_autostock_command))
    application.add_handler(CommandHandler("help", help_command))
    
    # Добавляем периодическую задачу проверки стока (каждые 5 минут)
    job_queue = application.job_queue
    job_queue.run_repeating(
        stock_check, 
        interval=CHECK_INTERVAL_MINUTES * 60,  # 5 минут в секундах
        first=5  # Первая проверка через 5 секунд после запуска
    )
    
    # Запускаем бота (run_polling сам управляет event loop)
    logger.info("🚀 Запускаем бота...")
    application.run_polling(allowed_updates=None, drop_pending_updates=True)

if __name__ == "__main__":
    main()