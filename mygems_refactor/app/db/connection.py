from contextlib import contextmanager

import psycopg2

from app.config import DB_CONFIG


@contextmanager
def get_connection():
    """Yield a PostgreSQL connection with proper cleanup."""
    conn = psycopg2.connect(**DB_CONFIG.as_dict())
    try:
        yield conn
    finally:
        conn.close()
