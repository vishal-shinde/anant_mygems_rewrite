from app.db.connection import get_connection


class SystemService:
    def check_database(self):
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            return True, None
        except Exception as exc:  # pragma: no cover - runtime connectivity check
            return False, str(exc)
