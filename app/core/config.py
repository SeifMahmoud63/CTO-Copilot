import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # GitHub
    github_token: str = Field(default="")
    github_repo: str = Field(default="SeifMahmoud63/CTO-Copilot")
    github_api_url: str = Field(default="https://api.github.com")
    github_poll_interval_seconds: int = Field(default=30)
    pr_stale_threshold_days: int = Field(default=5)

    # Bedrock
    bedrock_api_key: str = Field(default="")
    bedrock_base_url: str = Field(default="https://bedrock-mantle.us-west-2.api.aws/openai/v1")
    bedrock_base_url_qwen: str = Field(default="https://bedrock-mantle.us-west-2.api.aws/v1")
    bedrock_vision_model: str = Field(default="us.amazon.nova-pro-v1:0")
    bedrock_model: str = Field(default="Qwen3-32B")
    aws_access_key_id: str = Field(default="")
    aws_secret_access_key: str = Field(default="")
    aws_region: str = Field(default="us-west-2")
    aws_default_region: str = Field(default="us-west-2")

    # JEV Decision Model
    jev_api_key: str = Field(default="")
    jev_api_url: str = Field(default="https://api.typesafe.ai/v1/systemone")
    jev_model: str = Field(default="jev-latest")

    # Groq Fallback
    groq_api_key: str = Field(default="")
    groq_model: str = Field(default="openai/gpt-oss-20b")
    groq_backup_model: str = Field(default="openai/gpt-oss-120b")

    # Hyperparameters
    llm_temperature: float = Field(default=0.2)
    llm_max_tokens: int = Field(default=1024)

    # Circuit Breaker
    circuit_breaker_cooldown_seconds: int = Field(default=1800)
    circuit_breaker_probe_prompt: str = Field(default="ping")

    # MySQL Async Database
    mysql_host: str = Field(default="mysql")
    mysql_port: int = Field(default=3306)
    mysql_user: str = Field(default="cto_user")
    mysql_password: str = Field(default="cto_password_2026")
    mysql_database: str = Field(default="cto_copilot_db")
    database_url: Optional[str] = Field(default=None)

    @property
    def async_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"mysql+aiomysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
        )

    # Application
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000)
    static_dir: str = Field(default="web")

settings = Settings()
