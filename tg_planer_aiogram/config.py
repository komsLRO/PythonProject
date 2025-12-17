import os

# ---------------- НАСТРОЙКИ ----------------

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
DB_NAME = 'planner.db'
EMB_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
