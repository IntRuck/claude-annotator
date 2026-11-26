"""Settings read from the environment / backend/.env. The only place that reads env values."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/.env, found from this file's own location, so the folder the API or worker
# is started from doesn't matter.
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    # Local Supabase Postgres (session-capable, direct :55322). Schema is owned by Flyway.
    database_url: str = "postgresql+psycopg://postgres:postgres@127.0.0.1:55322/postgres"
    supabase_url: str = "http://127.0.0.1:55321"
    supabase_service_role_key: str = ""

    # Browser origins allowed by CORS (the Vite dev server by default).
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Engines
    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    claude_bin: str = ""
    ollama_url: str = "http://127.0.0.1:11434"


@lru_cache
def get_settings() -> Settings:
    return Settings()
