import asyncio
import json
import os
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.enums import ContentType
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.media_group import MediaGroupBuilder

from config import BOT_TOKEN, SOURCE_CHAT_ID, TARGET_CHAT_ID
from filters import ALLOWED_KEYWORDS, BLOCKED_WORDS

# ====== БОТ ======
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)
dp = Dispatcher()

# ====== ФАЙЛЫ ======
MESSAGE_MAP_FILE = "message_map.json"
BANNED_FILE = "banned_users.json"

# ====== ЗАГРУЗКА ======
def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

message_map = load_json(MESSAGE_MAP_FILE, {})
banned_users = set(load_json(BANNED_FILE, []))

def save_message_map():
    save_json(MESSAGE_MAP_FILE, message_map)

def save_banned():
    save_json(BANNED_FILE, list(banned_users))

# ====== ФИЛЬТРЫ ======
def check_filters(text: str) -> bool:
    if not text:
        return False
    for w in BLOCKED_WORDS:
        if w.lower() in text.lower():
            return False
    for w in ALLOWED_KEYWORDS:
        if w in text:
            return True
    return False

def is_banned(user_id: int) -> bool:
    return user_id in banned_users

# ====== АЛЬБОМЫ ======
pending_albums = {}
album_timers = {}

async def process_album(group_id):
    await asyncio.sleep(1)

    if group_id not in pending_albums:
        return

    messages = pending_albums.pop(group_id)
    first = messages[0]
    text = first.caption or first.text or ""
    sender = first.from_user.id

    if is_banned(sender):
        return

    if not check_filters(text):
        return

    builder = MediaGroupBuilder()

    for msg in messages:
        if msg.photo:
            builder.add_photo(msg.photo[-1].file_id)
        elif msg.video:
            builder.add_video(msg.video.file_id)

    sent = await bot.send_media_group(
        chat_id=TARGET_CHAT_ID,
        media=builder.build()
    )

    for i, msg in enumerate(messages):
        message_map[str(msg.message_id)] = sent[i].message_id

    save_message_map()

# ====== НОВЫЕ СООБЩЕНИЯ ======
@dp.message(F.chat.id == SOURCE_CHAT_ID)
async def new_message(msg: Message):
    user_id = msg.from_user.id

    if is_banned(user_id):
        return

    # Альбом
    if msg.media_group_id:
        gid = msg.media_group_id

        if gid not in pending_albums:
            pending_albums[gid] = []

        pending_albums[gid].append(msg)

        if gid in album_timers:
            album_timers[gid].cancel()

        album_timers[gid] = asyncio.create_task(process_album(gid))
        return

    # Обычное сообщение
    text = msg.text or msg.caption or ""

    if not check_filters(text):
        return

    if msg.photo:
        sent = await bot.send_photo(
            TARGET_CHAT_ID,
            msg.photo[-1].file_id,
            caption=text
        )
    elif msg.video:
        sent = await bot.send_video(
            TARGET_CHAT_ID,
            msg.video.file_id,
            caption=text
        )
    else:
        sent = await bot.send_message(
            TARGET_CHAT_ID,
            text
        )

    message_map[str(msg.message_id)] = sent.message_id
    save_message_map()

# ====== РЕДАКТИРОВАНИЕ ======
@dp.edited_message(F.chat.id == SOURCE_CHAT_ID)
async def edit_message(msg: Message):
    key = str(msg.message_id)
    text = msg.text or msg.caption or ""

    if is_banned(msg.from_user.id):
        return

    # Если сообщение не было переслано
    if key not in message_map:
        if check_filters(text):
            await new_message(msg)
        return

    target_id = message_map[key]

    # Если после редактирования не проходит фильтр → удалить
    if not check_filters(text):
        await bot.delete_message(TARGET_CHAT_ID, target_id)
        del message_map[key]
        save_message_map()
        return

    # Обновление
    if msg.photo:
        await bot.edit_message_caption(
            chat_id=TARGET_CHAT_ID,
            message_id=target_id,
            caption=text
        )
    else:
        await bot.edit_message_text(
            chat_id=TARGET_CHAT_ID,
            message_id=target_id,
            text=text
        )

# ====== УДАЛЕНИЕ ======
@dp.message_deleted()
async def deleted(event):
    for deleted_id in event.message_ids:
        key = str(deleted_id)
        if key in message_map:
            try:
                await bot.delete_message(
                    TARGET_CHAT_ID,
                    message_map[key]
                )
            except:
                pass
            del message_map[key]
            save_message_map()

# ====== ЗАПУСК ======
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())