#!/usr/bin/env python3
"""
Скрипт для запуска Telegram бота-планировщика
"""

import os
import sys

def find_bot_directory():
    """Находит директорию с модулями бота"""
    # Сначала пробуем текущую директорию
    current_dir = os.getcwd()
    bot_dir = os.path.join(current_dir, 'tg_planer_aiogram')
    if os.path.exists(bot_dir):
        return bot_dir

    # Если не нашли, пробуем директорию скрипта
    script_dir = os.path.dirname(os.path.abspath(__file__))
    bot_dir = os.path.join(script_dir, 'tg_planer_aiogram')
    if os.path.exists(bot_dir):
        return bot_dir

    print("Ошибка: Не удалось найти директорию tg_planer_aiogram!")
    return None

def main():
    """Основная функция запуска"""
    # Находим директорию с ботом
    bot_dir = find_bot_directory()
    if not bot_dir:
        sys.exit(1)

    # Добавляем в путь
    if bot_dir not in sys.path:
        sys.path.insert(0, bot_dir)

    print(f"Запуск бота из директории: {bot_dir}")

    try:
        # Импортируем и запускаем
        from tg_planer_aiogram.main import main as bot_main
        import asyncio
        asyncio.run(bot_main())
    except ImportError as e:
        print(f"Ошибка импорта модулей бота: {e}")
        print(f"Проверьте, что все файлы находятся в директории {bot_dir}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nБот остановлен пользователем")
    except Exception as e:
        print(f"Неожиданная ошибка при запуске бота: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
