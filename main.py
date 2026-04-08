import asyncio
import os
import time
import sqlite3
import logging
import html as html_lib
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

# ========= НАСТРОЙКИ =========
TOKEN = os.environ.get("BOT_TOKEN")
ADMINS = [8394162540]
CHANNEL_ID = -1003285603970
PORT = int(os.environ.get("PORT", 10000))

if not TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден")

# ========= ЛОГИ =========
logging.basicConfig(level=logging.INFO)

# ========= БОТ =========
bot = Bot(token=TOKEN)
dp = Dispatcher()

# ========= БАЗА =========
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    text TEXT,
    media_type TEXT,
    file_id TEXT,
    forwarded INTEGER DEFAULT 0,
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)
""")

cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('forwarding', '1')")
conn.commit()

# ========= УТИЛИТЫ =========
def get_forwarding():
    cursor.execute("SELECT value FROM settings WHERE key='forwarding'")
    row = cursor.fetchone()
    return row[0] == "1" if row else True

def set_forwarding(val):
    cursor.execute("UPDATE settings SET value=? WHERE key='forwarding'", (val,))
    conn.commit()

# ========= FSM =========
class ReplyState(StatesGroup):
    waiting = State()

# ========= АНТИСПАМ =========
last_msg = {}
SPAM_DELAY = 5

# ========= КНОПКИ =========
def forward_kb():
    status = get_forwarding()
    text = "🟢 Выключить пересылку" if status else "🔴 Включить пересылку"
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=text, callback_data="toggle")]]
    )

# ========= КОМАНДЫ =========
@dp.message(CommandStart())
async def start(msg: types.Message):
    me = await bot.get_me()
    link = f"https://t.me/{me.username}"

    await msg.answer(
        f"👋 Привет!\n\n"
        f"📩 Напиши сюда — сообщение придёт анонимно\n\n"
        f"🔗 Твоя ссылка:\n<code>{link}</code>",
        parse_mode="HTML"
    )

@dp.message(Command("forward"))
async def forward(msg: types.Message):
    if msg.from_user.id not in ADMINS:
        return
    await msg.answer("⚙️ Управление пересылкой", reply_markup=forward_kb())

@dp.callback_query(F.data == "toggle")
async def toggle(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMINS:
        return await cb.answer("Нет доступа", show_alert=True)

    new = not get_forwarding()
    set_forwarding("1" if new else "0")

    await cb.message.edit_text("⚙️ Настройки обновлены", reply_markup=forward_kb())
    await cb.answer()

# ========= ОТВЕТ =========
@dp.callback_query(F.data.startswith("reply_"))
async def reply(cb: types.CallbackQuery, state: FSMContext):
    uid = int(cb.data.split("_")[1])
    await state.update_data(uid=uid)
    await state.set_state(ReplyState.waiting)
    await cb.message.answer("✍️ Напиши ответ")
    await cb.answer()

@dp.message(ReplyState.waiting)
async def send_reply(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    try:
        await bot.send_message(data["uid"], f"📬 Ответ:\n\n{msg.text}")
        await msg.answer("✅ Отправлено")
    except:
        await msg.answer("❌ Ошибка")
    await state.clear()

# ========= ОСНОВНАЯ ЛОГИКА =========
@dp.message(~F.text.startswith("/"))
async def handle(msg: types.Message):
    user = msg.from_user
    now = time.time()

    if user.id in last_msg and now - last_msg[user.id] < SPAM_DELAY:
        return await msg.answer("⏳ Подожди")

    last_msg[user.id] = now

    text = msg.text or ""
    media = None
    file_id = None

    if msg.photo:
        media = "photo"
        file_id = msg.photo[-1].file_id
    elif msg.video:
        media = "video"
        file_id = msg.video.file_id

    # отправка в канал
    if get_forwarding():
        try:
            if text:
                await bot.send_message(CHANNEL_ID, f"💬 {html_lib.escape(text)}")
            elif media == "photo":
                await bot.send_photo(CHANNEL_ID, file_id)
            elif media == "video":
                await bot.send_video(CHANNEL_ID, file_id)
        except Exception as e:
            logging.error(e)

    # запись в БД
    cursor.execute(
        "INSERT INTO messages (user_id, text, media_type, file_id) VALUES (?, ?, ?, ?)",
        (user.id, text, media, file_id)
    )
    conn.commit()

    # админам
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="↩️ Ответить", callback_data=f"reply_{user.id}")]]
    )

    for admin in ADMINS:
        await bot.send_message(
            admin,
            f"📩 {html_lib.escape(text)}\n\nID: {user.id}",
            reply_markup=kb
        )

    await msg.answer("✅ Отправлено")

# ========= ВЕБ =========
async def start_web():
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="OK"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

# ========= ЗАПУСК =========
async def main():
    await start_web()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
