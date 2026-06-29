import asyncio
import json
import logging
import re
from contextlib import asynccontextmanager

import httpx
from sqlalchemy import text as sa_text
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    AuthenticationError,
    PermissionDeniedError,
    ResourceNotFoundError,
    BusinessError,
)
from app.routers import auth, admin, review, knowledge, documents, export

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.database import async_engine
    from app.services.vector_service import VectorService
    from app.config import settings, validate_secret_key

    validate_secret_key()

    db_ok = False
    redis_ok = False
    qdrant_ok = False

    try:
        async with async_engine.connect() as conn:
            await conn.execute(sa_text("SELECT 1"))
        db_ok = True
        logger.info("✅ PostgreSQL 数据库连接正常")
    except Exception as e:
        logger.error(f"❌ 数据库连接失败: {e}")

    try:
        import redis.asyncio as aioredis
        redis_client = aioredis.from_url(settings.REDIS_URL)
        await redis_client.ping()
        await redis_client.close()
        redis_ok = True
        logger.info("✅ Redis 连接正常")
    except Exception as e:
        logger.warning(f"⚠️  Redis 连接失败（非致命）: {e}")

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{settings.QDRANT_URL}/collections", timeout=5.0)
            resp.raise_for_status()
        qdrant_ok = True
        logger.info("✅ Qdrant 连接正常")
    except Exception as e:
        logger.warning(f"⚠️  Qdrant 连接失败（非致命）: {e}")

    try:
        await VectorService.init_qdrant_collection()
        logger.info("✅ Qdrant collection 已就绪")
    except Exception as e:
        logger.warning(f"⚠️  Qdrant 初始化失败（非致命）: {e}")

    try:
        from app.core.init_data import init_database_data
        await init_database_data()
        logger.info("✅ 数据库初始数据已就绪")
    except Exception as e:
        logger.error(f"❌ 数据库初始数据初始化失败: {e}", exc_info=True)

    from app.core.http_client import init_shared_client, close_shared_client
    await init_shared_client()
    logger.info("✅ 共享 HTTP 客户端已就绪")

    if db_ok:
        logger.info("🚀 All services connected successfully. PixelPulse Engine is running!")
    else:
        logger.error("🚀 PixelPulse Engine started (database connection failed, please check)")

    yield

    logger.info("PixelPulse 正在关闭...")
    await close_shared_client()


# 统一去掉响应时间里的微秒，前端显示好看点
_ISO_DATETIME_RE = re.compile(r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\.\d+')


def _strip_microseconds(obj):
    if isinstance(obj, dict):
        return {k: _strip_microseconds(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_strip_microseconds(i) for i in obj]
    if isinstance(obj, str):
        return _ISO_DATETIME_RE.sub(r'\1', obj)
    return obj


class SecondPrecisionJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        return json.dumps(
            _strip_microseconds(content),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")


app = FastAPI(
    title="PixelPulse 多模态RAG知识库引擎",
    description="面向企业的私有化多模态RAG知识库引擎",
    version="2.0.0",
    lifespan=lifespan,
    default_response_class=SecondPrecisionJSONResponse,
)


def _parse_cors_origins(origins_str: str) -> list:
    if not origins_str or not origins_str.strip():
        return [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    return [origin.strip() for origin in origins_str.split(",") if origin.strip()]


from app.config import settings as _settings

_cors_origins = _parse_cors_origins(_settings.CORS_ALLOWED_ORIGINS)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
)


# 全局异常处理
@app.exception_handler(AuthenticationError)
async def auth_exception_handler(request: Request, exc: AuthenticationError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": exc.detail, "error_code": "AUTHENTICATION_ERROR"},
    )


@app.exception_handler(PermissionDeniedError)
async def permission_exception_handler(request: Request, exc: PermissionDeniedError):
    content = {"code": exc.status_code, "detail": exc.detail, "error_code": "PERMISSION_DENIED"}
    if exc.extra:
        for key, value in exc.extra.items():
            content[key] = value
    return JSONResponse(status_code=exc.status_code, content=content)


@app.exception_handler(ResourceNotFoundError)
async def not_found_exception_handler(request: Request, exc: ResourceNotFoundError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": exc.detail, "error_code": "RESOURCE_NOT_FOUND"},
    )


@app.exception_handler(BusinessError)
async def business_exception_handler(request: Request, exc: BusinessError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": exc.detail, "error_code": "BUSINESS_ERROR"},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"未捕获的异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": "服务器内部错误，请稍后重试", "error_code": "INTERNAL_ERROR"},
    )


app.include_router(auth.router, prefix="/api", tags=["认证管理"])
app.include_router(admin.router, prefix="/api", tags=["超级管理员"])
app.include_router(review.router, prefix="/api", tags=["审核工作流"])
app.include_router(knowledge.router, prefix="/api", tags=["智能问答"])
app.include_router(documents.router, prefix="/api", tags=["文档管理"])
app.include_router(export.router, prefix="/api", tags=["数据导出"])


@app.get("/api/health")
async def health_check():
    from app.database import async_engine
    from app.config import settings

    result = {"status": "healthy", "services": {}}

    try:
        async with async_engine.connect() as conn:
            await conn.execute(sa_text("SELECT 1"))
        result["services"]["db"] = "ok"
    except Exception:
        result["services"]["db"] = "error"
        result["status"] = "unhealthy"

    try:
        import redis.asyncio as aioredis
        redis_client = aioredis.from_url(settings.REDIS_URL)
        await redis_client.ping()
        await redis_client.close()
        result["services"]["redis"] = "ok"
    except Exception:
        result["services"]["redis"] = "error"
        result["status"] = "unhealthy"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{settings.QDRANT_URL}/collections", timeout=5.0)
            resp.raise_for_status()
        result["services"]["qdrant"] = "ok"
    except Exception:
        result["services"]["qdrant"] = "error"
        result["status"] = "unhealthy"

    return result


@app.get("/")
async def root():
    return {"message": "PixelPulse API", "version": "2.0.0", "docs": "/docs"}
