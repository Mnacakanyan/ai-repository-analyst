"""
Configuration and Environment Settings for AI Repository Analyst.
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Automatically load .env from project root or current working directory
load_dotenv()


class Settings:
    """Application configuration resolved from environment variables."""

    # LLM API Keys
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")

    # GitHub Access Token (optional for public repositories, increases rate limits from 60 to 5,000 req/hr)
    GITHUB_TOKEN: Optional[str] = os.getenv("GITHUB_TOKEN")

    # Default Models
    DEFAULT_PROVIDER: str = os.getenv("DEFAULT_PROVIDER", "anthropic").lower()
    DEFAULT_ANTHROPIC_MODEL: str = os.getenv("DEFAULT_ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
    DEFAULT_OPENAI_MODEL: str = os.getenv("DEFAULT_OPENAI_MODEL", "gpt-4o")

    # Agent Execution Boundaries
    MAX_TURNS: int = int(os.getenv("MAX_TURNS", "15"))
    MAX_TOTAL_COST_USD: float = float(os.getenv("MAX_TOTAL_COST_USD", "1.50"))
    MAX_FILE_READ_BYTES: int = int(os.getenv("MAX_FILE_READ_BYTES", "60000"))
    MAX_TREE_ITEMS: int = int(os.getenv("MAX_TREE_ITEMS", "300"))

    # Project directories
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    OUTPUT_DIR: Path = Path(os.getenv("OUTPUT_DIR", str(BASE_DIR / "reports")))

    @classmethod
    def ensure_output_dir(cls) -> Path:
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        return cls.OUTPUT_DIR


settings = Settings()
