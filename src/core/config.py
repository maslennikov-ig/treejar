from __future__ import annotations

from typing import Any

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "treejar-ai-bot"
    app_env: str = "development"
    app_debug: bool = False
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_log_level: str = "INFO"
    app_secret_key: str = "change-me-in-production"

    # Database (Supabase Cloud)
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/treejar"
    database_url_direct: str | None = None  # For migrations (bypasses pooler)

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # OpenRouter (LLM)
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model_fast: str = "xiaomi/mimo-v2-flash"
    openrouter_model_main: str = "z-ai/glm-5"
    voxtral_model: str = "openai/gpt-audio-mini"

    # Wazzup (WhatsApp Gateway)
    wazzup_api_key: str = ""
    wazzup_api_url: str = "https://api.wazzup24.com/v3"
    wazzup_channel_id: str = ""  # UUID of the WhatsApp channel in Wazzup
    wazzup_allowed_ips: str = (
        ""  # Comma-separated CIDRs, e.g. "94.242.232.0/22,172.241.70.0/22"
    )

    # Zoho CRM
    zoho_crm_client_id: str = ""
    zoho_crm_client_secret: str = ""
    zoho_crm_refresh_token: str = ""
    zoho_crm_api_url: str = "https://www.zohoapis.eu/crm/v7"
    zoho_crm_accounts_url: str = "https://accounts.zoho.eu"

    # Zoho Inventory
    zoho_inventory_client_id: str = ""
    zoho_inventory_client_secret: str = ""
    zoho_inventory_refresh_token: str = ""
    zoho_inventory_api_url: str = "https://www.zohoapis.eu/inventory/v1"
    zoho_inventory_org_id: str = ""

    # Embeddings
    embedding_model: str = "BAAI/bge-m3"
    embedding_dimension: int = 1024

    # Admin Panel
    admin_username: str = "admin"
    admin_password: str = "change-me-admin-password"

    # Telegram Notifications (Stage 2)
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_allowed_inbound_phone: str = "+971551220665"

    # API key for internal endpoints (referrals, reports, notifications)
    api_key: str = ""

    # Domain (optional, for HTTPS)
    domain: str = ""

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def migration_database_url(self) -> str:
        """URL for Alembic migrations (direct connection, no pooler)."""
        return self.database_url_direct or self.database_url

    @model_validator(mode="after")
    def validate_production_secrets(self) -> Settings:
        if self.is_production:
            if self.app_secret_key == "change-me-in-production":
                raise ValueError("app_secret_key must be changed in production")
            if self.admin_password == "change-me-admin-password":
                raise ValueError("admin_password must be changed in production")
            if not self.api_key:
                raise ValueError("api_key must be set in production")
        return self


settings = Settings()


async def get_system_config(db: Any, key: str, default: str) -> str:
    """Fetch a configuration value from the DB, fallback to default."""
    from sqlalchemy import select

    from src.models.system_config import SystemConfig

    try:
        stmt = select(SystemConfig).where(SystemConfig.key == key)
        result = await db.execute(stmt)
        config = result.scalar_one_or_none()

        if config:
            return str(config.value)
    except Exception:
        import logging

        logging.getLogger(__name__).warning(
            "Failed to fetch system config '%s', using default", key
        )

    return default
