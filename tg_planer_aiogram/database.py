import aiosqlite
import logging
from datetime import datetime
from config import DB_NAME

log = logging.getLogger("planner_bot")


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
) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            """
            INSERT INTO tasks(user_id, title, date, time, status, emb)
            VALUES (?, ?, ?, ?, 'pending', ?)
            """,
            (user_id, title, date_str, time_str, emb_blob),
        )
        await db.commit()
        return cur.lastrowid


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


async def fetch_tasks_for_dates(user_id: int, date_list: list[str]):
    """Получить задачи для нескольких дат"""
    placeholders = ','.join('?' * len(date_list))
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            f"""
            SELECT id, title, date, time, status
            FROM tasks
            WHERE user_id = ? AND date IN ({placeholders})
            ORDER BY date, time
            """,
            (user_id, *date_list),
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


async def delete_task(user_id: int, task_id: int) -> int:
    """Удалить задачу"""
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            """
            DELETE FROM tasks
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


async def fetch_all_tasks(user_id: int, limit: int = 50):
    """Получить все задачи пользователя (с лимитом для производительности)"""
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            """
            SELECT id, title, date, time, status
            FROM tasks
            WHERE user_id = ?
            ORDER BY date ASC, time ASC
            LIMIT ?
            """,
            (user_id, limit),
        )
        rows = await cur.fetchall()
    return rows


async def delete_expired_tasks() -> int:
    """Удалить все просроченные задачи (старше текущего момента)"""
    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M")
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            """
            DELETE FROM tasks
            WHERE (date || ' ' || time) < ? AND status = 'pending'
            """,
            (current_datetime,),
        )
        deleted_count = cur.rowcount
        await db.commit()
    return deleted_count


async def delete_all_tasks(user_id: int) -> int:
    """Удалить все задачи пользователя"""
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "DELETE FROM tasks WHERE user_id = ?",
            (user_id,),
        )
        deleted_count = cur.rowcount
        await db.commit()

        # Сбрасываем autoincrement счетчик
        await db.execute("DELETE FROM sqlite_sequence WHERE name='tasks'")
        await db.commit()

    return deleted_count


async def count_user_tasks(user_id: int) -> int:
    """Посчитать количество задач пользователя"""
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT COUNT(*) FROM tasks WHERE user_id = ?",
            (user_id,),
        )
        row = await cur.fetchone()
    return row[0] if row else 0


async def reset_task_ids() -> None:
    """Сбросить autoincrement счетчик ID задач"""
    async with aiosqlite.connect(DB_NAME) as db:
        # Получить максимальный ID
        cur = await db.execute("SELECT MAX(id) FROM tasks")
        max_id_row = await cur.fetchone()
        max_id = max_id_row[0] if max_id_row and max_id_row[0] else 0

        # Если задач нет, сбрасываем счетчик на 1
        if max_id == 0:
            await db.execute("DELETE FROM sqlite_sequence WHERE name='tasks'")
        else:
            # Если задачи есть, устанавливаем счетчик на max_id + 1
            await db.execute(
                "UPDATE sqlite_sequence SET seq = ? WHERE name = 'tasks'",
                (max_id,)
            )

        await db.commit()
