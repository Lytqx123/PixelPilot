import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    VERSION: str = "2.0.0"
    
    # CORS: 逗号分隔域名列表，空则默认允许本地地址
    CORS_ALLOWED_ORIGINS: str = ""

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/pixelpulse"
    QDRANT_URL: str = "http://localhost:6333"
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT配置，生产一定要改！
    SECRET_KEY: str = "pixelpulse-default-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8小时

    TEMP_TOKEN_EXPIRE_HOURS: int = 24
    APPLICATION_COOLDOWN_DAYS: int = 7
    UPLOAD_DIR: str = "./uploads"

    # Ollama 大模型配置
    LLM_API_URL: str = "http://localhost:11434/api/generate"
    LLM_MODEL: str = "qwen2.5:14b"
    LLM_NUM_CTX: int = 8192  # 上下文窗口，越大越慢

    # 大模型备用，默认关
    LLM_LARGE_ENABLED: bool = False
    LLM_LARGE_MODEL: str = "qwen2.5:14b"
    LLM_LARGE_API_URL: str = "http://localhost:11434/api/generate"
    LLM_LARGE_TEMPERATURE: float = 0.7

    # Embedding
    EMBEDDING_API_URL: str = "http://localhost:11434/api/embeddings"
    EMBEDDING_MODEL: str = "bge-m3"

    # 多模态：图纸/图片理解
    VISION_LLM_API_URL: str = "http://localhost:11434/api/generate"
    VISION_LLM_MODEL: str = "minicpm-v:8b"
    VISION_ENABLED: bool = True

    # Reranker精排，效果更好但更慢，机器差可以关
    RERANKER_API_URL: str = "http://localhost:11434/api/generate"
    RERANKER_MODEL: str = "dengcao/Qwen3-Reranker-4B"
    RERANKER_ENABLED: bool = True
    RERANKER_TOP_K: int = 5
    RERANKER_PREFETCH: int = 20

    # RAG分块参数，技术文档用1000/200差不多
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200

    # 上传文档去重阈值
    DEDUP_SIMILARITY_THRESHOLD: float = 0.98

    # 检索相关
    RETRIEVAL_TOP_K: int = 7
    RETRIEVAL_SIMILARITY_THRESHOLD: float = 0.35
    RETRIEVAL_PREFETCH_MULTIPLIER: int = 4
    PREVIEW_MAX_SEGMENTS: int = 3
    PREVIEW_MAX_CHARS: int = 120

    APPLICATION_EXPIRY_DAYS: int = 7
    WORKER_CLEANUP_INTERVAL: int = 3600

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "protected_namespaces": (),
    }


settings = Settings()


_DEFAULT_SECRET_KEY = "pixelpulse-default-secret-key-change-in-production"


def validate_secret_key() -> None:
    # 启动就检查密钥，别用默认的跑生产
    import sys
    if settings.SECRET_KEY == _DEFAULT_SECRET_KEY:
        if os.getenv("ALLOW_DEFAULT_SECRET", "0") == "1":
            return
        print(
            "[FATAL] SECRET_KEY 还是默认值！JWT会被伪造的\n"
            "去.env里改个随机字符串再启动\n"
            "本地开发嫌麻烦就设 ALLOW_DEFAULT_SECRET=1 跳过",
            file=sys.stderr,
        )
        raise SystemExit(1)