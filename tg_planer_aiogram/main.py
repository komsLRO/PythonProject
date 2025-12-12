import asyncio
import logging
from datetime import datetime

import aiosqlite
import numpy as np
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message
from sentence_transformers import SentenceTransformer
from sympy.codegen.ast import none

# ---------------- НАСТРОЙКИ ----------------

TOKEN = "***********************"
DB_NAME = 'planner.db'
EMB_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("planner_bot")

bot = Bot(token=(TOKEN), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
embedder = SentenceTransformer(EMB_MODEL)


# ---------------- УТИЛИТЫ ----------------


def current_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def current_time() -> str:
    return datetime.now().strftime("%H:%M")


def make_embedding(text: str) -> np.ndarray:
    vec = embedder.encode([text])[0].astype("float32")
    return vec


def emb_to_blob(vec: np.ndarray) -> bytes:
    return vec.tobytes()


def blob_to_emb(data: bytes | None) -> np.ndarray | None:
    if data is None:
        return None
    return np.frombuffer(data, dtype="float32")


def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


# ---------------- РАБОТА С БД ----------------


async def setup_db() -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                nickname TEXT
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title   TEXT    NOT NULL,
                date    TEXT    NOT NULL,
                time    TEXT    NOT NULL,
                status  TEXT    NOT NULL DEFAULT 'pending',
                emb     BLOB,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
            """
        )
        await db.commit()
    log.info("База данных инициализирована")


async def register_user(user_id: int, nickname: str | None) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users(user_id, nickname) VALUES (?, ?)",
            (user_id, nickname),
        )
        await db.commit()


async def insert_task(
    user_id: int,
    title: str,
    date_str: str,
    time_str: str,
    emb_blob: bytes,
) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            INSERT INTO tasks(user_id, title, date, time, status, emb)
            VALUES (?, ?, ?, ?, 'pending', ?)
            """,
            (user_id, title, date_str, time_str, emb_blob),
        )
        await db.commit()


async def fetch_tasks_for_date(user_id: int, date_str: str):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            """
            SELECT id, title, time, status
            FROM tasks
            WHERE user_id = ? AND date = ?
            ORDER BY time
            """,
            (user_id, date_str),
        )
        rows = await cur.fetchall()
    return rows


async def mark_task_done(user_id: int, task_id: int) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            """
            UPDATE tasks
            SET status = 'done'
            WHERE id = ? AND user_id = ?
            """,
            (task_id, user_id),
        )
        await db.commit()
        return cur.rowcount

async def mark_task_undo(user_id: int, task_id: int) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            """
            UPDATE tasks
            SET status = 'pending'
            WHERE id = ? AND user_id = ?
            """,
            (task_id, user_id),
        )
        await db.commit()
        return cur.rowcount


async def tasks_for_exact_datetime(date_str: str, time_str: str):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            """
            SELECT id, user_id, title
            FROM tasks
            WHERE date = ? AND time = ? AND status = 'pending'
            """,
            (date_str, time_str),
        )
        rows = await cur.fetchall()
    return rows


async def load_tasks_with_vectors(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT id, title, emb FROM tasks WHERE user_id = ?",
            (user_id,),
        )
        rows = await cur.fetchall()
    return rows


# ---------------- ОБРАБОТЧИКИ КОМАНД ----------------


@dp.message(Command("start"))
async def on_start(message: Message):
    await register_user(message.from_user.id, message.from_user.username)

    msg = (
        "Привет! Я помогаю планировать день.\n\n"
        "Основные команды:\n"
        "/add текст;YYYY-MM-DD;HH:MM — добавить задачу\n"
        "/today — показать задачи на сегодня\n"
        "/done ID — отметить задачу выполненной\n"
        "/undo ID — отметить задачу невыполненной\n"
        "/search запрос — найти похожие задачи по смыслу\n"

    )
    await message.answer(msg)


@dp.message(Command("add"))
async def on_add(message: Message):

    if " " not in message.text:
        await message.answer(
            "Нужно указать параметры.\n"
            "Пример: /add Сделать лабу;2025-12-10;18:30"
        )
        return

    _, raw = message.text.split(" ", 1)
    parts = [p.strip() for p in raw.split(";")]
    if len(parts) != 3:
        await message.answer(
            "Неверный формат. Должно быть: текст;дата;время\n"
            "Пример: /add Купить продукты;2025-12-10;19:00"
        )
        return

    title, date_str, time_str = parts

    # можно добавить простую проверку формата даты/времени
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        datetime.strptime(time_str, "%H:%M")
    except ValueError:
        await message.answer("Дата или время указаны неправильно.")
        return

    vec = make_embedding(title)
    blob = emb_to_blob(vec)
    await insert_task(message.from_user.id, title, date_str, time_str, blob)

    await message.answer(
        f"Задача сохранена:\n<b>{title}</b>\nДата: {date_str}, время: {time_str}"
    )


@dp.message(Command("today"))
async def on_today(message: Message):
    today = current_date()
    tasks = await fetch_tasks_for_date(message.from_user.id, today)

    if not tasks:
        await message.answer("На сегодня задач нет")
    else:
        lines = [f"Задачи на {today}:"]
        for task_id, title, time_str, status in tasks:
            mark = "✅" if status == "done" else "⏳"
            lines.append(f"{task_id}. [{time_str}] {title} {mark}")
        await message.answer("\n".join(lines))


@dp.message(Command("done"))
async def on_done(message: Message):
    # формат: /done ID
    try:
        task_id = int(message.text.split(" ", 1)[1])
    except (ValueError, IndexError):
        await message.answer("Нужно указать ID задачи.\nПример: /done 1")
        return

    count = await mark_task_done(message.from_user.id, task_id)
    if count > 0:
        await message.answer(f"Задача {task_id} выполнена! ✅")
    else:
        await message.answer("Задача не найдена или уже выполнена.")


@dp.message(Command("undo"))
async def on_done(message: Message):
    # формат: /done ID
    try:
        task_id = int(message.text.split(" ", 1)[1])
    except (ValueError, IndexError):
        await message.answer("Нужно указать ID задачи.\nПример: /undo 1")
        return

    count = await mark_task_undo(message.from_user.id, task_id)
    if count > 0:
        await message.answer(f"Задача {task_id} возвращена! ✅")
    else:
        await message.answer("Задача не найдена или ещё не выполнена.")


@dp.message(Command("search"))
async def on_search(message: Message):
    # формат: /search текст
    if " " not in message.text:
        await message.answer("Введите текст для поиска.\nПример: /search купить")
        return

    query_text = message.text.split(" ", 1)[1]
    query_vec = make_embedding(query_text)

    # Получаем все задачи пользователя (включая старые)
    rows = await load_tasks_with_vectors(message.from_user.id)
    if not rows:
        await message.answer("У вас пока нет задач для поиска.")
        return

    # Считаем косинусное сходство
    results = []
    for t_id, t_title, t_blob in rows:
        t_vec = blob_to_emb(t_blob)
        if t_vec is not None:
            score = cosine_sim(query_vec, t_vec)
            results.append((score, t_title))

    # Сортируем по убыванию похожести и берем топ-3
    results.sort(key=lambda x: x[0], reverse=True)
    top_3 = results[:3]

    if not top_3 or top_3[0][0] < 0.3:  # порог похожести
        await message.answer("Ничего похожего не найдено.")
        return

    text_lines = ["Найдены похожие задачи:"]
    for score, title in top_3:
        text_lines.append(f"— {title} (сходство: {score:.2f})")

    await message.answer("\n".join(text_lines))

    # ---------------- ЗАПУСК БОТА ----------------

async def main():
    await setup_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        log.info("Бот запускается...")
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Бот остановлен вручную.")
