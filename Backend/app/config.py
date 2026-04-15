"""
app/config.py
─────────────────────────────────────────────────────────────
Centralised application settings loaded from the .env file.
All sensitive values (API keys, DB credentials) are read from
environment variables — never hardcoded.
"""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application-wide configuration.
    All fields are sourced from the .env file (or actual env vars).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────
    app_title: str = "Recipe Extractor & Meal Planner API"
    app_version: str = "1.0.0"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = False

    # ── CORS ─────────────────────────────────────────────────
    cors_origins: str = "https://recipe-ai-1-fc1o.onrender.com,http://localhost:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    # ── NVIDIA / LangChain ───────────────────────────────────
    nvidia_api_key: str = "your_nvidia_api_key_here"
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    llm_model_name: str = "meta/llama-3.1-70b-instruct"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 4096

    # ── PostgreSQL (async) ───────────────────────────────────
    database_url: str = "postgresql+asyncpg://recipe_user:recipe_pass@localhost:5432/recipe_db"

    # ── Scraper ──────────────────────────────────────────────
    scraper_max_text_length: int = 8000
    scraper_request_timeout: int = 30


@lru_cache()
def get_settings() -> Settings:
    """
    Return a cached Settings singleton.
    Use FastAPI's Depends(get_settings) for dependency injection,
    or call directly in service modules.
    """
    return Settings()


# Module-level convenience alias
settings: Settings = get_settings()
