from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AtlasAI"
    app_version: str = "0.2.0"
    environment: str = "development"
    debug: bool = False
    database_url: str = "sqlite:///./atlas_ai.db"
    auth_secret_key: str = "development-only-change-this-secret"
    access_token_expire_minutes: int = 60
    max_document_size_bytes: int = 5_000_000
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    reranker_model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    ollama_timeout_seconds: float = 120
    ocr_language: str = "eng"
    redis_url: str = "redis://localhost:6379/0"
    document_storage_backend: str = "local"
    local_document_storage_path: str = "./document_uploads"
    s3_endpoint_url: str | None = None
    s3_bucket: str | None = None
    s3_region: str = "us-east-1"
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @model_validator(mode="after")
    def validate_configuration(self) -> "Settings":
        if self.access_token_expire_minutes <= 0:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be positive")
        if self.max_document_size_bytes <= 0:
            raise ValueError("MAX_DOCUMENT_SIZE_BYTES must be positive")
        if self.ollama_timeout_seconds <= 0:
            raise ValueError("OLLAMA_TIMEOUT_SECONDS must be positive")
        if self.document_storage_backend not in {"local", "s3"}:
            raise ValueError("DOCUMENT_STORAGE_BACKEND must be either local or s3")
        if self.document_storage_backend == "s3" and not self.s3_bucket:
            raise ValueError("S3_BUCKET is required when document storage uses S3")
        if self.environment.lower() in {"production", "prod"} and (
            self.auth_secret_key
            in {
                "development-only-change-this-secret",
                "replace-with-a-random-secret-of-at-least-32-characters",
            }
            or len(self.auth_secret_key) < 32
        ):
            raise ValueError(
                "Set a unique AUTH_SECRET_KEY of at least 32 characters in production"
            )
        return self


settings = Settings()
