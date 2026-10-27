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
    gemini_character_model: str = ""
    gemini_min_interval: float = 6.0
    ner_model: str = "Davlan/xlm-roberta-base-ner-hrl"
    seconds_per_paragraph: float = 0.5
    # Khusus pengembangan: perlakukan semua akun sebagai High Tier agar semua fitur bisa dites tanpa pembayaran
    dev_unlock_all_tiers: bool = False

    # Pembayaran: tanpa kunci Midtrans, pembayaran berjalan dalam mode simulasi (tanpa uang sungguhan)
    midtrans_server_key: str = ""
    midtrans_is_production: bool = False
    # Invoice via email: tanpa smtp_host, invoice hanya dicatat di log server
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "NARAtive <no-reply@narative.local>"


settings = Settings()