import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramConflictError, TelegramNetworkError

import config
import database
import handlers

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

# Фильтр для блокировки сообщений о конфликте
class ConflictFilter(logging.Filter):
    def filter(self, record):
        message = record.getMessage()
        return "Conflict" not in message and "terminated by other getUpdates" not in message

# Отключаем подробные логи aiogram и добавляем фильтр
aiogram_logger = logging.getLogger("aiogram")
aiogram_logger.setLevel(logging.ERROR)
aiogram_logger.addFilter(ConflictFilter())

dispatcher_logger = logging.getLogger("aiogram.dispatcher")
dispatcher_logger.setLevel(logging.CRITICAL)
dispatcher_logger.addFilter(ConflictFilter())

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
        log.info("Проверка токена через Telegram API...")
        bot_info = await bot.get_me()
        log.info(f"✅ Бот успешно авторизован: @{bot_info.username} (ID: {bot_info.id})")
        return True
    except TelegramBadRequest as e:
        log.error(f"❌ Ошибка токена: {e}")
        log.error("Токен неправильный или истек")
        log.error("Получите новый токен у @BotFather")
        return False
    except TelegramNetworkError as e:
        log.error(f"❌ Ошибка сети при проверке токена: {e}")
        log.error("Проверьте интернет-соединение")
        return False
    except Exception as e:
        log.error(f"❌ Неожиданная ошибка авторизации: {e}")
        log.error("Проверьте токен и интернет-соединение")
        return False


async def main():
    # Проверяем токен перед настройкой БД
    if not await validate_token():
        return False

    await database.setup_db()

    # Удаляем просроченные задачи при запуске
    deleted_count = await database.delete_expired_tasks()
    if deleted_count > 0:
        log.info(f"Удалено {deleted_count} просроченных задач при запуске")

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        log.info("Запуск polling...")
        await dp.start_polling(bot)
    except TelegramConflictError as e:
        log.error("=" * 60)
        log.error("ОШИБКА: Конфликт экземпляров бота!")
        log.error("Причина: Другой экземпляр бота уже запущен")
        log.error("=" * 60)
        log.error("Решения:")
        log.error("1. Запустите: python stop_bot.py")
        log.error("2. Подождите 1-2 минуты")
        log.error("3. Перезапустите бота")
        log.error("4. Или используйте: python check_and_run.py")
        log.error("=" * 60)
        print("\n" + "=" * 60)
        print("КОНФЛИКТ ЭКЗЕМПЛЯРОВ БОТА!")
        print("Запустите: python stop_bot.py")
        print("Затем: python check_and_run.py")
        print("=" * 60)
        return False
    except TelegramNetworkError as e:
        log.error(f"Ошибка сети: {e}")
        log.error("Проверьте интернет-соединение")
        return False
    except Exception as e:
        log.error(f"Неожиданная ошибка при запуске polling: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


async def run_bot():
    """Запуск бота с обработкой ошибок"""
    log.info("Бот запускается...")

    success = await main()
    if not success:
        log.error("Не удалось запустить бота из-за ошибок")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        log.info("Бот остановлен вручную (Ctrl+C)")
        print("\nБот остановлен пользователем")
    except Exception as e:
        log.error(f"Критическая ошибка при запуске: {e}")
        import traceback
        traceback.print_exc()
        print(f"\nКритическая ошибка: {e}")
        sys.exit(1)
