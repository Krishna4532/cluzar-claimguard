from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "ClaimGuard"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    APP_ENV: str = "development"

    DATABASE_URL: Optional[str] = "postgresql+psycopg://postgres:postgres@localhost:5432/claimguard_dev"

    # Embedding Configuration (sentence-transformers / all-MiniLM-L6-v2 produces 384-dim dense vectors)
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384

    # Chunking Configuration (RecursiveCharacterTextSplitter)
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 75

    OPENAI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()

