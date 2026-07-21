from functools import lru_cache

from app.config import Settings, load_settings
from app.db import Database


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


def get_db() -> Database:
    return Database(get_settings())
