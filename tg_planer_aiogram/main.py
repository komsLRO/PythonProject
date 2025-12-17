import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import config
import database
import handlers

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("planner_bot")

# Проверка токена
if not config.TOKEN or config.TOKEN.strip() == "":
    log.error("Токен Telegram бота не настроен!")
    log.error("Установите переменную окружения TELEGRAM_BOT_TOKEN")
    log.error("Пример: export TELEGRAM_BOT_TOKEN='ваш_токен_от_BotFather'")
    exit(1)

# Инициализация бота
bot = Bot(token=config.TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Регистрация обработчиков
handlers.register_handlers(dp)


async def validate_token():
    """Проверка токена через Telegram API"""
    try:
        bot_info = await bot.get_me()
        log.info(f"Бот успешно авторизован: @{bot_info.username} (ID: {bot_info.id})")
        return True
    except Exception as e:
        log.error(f"Ошибка авторизации бота: {e}")
        log.error("Проверьте правильность токена TELEGRAM_BOT_TOKEN")
        return False


async def main():
    # Проверяем токен перед настройкой БД
    if not await validate_token():
        exit(1)

    await database.setup_db()

    # Удаляем просроченные задачи при запуске
    deleted_count = await database.delete_expired_tasks()
    if deleted_count > 0:
        log.info(f"Удалено {deleted_count} просроченных задач при запуске")

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        log.info("Бот запускается...")
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Бот остановлен вручную.")
