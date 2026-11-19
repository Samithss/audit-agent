"""
Postgres connection. One function, used by the loader and by Tools._raw().
"""
import psycopg
from psycopg.rows import dict_row

from .config import DATABASE_URL


def connect():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set -- check .env (docker compose up -d first)")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)
