# backend/app/config.py
from __future__ import annotations
import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # --- App basics ---
    jwt_secret: str = "dev-secret-change-me"

    # Google OAuth (compose에서는 APP_GOOGLE_CLIENT_ID 사용 권장)
    google_client_id: str = ""

    # CORS (쉼표로 여러개 가능)
    backend_cors_origins: str = "http://localhost:3000"

    # Paths
    media_dir: str = "/app/media"
    sqlite_path: str = "/app/db/app.db"

    # Snowflake (옵션)
    snowflake_account: str | None = None
    snowflake_user: str | None = None
    snowflake_password: str | None = None
    snowflake_role: str | None = None
    snowflake_warehouse: str | None = None
    snowflake_database: str | None = None
    snowflake_schema: str | None = None

    # .env/compose 에서 APP_ 프리픽스 읽기
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    def __init__(self, **values):
        super().__init__(**values)

        def _get_clean(*keys: str) -> str | None:
            for k in keys:
                v = os.getenv(k)
                if not v:
                    continue
                v = v.strip()
                if "#" in v:
                    v = v.split("#", 1)[0].rstrip()
                if v:
                    return v
            return None

        # Google: APP_GOOGLE_CLIENT_ID 없으면 GOOGLE_CLIENT_ID 폴백
        if not self.google_client_id:
            alt = _get_clean("GOOGLE_CLIENT_ID")
            if alt:
                object.__setattr__(self, "google_client_id", alt)
        if not self.google_client_id:
            raise ValueError(
                "google_client_id is required. "
                "Set APP_GOOGLE_CLIENT_ID (preferred) or GOOGLE_CLIENT_ID."
            )

        # Snowflake: APP_* 우선, 없으면 SNOWFLAKE_* 폴백 (+ 주석/공백 제거)
        def _fallback(field: str, *env_names: str):
            cur = getattr(self, field, None)
            if cur in (None, ""):
                val = _get_clean(*env_names)
                if val:
                    object.__setattr__(self, field, val)

        # account 는 ACCOUNT_IDENTIFIER 별칭도 지원
        _fallback("snowflake_account",
                  "APP_SNOWFLAKE_ACCOUNT", "SNOWFLAKE_ACCOUNT", "SNOWFLAKE_ACCOUNT_IDENTIFIER")
        _fallback("snowflake_user",
                  "APP_SNOWFLAKE_USER", "SNOWFLAKE_USER")
        _fallback("snowflake_password",
                  "APP_SNOWFLAKE_PASSWORD", "SNOWFLAKE_PASSWORD")
        _fallback("snowflake_role",
                  "APP_SNOWFLAKE_ROLE", "SNOWFLAKE_ROLE")
        _fallback("snowflake_warehouse",
                  "APP_SNOWFLAKE_WAREHOUSE", "SNOWFLAKE_WAREHOUSE")
        _fallback("snowflake_database",
                  "APP_SNOWFLAKE_DATABASE", "SNOWFLAKE_DATABASE")
        _fallback("snowflake_schema",
                  "APP_SNOWFLAKE_SCHEMA", "SNOWFLAKE_SCHEMA")

settings = Settings()
