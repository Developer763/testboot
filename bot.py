import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Список администраторов (user_id -> имя)
admins = {}

# --- команда /start ---
@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer("Привет! Я Security Сафронкса.")

# --- команда /setadm ---
@dp.message(Command("setadm"))
async def setadm_handler(message: Message):
    # Только владелец бота может назначать (по user_id)
    OWNER_ID = 123456789  # <-- замени на свой Telegram ID
    
    if message.from_user.id != OWNER_ID:
        await message.answer("❌ У вас нет прав назначать администраторов.")
        return

    # Разбираем аргументы (/setadm @username)
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("⚠️ Использование: /setadm @username")
        return

    username = args[1].lstrip("@")
    user_id = message.from_user.id  # здесь лучше добавить поиск по юзеру через базу

    admins[username] = user_id
    await message.answer(f"✅ Пользователь @{username} назначен администратором в боте!")

# --- команда /admins ---
@dp.message(Command("admins"))
async def admins_handler(message: Message):
    if not admins:
        await message.answer("👤 Администраторов пока нет.")
    else:
        admin_list = "\n".join([f"@{u}" for u in admins.keys()])
        await message.answer(f"📋 Список администраторов:\n{admin_list}")

# Основной запуск
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
