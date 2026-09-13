from __future__ import annotations

from typing import Any

from app.db.connection import get_connection


class BaseRepository:
    def fetch_one(self, query: str, params: tuple | None = None):
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params or ())
                return cur.fetchone()

    def fetch_all(self, query: str, params: tuple | None = None):
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params or ())
                return cur.fetchall()

    def execute(self, query: str, params: tuple | None = None):
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params or ())
                conn.commit()
                if cur.description:
                    rows = cur.fetchall()
                    if not rows:
                        return cur.rowcount
                    if len(rows) == 1 and len(rows[0]) == 1:
                        return rows[0][0]
                    return rows[0]
                return cur.rowcount
