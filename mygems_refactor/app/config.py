import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


@dataclass(frozen=True)
class DatabaseConfig:
    host: str = os.getenv("MYGEMS_DB_HOST", "localhost")
    port: int = int(os.getenv("MYGEMS_DB_PORT", "5432"))
    dbname: str = os.getenv("MYGEMS_DB_NAME", "mygems")
    user: str = os.getenv("MYGEMS_DB_USER", "myuser")
    password: str = os.getenv("MYGEMS_DB_PASSWORD", "28116")

    def as_dict(self) -> dict:
        return {
            "host": self.host,
            "port": self.port,
            "dbname": self.dbname,
            "user": self.user,
            "password": self.password,
        }


DB_CONFIG = DatabaseConfig()
