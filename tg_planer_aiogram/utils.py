import numpy as np
from datetime import datetime, timedelta
from sentence_transformers import SentenceTransformer
from config import EMB_MODEL

# Инициализация модели эмбеддингов
embedder = SentenceTransformer(EMB_MODEL)


def current_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def current_time() -> str:
    return datetime.now().strftime("%H:%M")


def parse_date_time(date_input: str, time_input: str) -> tuple[str, str] | None:
    """
    Парсит дату и время в простом формате: DD.MM.YYYY HH:MM
    """
    try:
        # Пробуем распарсить дату в формате DD.MM.YYYY
        date_obj = datetime.strptime(date_input.strip(), "%d.%m.%Y").date()

        # Пробуем распарсить время в формате HH:MM
        time_obj = datetime.strptime(time_input.strip(), "%H:%M").time()

        return date_obj.strftime("%Y-%m-%d"), time_obj.strftime("%H:%M")
    except ValueError:
        return None


def validate_datetime(date_str: str, time_str: str) -> bool:
    """
    Проверяет, что дата и время не в прошлом
    """
    try:
        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        return dt > datetime.now()
    except ValueError:
        return False


def format_datetime_display(date_str: str, time_str: str) -> str:
    """
    Форматирует дату и время для отображения в числовом формате DD.MM.YYYY HH:MM
    """
    try:
        # Парсим дату и время
        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")

        # Всегда показываем в формате DD.MM.YYYY HH:MM
        return dt.strftime("%d.%m.%Y %H:%M")
    except ValueError:
        # Если не удается распарсить, возвращаем как есть
        return f"{date_str} {time_str}"


def format_date_display(date_str: str) -> str:
    """
    Форматирует только дату для отображения в формате DD.MM.YYYY
    """
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%d.%m.%Y")
    except ValueError:
        return date_str


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
