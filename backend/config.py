from typing import List
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_FILE_PATH = ROOT_DIR / ".env"

class Settings(BaseSettings):
    # --- App Metadata ---
    APP_TITLE: str = "Coeus AI"
    APP_DESCRIPTION: str = "Voice Based RAG Assistant"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ALLOWED_ORIGINS: List[str] = ["*"]

    # --- Groq Configuration ---
    GROQ_API_KEY: str
    GROQ_MODEL: str 

    # --- Gemini Configuration ---
    GEMINI_API_KEY: str
    GEMINI_MODEL: str

    # --- Supabase Configuration ---
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str  

    # --- Cohere Configuration ---
    CO_API_KEY: str 

    # --- Hugging Face & Embeddings ---
    HF_TOKEN: str
    HF_EMBEDDING_MODEL: str 

   
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore" 
    )

@lru_cache()
def get_settings() -> Settings:
    """
    Creates a singleton instance of the Settings.
    The @lru_cache decorator ensures the .env file is parsed only once.
    """
    return Settings()

# Global instance for easy import
settings = get_settings()