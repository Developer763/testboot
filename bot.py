import os
import json
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command

API_TOKEN = os.getenv("BOT_TOKEN")

ADMINS_FILE = "admins.json"
BANNED_FILE = "banned.json"
MUTED_FILE = "muted.json"

def load_data(filename, default=None):
    if not os.path.exists(filename):
        return default if default is not None else {}
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

admins = load_data(ADMINS_FILE, {})
banned = load_data(BANNED_FILE, {})
muted = load_data(MUTED_FILE, {})

ROLES = ["Стажер", "Модератор", "Старший модератор", "Заместитель", "Владелец"]

def get_role(user_id: int):
    for adm in admins.values():
        if adm["id"] == user_id:
            return adm["role"]
    return None

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

@dp.message(Command("admins"))
async def list_admins(message: Message):
    text = "👮 Администраторы:\n"
    for adm in admins.values():
        text += f'- {adm["id"]} ({adm["role"]})\n'
    await message.answer(text)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
