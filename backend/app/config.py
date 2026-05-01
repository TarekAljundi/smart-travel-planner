# backend/app/config.py
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -------------------------- Required secrets --------------------------
    database_url: str = Field(..., min_length=1)
    groq_api_key: str = Field(..., min_length=1)
    secret_key: str = Field(..., min_length=1)
    webhook_url: str = Field(..., min_length=1)
    webhook_gmail_address: str = Field(..., min_length=1)   # your Gmail address
    webhook_gmail_app_password: str = Field(..., min_length=1)
    
    # LangSmith tracing (optional – only needed if you want tracing)
    langsmith_tracing: str = "false"
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_api_key: str = ""
    langsmith_project: str = "Smart-Travel-Planner"

    # -------------------------- Groq --------------------------
    groq_api_base: str = "https://api.groq.com/openai/v1"
    cheap_model: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    strong_model: str = "llama-3.3-70b-versatile"

    # -------------------------- Embedding --------------------------
    embedding_model: str = "all-MiniLM-L6-v2"

    # -------------------------- ML model path --------------------------
    ml_model_path: str = "pipeline/classifier_pipeline.joblib"

    # -------------------------- RAG / vector store --------------------------
    vector_table_name: str = "destination_chunks"
    embedding_dim: int = 384
    rag_top_k: int = 3                    # how many chunks the RAG tool retrieves

    # -------------------------- Live APIs (Open‑Meteo) --------------------------
    weather_api_url: str = "https://api.open-meteo.com/v1/forecast"
    geocoding_api_url: str = "https://geocoding-api.open-meteo.com/v1/search"
    weather_cache_ttl: int = 600          # seconds (10 minutes)

    # -------------------------- JWT --------------------------
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # -------------------------- Logging --------------------------
    log_level: str = "INFO"

    # -------------------------- Knowledge base storage --------------------------
    knowledge_base_dir: str = "knowledge_base"   # folder with .txt files

    # -------------------------- Webhook retries --------------------------
    webhook_retry_attempts: int = 3
    webhook_retry_backoff_multiplier: float = 1.0
    webhook_retry_backoff_min: int = 1          # seconds
    webhook_retry_backoff_max: int = 10         # seconds
    webhook_timeout: float = 5.0                # seconds

    # -------------------------- Weather geocoding aliases --------------------------
    # (mapping of “destination name” → “city name the API understands”)
    weather_city_aliases: dict = {
        "amalfi coast": "Amalfi",
        "cinque terre": "Riomaggiore",
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()