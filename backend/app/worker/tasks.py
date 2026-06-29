# 异步文档解析worker：从Redis取任务，解析完分块向量化入库

import json
import logging
import os
import sys
import time
import traceback
import uuid
from datetime import datetime, timedelta
from typing import Optional

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.config import settings
from app.worker.parsers import DocumentParser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("worker")

MAX_RETRIES = 3
RETRY_DELAY = 5
TOKEN_CLEANUP_INTERVAL = 3600  # 每小时清理一次
EMBEDDING_DELAY = 0.1


class TaskWorker:
    """后台任务处理器"""

    def __init__(self):
        try:
            import redis
            self.redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
            self.redis_client.ping()
            logger.info("Redis 连接成功")
        except Exception as e:
            logger.error(f"Redis 连接失败: {e}")
            self.redis_client = None

        sync_url = settings.DATABASE_URL.replace("+asyncpg", "+psycopg2")
        from sqlalchemy import create_engine
        self.db_engine = create_engine(sync_url, echo=False, pool_size=5)
        logger.info("数据库同步引擎已创建")

        from qdrant_client import QdrantClient
        from qdrant_client.http import models as qdrant_models
        self.qdrant_client = QdrantClient(url=settings.QDRANT_URL)
        self.qdrant_models = qdrant_models

        collection_exists = True
        try:
            self.qdrant_client.get_collection("document_chunks")
        except Exception:
            self.qdrant_client.create_collection(
                collection_name="document_chunks",
                vectors_config=qdrant_models.VectorParams(size=1024, distance=qdrant_models.Distance.COSINE),
            )
            logger.info("创建 Qdrant collection: document_chunks")
            collection_exists = True

        if collection_exists:
            payload_fields = [
                ("document_id", qdrant_models.PayloadSchemaType.INTEGER),
                ("department_id", qdrant_models.PayloadSchemaType.INTEGER),
                ("model_tag", qdrant_models.PayloadSchemaType.KEYWORD),
                ("region_tag", qdrant_models.PayloadSchemaType.KEYWORD),
                ("doc_type_tag", qdrant_models.PayloadSchemaType.KEYWORD),
                ("tags", qdrant_models.PayloadSchemaType.KEYWORD),
                ("status", qdrant_models.PayloadSchemaType.INTEGER),
                ("is_reviewed", qdrant_models.PayloadSchemaType.BOOL),
                ("is_public_to_all", qdrant_models.PayloadSchemaType.BOOL),
            ]
            for field_name, field_type in payload_fields:
                try:
                    self.qdrant_client.create_payload_index(
                        collection_name="document_chunks",
                        field_name=field_name,
                        field_schema=field_type,
                    )
                except Exception:
                    pass
            logger.info("Qdrant payload 索引已就绪")

        self.parser = DocumentParser()
        self._last_cleanup = time.time()

    def run(self):
        """主循环：阻塞等待 Redis 任务 → 处理任务 → 定期清理"""
        if not self.redis_client:
            logger.error("Redis 不可用，Worker 退出")
            return

        logger.info("=" * 50)
        logger.info("TaskWorker 已启动，监听队列: doc_parse_queue")
        logger.info("=" * 50)

        while True:
            try:
                now = time.time()
                if now - self._last_cleanup > TOKEN_CLEANUP_INTERVAL:
                    self._cleanup_expired_tokens()
                    self._cleanup_expired_applications()
                    self._last_cleanup = now

                result = self.redis_client.brpop("doc_parse_queue", timeout=5)
                if result is None:
                    continue

                _, task_json = result
                task_data = json.loads(task_json)
                logger.info(f"获取到任务: document_id={task_data.get('document_id')}")

                self._process_task_with_retry(task_data)

            except KeyboardInterrupt:
                logger.info("Worker 收到中断信号，正在退出...")
                break
            except Exception as e:
                logger.error(f"Worker 主循环异常: {e}\n{traceback.format_exc()}")
                time.sleep(1)

    def _process_task_with_retry(self, task_data: dict):
        document_id = task_data.get("document_id")
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                self.process_task(task_data)
                logger.info(f"[OK] 任务处理完成: document_id={document_id}")
                return
            except Exception as e:
                logger.error(f"[RETRY {attempt}/{MAX_RETRIES}] 任务处理失败: document_id={document_id}, error={e}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                else:
                    logger.error(f"[FAIL] 任务最终失败: document_id={document_id}")

    def process_task(self, task_data: dict):
        document_id = task_data["document_id"]
        file_path = task_data["file_path"]
        file_type = task_data["file_type"]
        tags = task_data.get("tags", [])
        department_id = task_data.get("department_id")

        logger.info(f"  步骤1 - 解析文档: {file_path} (type={file_type})")
        parsed_chunks = self.parser.parse(file_path, file_type)
        if not parsed_chunks:
            parsed_chunks = [{"content": f"[空文档] {os.path.basename(file_path)}", "page_number": 1, "paragraph": ""}]

        logger.info(f"  解析完成，共 {len(parsed_chunks)} 个原始块")

        logger.info(f"  步骤2 - 文本分块 (chunk_size={settings.CHUNK_SIZE}, overlap={settings.CHUNK_OVERLAP})...")
        all_chunks: list[dict] = []
        for parsed in parsed_chunks:
            sub_chunks = self.parser.chunk_text(parsed["content"], chunk_size=settings.CHUNK_SIZE, overlap=settings.CHUNK_OVERLAP)
            for sub_text in sub_chunks:
                all_chunks.append({
                    "content": sub_text,
                    "page_number": parsed["page_number"],
                    "paragraph": parsed["paragraph"],
                    "vector_id": str(uuid.uuid4()),
                })

        logger.info(f"  分块完成，共 {len(all_chunks)} 个片段")
        if not all_chunks:
            return

        logger.info(f"  步骤3 - 向量化 ({len(all_chunks)} 个片段)...")
        for i, chunk in enumerate(all_chunks):
            chunk["vector"] = self._embed_text(chunk["content"])
            if (i + 1) % 10 == 0:
                logger.info(f"    向量化进度: {i + 1}/{len(all_chunks)}")
            if EMBEDDING_DELAY > 0:
                time.sleep(EMBEDDING_DELAY)

        logger.info(f"  向量化完成")
        doc_info = self._get_document_info(document_id)
        doc_status = doc_info["status"]
        logger.info(f"  步骤4 - 存储数据...")
        self._store_chunks(
            document_id, all_chunks, tags,
            doc_status=doc_status, file_path=file_path, department_id=department_id,
            is_public_to_all=doc_info["is_public_to_all"], uploader_id=doc_info["uploader_id"],
        )
        logger.info(f"  步骤5 - 更新文档状态...")
        self._update_document_status(document_id, chunk_count=len(all_chunks))

    def _embed_text(self, text: str) -> list[float]:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                settings.EMBEDDING_API_URL,
                json={"model": settings.EMBEDDING_MODEL, "prompt": text},
            )
            response.raise_for_status()
            embedding = response.json().get("embedding", [])
            if len(embedding) == 1024:
                return embedding
            raise RuntimeError(f"Embedding 维度异常: 期望 1024，实际 {len(embedding)}")

    def _get_document_status(self, document_id: int) -> int:
        """获取文档审核状态(兼容旧调用,返回 status int)"""
        info = self._get_document_info(document_id)
        return info.get("status", 0)

    def _get_document_info(self, document_id: int) -> dict:
        """获取文档完整信息:status, is_public_to_all, uploader_id（使用 ORM）"""
        from sqlalchemy import select
        from sqlalchemy.orm import Session
        from app.models.document import Document

        with Session(self.db_engine) as session:
            result = session.execute(
                select(Document.status, Document.is_public_to_all, Document.uploader_id).where(
                    Document.id == document_id
                )
            )
            row = result.fetchone()
            if row:
                return {
                    "status": row[0] or 0,
                    "is_public_to_all": row[1] or 0,
                    "uploader_id": row[2],
                }
            return {"status": 0, "is_public_to_all": 0, "uploader_id": None}

    def _store_chunks(self, document_id, chunks, tags, doc_status=0, file_path="", department_id=None, is_public_to_all=0, uploader_id=None):
        from sqlalchemy.orm import Session
        from app.models.document import DocumentChunk

        # 使用 ORM 批量写入 document_chunks，确保字段默认值/约束一致
        with Session(self.db_engine) as session:
            for chunk in chunks:
                session.add(
                    DocumentChunk(
                        document_id=document_id,
                        content=chunk["content"],
                        page_number=chunk["page_number"],
                        paragraph=chunk["paragraph"],
                        vector_id=chunk["vector_id"],
                    )
                )
            session.commit()
        logger.info(f"    已写入 {len(chunks)} 条 document_chunks 记录")

        # 构建标签结构：通用标签名列表 + 按分类分组的标签
        tag_names = [t.get("name", "") for t in tags if t.get("name")]
        tags_by_category = {}
        for t in tags:
            cat_code = t.get("category_code")
            tag_name = t.get("name")
            if cat_code and tag_name:
                if cat_code not in tags_by_category:
                    tags_by_category[cat_code] = []
                tags_by_category[cat_code].append(tag_name)

        # 构建payload
        payload_base = {
            "document_id": document_id,
            "department_id": department_id,
            "tags": tag_names,
            "status": doc_status,
            "is_reviewed": (doc_status == 1),
            "is_public_to_all": is_public_to_all,
            "uploader_id": uploader_id,
            "document_name": os.path.basename(file_path) if file_path else "",
        }

        # 添加按分类的标签字段
        for cat_code, tag_list in tags_by_category.items():
            payload_base[f"tag_{cat_code}"] = tag_list

        qdrant_points = []
        for chunk in chunks:
            point_payload = payload_base.copy()
            point_payload.update({
                "page_number": chunk["page_number"],
                "paragraph": chunk["paragraph"],
                "content": chunk["content"][:200],
            })
            qdrant_points.append(
                self.qdrant_models.PointStruct(
                    id=chunk["vector_id"],
                    vector=chunk["vector"],
                    payload=point_payload,
                )
            )

        self.qdrant_client.upsert(collection_name="document_chunks", points=qdrant_points, wait=True)
        logger.info(f"    已写入 {len(qdrant_points)} 个 Qdrant 向量点，标签: {tag_names}")

    def _update_document_status(self, document_id, chunk_count):
        """更新文档解析状态:记录分块数量、标记为已解析、记录解析完成时间（使用 ORM）"""
        from datetime import datetime, timezone
        from sqlalchemy import select
        from sqlalchemy.orm import Session
        from app.models.document import Document

        try:
            with Session(self.db_engine) as session:
                result = session.execute(
                    select(Document).where(Document.id == document_id)
                )
                doc = result.scalar_one_or_none()
                if doc:
                    doc.chunk_count = chunk_count
                    doc.is_parsed = 1
                    doc.parsed_at = datetime.now(timezone.utc)
                    session.commit()
                else:
                    logger.warning(f"    文档不存在: document_id={document_id}")
            logger.info(f"    文档解析状态已更新: document_id={document_id}, chunks={chunk_count}, is_parsed=1")
        except Exception as e:
            logger.error(f"    更新文档解析状态失败: document_id={document_id}, error={e}")
            try:
                with Session(self.db_engine) as session:
                    session.rollback()
            except Exception:
                pass

    def _cleanup_expired_tokens(self):
        """清理过期的临时访问令牌（使用 ORM）"""
        try:
            from datetime import datetime, timezone
            from sqlalchemy import delete
            from sqlalchemy.orm import Session
            from app.models.temp_token import TempAccessToken

            with Session(self.db_engine) as session:
                result = session.execute(
                    delete(TempAccessToken).where(
                        TempAccessToken.expires_at < datetime.now(timezone.utc)
                    )
                )
                deleted = result.rowcount
                session.commit()
            if deleted > 0:
                logger.info(f"[CLEANUP] 已清理 {deleted} 个过期临时令牌")
        except Exception as e:
            logger.warning(f"[CLEANUP] 清理过期令牌失败: {e}")

    def _cleanup_expired_applications(self):
        """将超过7天未处理的待审核申请自动标记为已拒绝（status=2），移入审核历史（使用 ORM）"""
        try:
            from datetime import datetime, timedelta, timezone
            from sqlalchemy import select
            from sqlalchemy.orm import Session
            from app.models.access_application import AccessApplication

            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            with Session(self.db_engine) as session:
                result = session.execute(
                    select(AccessApplication).where(
                        AccessApplication.status == 0,
                        AccessApplication.created_at < cutoff,
                    )
                )
                expired_apps = result.scalars().all()
                now = datetime.now(timezone.utc)
                for app in expired_apps:
                    app.status = 2
                    app.review_time = now
                session.commit()
                expired = len(expired_apps)
            if expired > 0:
                logger.info(f"[CLEANUP] 已将 {expired} 个超过7天的待审核申请标记为已拒绝")
        except Exception as e:
            logger.warning(f"[CLEANUP] 过期申请清理失败: {e}")


if __name__ == "__main__":
    worker = TaskWorker()
    print("Worker started, listening for tasks on doc_parse_queue...")
    worker.run()