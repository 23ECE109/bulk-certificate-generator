"""
Application configuration loaded from environment variables (with defaults).
"""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # SQLite by default; override with e.g. postgresql+psycopg2://...
    database_url: str = "sqlite:///./certificates.db"

    # Directory where generated PDF files are stored
    certificates_dir: str = str(Path(__file__).parent.parent / "certificates")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
