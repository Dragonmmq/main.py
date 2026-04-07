import asyncio
import os
import time
import sqlite3
import html
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = os.environ["8656014512:AAFOs-gYpJEM_j5QErlJ9cEnC4fWBliygkI"]

ADMINS = [8394162540]
CHANNEL_ID = -1003285603970

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ===== БАЗА =====
conn = sqlite3.connect("bot.db")
cur = conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS users(
id INTEGER PRIMARY KEY,
banned INTEGER DEFAULT 0
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS messages(
id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id INTEGER,
text TEXT,
likes INTEGER DEFAULT 0,
dislikes INTEGER DEFAULT 0
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS settings(
key TEXT PRIMARY KEY,
value TEXT
)""")

cur.execute("INSERT OR IGNORE INTO settings VALUES('auto','0')")
cur.execute("INSERT OR IGNORE INTO settings VALUES('forward','1')")

conn.commit()

# ===== УТИЛИТЫ =====
def is_admin(id): return id in ADMINS

def is_banned(id):
    cur.execute("SELECT banned FROM users WHERE id=?", (id,))
    r = cur.fetchone()
    return r and r[0]==1

def setting(key):
    cur.execute("SELECT value FROM settings WHERE key=?", (key,))
    r = cur.fetchone()
    return r[0]=="1"

def set_setting(k,v):
    cur.execute("UPDATE settings SET value=? WHERE key=?", (v,k))
    conn.commit()

# ===== КНОПКИ =====
def main_kb(bot_username):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✉️ Написать ещё", url=f"https://t.me/{bot_username}")]
    ])

def react_kb(msg_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👍", callback_data=f"like_{msg_id}"),
            InlineKeyboardButton(text="👎", callback_data=f"dislike_{msg_id}")
        ]
    ])

# ===== START =====
@dp.message(CommandStart())
async def start(m: types.Message):
    bot_info = await bot.get_me()
    await m.answer(
        f"👻 Анонимный бот\n\nОтправь сообщение:\nhttps://t.me/{bot_info.username}"
    )

# ===== СООБЩЕНИЯ =====
last = {}

@dp.message(~F.text.startswith("/"))
async def msg(m: types.Message):
    uid = m.from_user.id
    if is_banned(uid): return

    now = time.time()
    if uid in last and now-last[uid]<3:
        return await m.answer("⏳ Не спамь")
    last[uid]=now

    text = m.text or ""

    cur.execute("INSERT INTO messages(user_id,text) VALUES(?,?)",(uid,text))
    conn.commit()
    msg_id = cur.lastrowid

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ Ответить", callback_data=f"reply_{uid}")]
    ])

    for admin in ADMINS:
        # сообщение
        await bot.send_message(admin,
            f"💬 {html.escape(text)}",
            reply_markup=react_kb(msg_id)
        )

        # автор (🔥 отдельно)
        await bot.send_message(admin,
            f"👤 Автор\nID: {uid}\nИмя: {m.from_user.full_name}"
        )

    if setting("forward"):
        try:
            await bot.send_message(CHANNEL_ID, f"💬 {html.escape(text)}")
        except: pass

    # автоответ
    if setting("auto"):
        await m.answer("🤖 Спасибо за сообщение!")

    bot_info = await bot.get_me()
    await m.answer("✅ Отправлено", reply_markup=main_kb(bot_info.username))

# ===== РЕАКЦИИ =====
@dp.callback_query(F.data.startswith("like_"))
async def like(c):
    id = int(c.data.split("_")[1])
    cur.execute("UPDATE messages SET likes=likes+1 WHERE id=?", (id,))
    conn.commit()
    await c.answer("👍")

@dp.callback_query(F.data.startswith("dislike_"))
async def dislike(c):
    id = int(c.data.split("_")[1])
    cur.execute("UPDATE messages SET dislikes=dislikes+1 WHERE id=?", (id,))
    conn.commit()
    await c.answer("👎")

# ===== АДМИН =====
@dp.message(Command("ban"))
async def ban(m):
    if not is_admin(m.from_user.id): return
    uid = int(m.text.split()[1])
    cur.execute("INSERT OR REPLACE INTO users VALUES(?,1)", (uid,))
    conn.commit()
    await m.answer("🚫 бан")

@dp.message(Command("unban"))
async def unban(m):
    if not is_admin(m.from_user.id): return
    uid = int(m.text.split()[1])
    cur.execute("UPDATE users SET banned=0 WHERE id=?", (uid,))
    conn.commit()
    await m.answer("✅ разбан")

@dp.message(Command("stats"))
async def stats(m):
    if not is_admin(m.from_user.id): return
    cur.execute("SELECT COUNT(*) FROM messages")
    total = cur.fetchone()[0]
    await m.answer(f"📊 сообщений: {total}")

@dp.message(Command("autoon"))
async def autoon(m):
    if not is_admin(m.from_user.id): return
    set_setting("auto","1")
    await m.answer("🤖 автоответ включен")

@dp.message(Command("autooff"))
async def autooff(m):
    if not is_admin(m.from_user.id): return
    set_setting("auto","0")
    await m.answer("🤖 автоответ выключен")

@dp.message(Command("forward_on"))
async def fon(m):
    if not is_admin(m.from_user.id): return
    set_setting("forward","1")
    await m.answer("📡 включено")

@dp.message(Command("forward_off"))
async def foff(m):
    if not is_admin(m.from_user.id): return
    set_setting("forward","0")
    await m.answer("📡 выключено")

# ===== ЗАПУСК =====
async def main():
    print("🔥 ULTRA BOT STARTED")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
