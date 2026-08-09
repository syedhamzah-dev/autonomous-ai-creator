import json
from typing import List, Any
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or a local .env file.
    """
    app_name: str = Field(default="Autonomous AI Creator", validation_alias="APP_NAME")
    app_env: str = Field(default="dev", validation_alias="APP_ENV")
    log_level: str = Field(default="info", validation_alias="LOG_LEVEL")
    host: str = Field(default="0.0.0.0", validation_alias="HOST")
    port: int = Field(default=8000, validation_alias="PORT")

    # RSS/Atom Feeds for Topic Discovery
    discovery_feeds: List[str] = Field(
        default=[
            "https://techcrunch.com/category/artificial-intelligence/feed/",
            "https://developer.nvidia.com/blog/feed/",
            "https://aws.amazon.com/blogs/machine-learning/feed/",
            "https://www.technologyreview.com/topic/artificial-intelligence/feed/"
        ],
        validation_alias="DISCOVERY_FEEDS"
    )

    @field_validator("discovery_feeds", mode="before")
    @classmethod
    def parse_discovery_feeds(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            # Try parsing as JSON array
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            # Fallback to comma-separated values
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    # Editorial Judgment Settings
    editorial_engine_type: str = Field(default="deterministic", validation_alias="EDITORIAL_ENGINE_TYPE")
    editorial_threshold: float = Field(default=6.0, validation_alias="EDITORIAL_THRESHOLD")

    # Autonomous Loop & Scheduling Settings
    autonomous_enabled: bool = Field(default=True, validation_alias="AUTONOMOUS_ENABLED")
    autonomous_interval_seconds: float = Field(default=3600.0, validation_alias="AUTONOMOUS_INTERVAL_SECONDS")

    # Discovery Timeout Settings
    discovery_timeout_seconds: float = Field(default=10.0, validation_alias="DISCOVERY_TIMEOUT_SECONDS")

    # Real LLM API Provider Settings
    llm_api_key: str | None = Field(default=None, validation_alias="LLM_API_KEY")
    llm_model: str = Field(default="gemini-2.0-flash", validation_alias="LLM_MODEL")

    # CORS Settings
    cors_origins: List[str] = Field(
        default=["http://localhost:8000", "http://127.0.0.1:8000"],
        validation_alias="CORS_ORIGINS"
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

