from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./narative.db"
    secret_key: str = "dev-secret-ganti-di-production-minimal-32-karakter"
    access_token_minutes: int = 60 * 24
    model_dir: str = "../model"
    upload_dir: str = "uploads"
    cors_origins: str = "http://localhost:5173"
    gemini_api_key: str = ""                  # UC-09: kunci Gemini API (isi di .env: GEMINI_API_KEY)
    gemini_model: str = "gemini-3.5-flash-lite"
    seconds_per_paragraph: float = 0.5        # dasar estimasi waktu analisis (perkiraan kasar)


settings = Settings()