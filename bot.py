import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.filters import Command

# Логирование
logging.basicConfig(level=logging.INFO)

# Получаем токен из переменной окружения (Railway)
TOKEN = os.getenv("BOT_TOKEN")

# Создаем объекты
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- Пример: базовая команда /start ---
@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer("Привет! Я готов к работе. Добавляй команды в мой код 😊")

# --- Пример: базовая команда /ping ---
@dp.message(Command("ping"))
async def ping_handler(message: Message):
    await message.answer("pong 🏓")

# Основная функция запуска
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
