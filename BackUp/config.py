from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    app_name: str = "AI Identity Access Gateway"
    app_env: str = "development"
    debug: bool = True

    database_url: str = "sqlite:///./gateway.db"

    admin_api_key: str = "change-me"

    huggingface_api_key: str
    huggingface_model: str = "meta-llama/Llama-3.1-8B-Instruct"
    gemini_api_key: str
    gemini_model: str = "gemini-3.8-flash"

    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_api_version: str = "2024-02-15-preview"
    azure_openai_deployment: str = "gpt-4o"

    jwt_issuer: str = "http://localhost:8000"
    jwt_audience: str = "ai-gateway"
    jwt_jwks_url: str = "http://localhost:8000/.well-known/jwks.json"

    session_ttl_minutes: int = 60

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

settings = Settings()

print("CONFIG FILE:", BASE_DIR / ".env")
#print("ADMIN KEY LOADED:", repr(settings.admin_api_key))

