import os
from typing import List
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Explicitly load environment variables from .env file before settings initialization
load_dotenv()


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and an optional .env file.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # OpenRouter Config
    OPENROUTER_API_KEY: str
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    LLM_MODEL: str = "qwen/qwen3-30b-a3b:free"
    LLM_FALLBACK_MODELS: List[str] = [
        "openrouter/free",
        "cohere/north-mini-code:free",
        "openai/gpt-oss-20b:free"
    ]

    # Supabase / DB Config
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    DATABASE_URL: str
    SESSION_TIMEOUT_HOURS: int = 3
    CLEANUP_INTERVAL_MINUTES: int = 10
    RESET_DATABASE_ON_START: bool = False

    # Local Storage Config
    UPLOAD_DIR: str = "./data/uploads"
    REPO_DIR: str = "./data/repos"

    @property
    def upload_path(self) -> Path:
        """Returns the resolved Path for uploads directory."""
        path = Path(self.UPLOAD_DIR).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def repo_path(self) -> Path:
        """Returns the resolved Path for repositories directory."""
        path = Path(self.REPO_DIR).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path


# Global settings instance
settings = Settings()
