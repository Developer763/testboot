import asyncio
import logging
import os
import json
import time
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, exceptions
from aiogram.types import Message, ChatPermissions
from aiogram.filters import Command

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN env var is required")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# files
ADMINS_FILE = "admins.json"
BANNED_FILE = "banned.json"
MUTED_FILE = "muted.json"

ROLES = ["Стажер", "Модератор", "Старший модератор", "Заместитель", "Владелец"]
OWNER_ID = 7294123971  # main owner id

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
# muted structure: keys are "<chat_id>:<user_id>" -> { "chat_id":..., "user_id":..., "until": unix_ts }
muted = load_data(MUTED_FILE, {})

# default permissions (in-code)
permissions = {
    "Стажер": ["mute", "unmute"],
    "Модератор": ["mute", "unmute", "ban"],
    "Старший модератор": ["mute", "unmute", "ban", "unban"],
    "Заместитель": ["mute", "unmute", "ban", "unban", "setadm", "nahuisadm", "setperm"],
    "Владелец": ["*"]
}

def get_role(user_id):
    if str(user_id) == str(OWNER_ID):
        return "Владелец"
    for username, info in admins.items():
        if str(info.get("id")) == str(user_id):
            return info.get("role")
    return None

def can_execute(user_id, command):
    role = get_role(user_id)
    if role == "Владелец":
        return True
    allowed = permissions.get(role, [])
    return "*" in allowed or command in allowed

def has_permission(user_id, required_role):
    # higher index = higher power
    user_role = get_role(user_id)
    if user_role == "Владелец":
        return True
    if user_role is None:
        return False
    try:
        return ROLES.index(user_role) >= ROLES.index(required_role)
    except ValueError:
        return False

async def resolve_target(message: Message, arg: str = None):
    """Return (user_id, full_name) or (None, None) if not found.
       Supports reply, numeric id, and @username (tries chat member first, then get_chat).
    """
    # reply
    if message.reply_to_message:
        u = message.reply_to_message.from_user
        return u.id, (u.full_name or u.username or str(u.id))

    if not arg:
        return None, None

    # try numeric id
    if arg.isdigit():
        try:
            return int(arg), None
        except Exception:
            pass

    username = arg.lstrip("@")

    # try find in the chat members
    try:
        cm = await bot.get_chat_member(message.chat.id, username)
        u = cm.user
        return u.id, (u.full_name or u.username or str(u.id))
    except exceptions.TelegramBadRequest:
        # not found in chat by username, try get_chat (works for @username)
        try:
            ch = await bot.get_chat("@" + username)
            return ch.id, (getattr(ch, 'title', None) or getattr(ch, 'username', None) or str(ch.id))
        except Exception:
            return None, None
    except Exception:
        return None, None

# --- command handlers ---

@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer("Привет! Я групповой модератор. Используй команды в группе: /ban, /unban, /mute, /unmute, /setadm, /nahuisadm, /admins, /setperm")


@dp.message(Command("setadm"))
async def setadm_handler(message: Message):
    if not can_execute(message.from_user.id, "setadm"):
        return await message.answer("❌ У вас нет доступа к этой команде.")
    args = message.text.split()
    if len(args) < 3:
        return await message.answer("⚠️ Использование: /setadm @username Роль")
    username = args[1].lstrip("@")
    role = args[2]
    if role not in ROLES or role == "Владелец":
        return await message.answer("⚠️ Доступные роли: Стажер, Модератор, Старший модератор, Заместитель")
    # Try to resolve user id in current chat if possible
    user_id, _ = await resolve_target(message, args[1])
    if not user_id:
        return await message.answer("❌ Не удалось найти пользователя. Назначение по логину всё равно сохранится, но id пустой.")
    admins[username] = {"id": int(user_id), "role": role}
    save_data(ADMINS_FILE, admins)
    await message.answer(f"✅ @{username} назначен как {role}.")


@dp.message(Command("nahuisadm"))
async def nahuisadm_handler(message: Message):
    if not can_execute(message.from_user.id, "nahuisadm"):
        return await message.answer("❌ У вас нет доступа к этой команде.")
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("⚠️ Использование: /nahuisadm @username")
    username = args[1].lstrip("@")
    if username in admins:
        del admins[username]
        save_data(ADMINS_FILE, admins)
        await message.answer(f"❌ @{username} снят с админов.")
    else:
        await message.answer("⚠️ Такой админ не найден.")


@dp.message(Command("admins"))
async def admins_handler(message: Message):
    text = "📋 Администраторы:\n"
    for k, v in admins.items():
        text += f"- {k}: {v.get('id')} ({v.get('role')})\n"
    await message.answer(text)


async def ensure_group(message: Message):
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("⚠️ Эта команда работает только в группах.")
        return False
    return True


@dp.message(Command("ban"))
async def ban_handler(message: Message):
    if not can_execute(message.from_user.id, "ban"):
        return await message.answer("❌ У вас нет доступа к этой команде.")
    if not await ensure_group(message):
        return
    args = message.text.split()
    arg = args[1] if len(args) > 1 else None
    user_id, name = await resolve_target(message, arg)
    if not user_id:
        return await message.answer("❌ Не удалось определить пользователя для бана.")
    try:
        await bot.ban_chat_member(chat_id=message.chat.id, user_id=int(user_id))
        banned_key = f"{message.chat.id}:{user_id}"
        banned[banned_key] = True
        save_data(BANNED_FILE, banned)
        await message.answer(f"⛔ Пользователь {name or user_id} забанен в чате.")
    except Exception as e:
        await message.answer(f"Ошибка при бане: {e}")


@dp.message(Command("unban"))
async def unban_handler(message: Message):
    if not can_execute(message.from_user.id, "unban"):
        return await message.answer("❌ У вас нет доступа к этой команде.")
    if not await ensure_group(message):
        return
    args = message.text.split()
    arg = args[1] if len(args) > 1 else None
    user_id, name = await resolve_target(message, arg)
    if not user_id:
        return await message.answer("❌ Не удалось определить пользователя для разбанивания.")
    try:
        await bot.unban_chat_member(chat_id=message.chat.id, user_id=int(user_id))
        banned_key = f"{message.chat.id}:{user_id}"
        if banned_key in banned:
            del banned[banned_key]
            save_data(BANNED_FILE, banned)
        await message.answer(f"✅ Пользователь {name or user_id} разбанен.")
    except Exception as e:
        await message.answer(f"Ошибка при разбане: {e}")


@dp.message(Command("mute"))
async def mute_handler(message: Message):
    if not can_execute(message.from_user.id, "mute"):
        return await message.answer("❌ У вас нет доступа к этой команде.")
    if not await ensure_group(message):
        return
    args = message.text.split()
    arg = args[1] if len(args) > 1 else None
    user_id, name = await resolve_target(message, arg)
    if not user_id:
        return await message.answer("❌ Не удалось определить пользователя для мута.")
    if len(args) > 2 and args[2].isdigit():
        minutes = int(args[2])
    else:
        return await message.answer("⚠️ Использование: /mute @username 10  (в минутах)")
    until = int(time.time()) + minutes * 60
    permissions_restrict = ChatPermissions(can_send_messages=False, can_send_media_messages=False, can_send_other_messages=False, can_add_web_page_previews=False)
    try:
        await bot.restrict_chat_member(chat_id=message.chat.id, user_id=int(user_id), permissions=permissions_restrict, until_date=until)
        key = f"{message.chat.id}:{user_id}"
        muted[key] = {"chat_id": message.chat.id, "user_id": int(user_id), "until": until}
        save_data(MUTED_FILE, muted)
        await message.answer(f"🔇 Пользователь {name or user_id} замьючен на {minutes} минут.")
    except Exception as e:
        await message.answer(f"Ошибка при муте: {e}")


@dp.message(Command("unmute"))
async def unmute_handler(message: Message):
    if not can_execute(message.from_user.id, "unmute"):
        return await message.answer("❌ У вас нет доступа к этой команде.")
    if not await ensure_group(message):
        return
    args = message.text.split()
    arg = args[1] if len(args) > 1 else None
    user_id, name = await resolve_target(message, arg)
    if not user_id:
        return await message.answer("❌ Не удалось определить пользователя для размьючивания.")
    try:
        permissions_allow = ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True)
        await bot.restrict_chat_member(chat_id=message.chat.id, user_id=int(user_id), permissions=permissions_allow)
        key = f"{message.chat.id}:{user_id}"
        if key in muted:
            del muted[key]
            save_data(MUTED_FILE, muted)
        await message.answer(f"✅ Пользователь {name or user_id} размьючен.")
    except Exception as e:
        await message.answer(f"Ошибка при размьючивании: {e}")


@dp.message(Command("setperm"))
async def setperm_handler(message: Message):
    if not has_permission(message.from_user.id, "Заместитель"):
        return await message.answer("❌ У вас нет прав изменять доступ к командам.")
    args = message.text.split()
    if len(args) < 4:
        return await message.answer("⚠️ Использование: /setperm Роль команда on/off")
    role, command, action = args[1], args[2], args[3].lower()
    if role not in ROLES:
        return await message.answer("⚠️ Такой роли нет.")
    if role == "Владелец":
        return await message.answer("👑 У владельца всегда полный доступ.")
    if action == "on":
        if command not in permissions.get(role, []):
            permissions.setdefault(role, []).append(command)
        return await message.answer(f"✅ Для роли {role} включен доступ к команде /{command}.")
    elif action == "off":
        if command in permissions.get(role, []):
            permissions.get(role, []).remove(command)
        return await message.answer(f"❌ Для роли {role} отключен доступ к команде /{command}.")
    else:
        return await message.answer("⚠️ Используйте on или off.")


async def unmute_watcher():
    while True:
        try:
            now = int(time.time())
            to_unmute = []
            for key, info in list(muted.items()):
                if info.get("until", 0) <= now:
                    to_unmute.append((key, info))
            for key, info in to_unmute:
                try:
                    permissions_allow = ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True)
                    await bot.restrict_chat_member(chat_id=info["chat_id"], user_id=info["user_id"], permissions=permissions_allow)
                except Exception as e:
                    logging.exception("error while auto-unmuting: %s", e)
                if key in muted:
                    del muted[key]
                    save_data(MUTED_FILE, muted)
            await asyncio.sleep(10)
        except Exception:
            await asyncio.sleep(5)

async def on_startup():
    asyncio.create_task(unmute_watcher())

async def main():
    await on_startup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
