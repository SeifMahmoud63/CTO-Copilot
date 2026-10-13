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
    bedrock_model: str = Field(default="qwen.qwen3-32b")
    aws_access_key_id: str = Field(default="")
    aws_secret_access_key: str = Field(default="")
    aws_region: str = Field(default="us-west-2")
    aws_default_region: str = Field(default="us-west-2")

    # JEV Decision Model
    jev_api_key: str = Field(default="")
    jev_api_url: str = Field(default="https://api.typesafe.ai/v1/systemone")
    jev_model: str = Field(default="jev-latest")

    # Gemini (chatbot actor only — judge/summaries stay on Bedrock)
    gemini_api_key: str = Field(default="")
    gemini_base_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta/openai/")
    gemini_chat_model: str = Field(default="gemini-3.1-pro-preview")
    # Which backend drives the CHATBOT: "gemini" or "bedrock".
    chat_provider: str = Field(default="gemini")

    @property
    def chat_actor_model(self) -> str:
        """Model ID actually serving chat (for labels/metrics)."""
        if (self.chat_provider or "").strip().lower() == "gemini":
            return self.gemini_chat_model or self.bedrock_model
        return self.bedrock_model

    # Groq Fallback
    groq_api_key: str = Field(default="")
    groq_base_url: str = Field(default="https://api.groq.com/openai/v1")
    groq_model: str = Field(default="openai/gpt-oss-20b")
    groq_backup_model: str = Field(default="openai/gpt-oss-120b")

    # Hyperparameters
    llm_temperature: float = Field(default=0.2)
    llm_max_tokens: int = Field(default=1024)
    # Reasoning effort for the chat actor (low/medium/high/""). Empty = no reasoning.
    llm_reasoning_effort: str = Field(default="")

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

    @property
    def sync_database_url(self) -> str:
        """Sync-driver URL for Alembic (async drivers crash it)."""
        return self.async_database_url.replace(
            "mysql+aiomysql://", "mysql+pymysql://"
        ).replace("mysql+asyncmy://", "mysql+pymysql://")

    # Application
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000)
    static_dir: str = Field(default="web")

    # Chatbot Memory
    chat_memory_window_size: int = Field(default=10)

    # SSE streaming (Server-Sent Events token streaming for chat replies).
    # Runtime toggle via POST /api/chat/sse (Eval Lab button); resets on restart.
    chat_sse_enabled: bool = Field(default=False)

    # Chatbot Query Rewrite (standalone follow-up reformulation)
    chat_query_rewrite_window_size: int = Field(default=2)

    # LLM-as-a-Judge grounding gate (chat replies verified before delivery)
    judge_enabled: bool = Field(default=True)
    judge_model: str = Field(default="openai.gpt-oss-20b")
    # Max tokens for judge evaluation
    judge_max_tokens: int = Field(default=1024)
    # Empty-judge recovery: immediate retries, then a different model.
    # Fallback runs on GROQ (different provider/endpoint than the Bedrock
    # primary), so a Bedrock outage doesn't take the fallback down with it.
    # groq-style IDs contain "/" (e.g. "openai/gpt-oss-20b"), bedrock-style
    # IDs contain "." (e.g. "openai.gpt-oss-20b") — JudgeService routes each
    # model to its own client automatically. Empty = no fallback.
    judge_retries: int = Field(default=1)
    judge_fallback_model: str = Field(default="openai/gpt-oss-20b")

    # Email triage (IMAP polling, strictly read-only)
    email_enabled: bool = Field(default=False)
    email_imap_host: str = Field(default="imap.gmail.com")
    email_imap_port: int = Field(default=993)
    email_address: str = Field(default="")
    email_password: str = Field(default="")
    email_mailbox: str = Field(default="INBOX")
    email_unread_only: bool = Field(default=True)
    email_poll_interval_minutes: int = Field(default=3)
    email_max_body_chars: int = Field(default=4000)

    # S3-compatible object storage (MinIO with Web UI Console) —
    # ALL files live here, nothing on local disk.
    minio_endpoint: str = Field(default="http://localhost:9000")
    minio_access_key: str = Field(default="cto-minio-admin")
    minio_secret_key: str = Field(default="")
    minio_bucket_reports: str = Field(default="cto-reports")
    minio_bucket_mlflow: str = Field(default="mlflow-artifacts")
    minio_bucket_progress: str = Field(default="eval-progress")
    minio_secure: bool = Field(default=False)
    # MLflow artifact endpoint (S3 API, e.g. http://minio:9000 in compose).
    # Empty = derive from minio_endpoint.
    mlflow_s3_endpoint_url: str = Field(default="")

    # Eval Lab (MLflow experiment tracking — MySQL backend in prod, no local files)
    mlflow_tracking_uri: str = Field(default="sqlite:///./mlruns/mlflow.db")
    # Eval Lab concurrency: parallel question groups per run (1 = sequential).
    eval_max_concurrency: int = Field(default=3)

    # Celery Background Tasks
    celery_broker_url: str = Field(default="redis://redis:6379/0")
    celery_result_backend: str = Field(default="redis://redis:6379/0")

    # Daily CTO Report (scheduled)
    report_timezone: str = Field(default="Africa/Cairo")
    report_hour: int = Field(default=8)
    report_minute: int = Field(default=0)
    reports_dir: str = Field(default="reports")
    report_language: str = Field(default="English")

    # Deepgram Live Voice Agent
    deepgram_api_key: str = Field(default="")
    deepgram_agent_model: str = Field(default="nova-3")
    deepgram_voice_model: str = Field(default="aura-asteria-en")
    deepgram_agent_url: str = Field(default="wss://agent.deepgram.com/v1/agent/converse")

    # Slack Bot Integration
    slack_enabled: bool = Field(default=False)
    slack_bot_token: str = Field(default="")
    slack_channel_id: str = Field(default="")

    # Access Gate (shared password + Google Authenticator TOTP)
    cto_password: str = Field(default="")
    session_secret: str = Field(default="")
    session_max_age_hours: int = Field(default=12)
    remember_me_days: int = Field(default=7)
    totp_issuer: str = Field(default="CTO-Copilot")
    auth_max_attempts: int = Field(default=5)
    auth_lockout_seconds: int = Field(default=60)

settings = Settings()
