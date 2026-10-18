from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./narative.db"
    secret_key: str = "dev-secret-ganti-di-production-minimal-32-karakter"
    access_token_minutes: int = 60 * 24
    model_dir: str = "../model"
    upload_dir: str = "uploads"
    cors_origins: str = "http://localhost:5173"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    gemini_fallback_model: str = ""
    gemini_min_interval: float = 6.0
    seconds_per_paragraph: float = 0.5


settings = Settings()