import logging
from typing import List, Dict, Any

import httpx

from app.config import settings
from app.core.http_client import get_shared_client

logger = logging.getLogger(__name__)


class VectorService:
    """Qdrant 向量数据库服务封装"""

    COLLECTION_NAME = "document_chunks"

    @staticmethod
    async def init_qdrant_collection() -> None:
        """检查并初始化 Qdrant collection，配置 payload 索引"""
        client = get_shared_client()
        base_url = settings.QDRANT_URL
        coll_url = f"{base_url}/collections/{VectorService.COLLECTION_NAME}"

        resp = await client.get(coll_url, timeout=10.0)
        if resp.status_code == 200:
            logger.info("Qdrant collection 已存在")
            return

        # 创建 collection
        await client.put(
            coll_url,
            json={
                "vectors": {
                    "size": 1024,
                    "distance": "Cosine",
                }
            },
            timeout=10.0,
        )
        logger.info("Qdrant collection 已创建")

        # 配置 payload 索引
        index_url = f"{coll_url}/index"
        payload_fields = [
            {"field_name": "document_id", "field_type": "integer"},
            {"field_name": "department_id", "field_type": "integer"},
            {"field_name": "model_tag", "field_type": "keyword"},
            {"field_name": "region_tag", "field_type": "keyword"},
            {"field_name": "doc_type_tag", "field_type": "keyword"},
            {"field_name": "status", "field_type": "integer"},
            {"field_name": "is_reviewed", "field_type": "bool"},
        ]
        for field in payload_fields:
            try:
                await client.put(
                    index_url,
                    json=field,
                    timeout=5.0,
                )
            except Exception:
                pass  # 索引可能已存在

    @staticmethod
    async def embed_text(text: str):
        """调用 Embedding API 对文本进行向量化，失败时返回降级随机向量"""
        try:
            client = get_shared_client()
            response = await client.post(
                settings.EMBEDDING_API_URL,
                json={"model": settings.EMBEDDING_MODEL, "prompt": text},
                timeout=10.0,
            )
            response.raise_for_status()
            embedding = response.json().get("embedding", [])
            if len(embedding) == 1024:
                return embedding
        except Exception as e:
            logger.warning(f"向量化 API 调用失败，使用降级方案: {e}")

        # 降级方案：返回 None 表示向量化失败，调用方应做相应处理
        logger.error("Embedding API 调用完全失败，向量化不可用")
        return None

    @staticmethod
    async def upsert_vectors(chunks: List[Dict[str, Any]]) -> None:
        """批量写入向量点到 Qdrant（标签按数组存储，以支持数组匹配过滤）"""
        client = get_shared_client()
        url = f"{settings.QDRANT_URL}/collections/{VectorService.COLLECTION_NAME}/points"
        points = []
        for chunk in chunks:
            model_tag_raw = chunk.get("model_tag", "")
            region_tag_raw = chunk.get("region_tag", "")
            doc_type_tag_raw = chunk.get("doc_type_tag", "")

            model_tag_list = [t.strip() for t in model_tag_raw.split(",") if t.strip()] if isinstance(model_tag_raw, str) and model_tag_raw else []
            region_tag_list = [t.strip() for t in region_tag_raw.split(",") if t.strip()] if isinstance(region_tag_raw, str) and region_tag_raw else []
            doc_type_tag_list = [t.strip() for t in doc_type_tag_raw.split(",") if t.strip()] if isinstance(doc_type_tag_raw, str) and doc_type_tag_raw else []

            payload = {
                "document_id": chunk.get("document_id", 0),
                "department_id": chunk.get("department_id"),
                "model_tag": model_tag_list,
                "region_tag": region_tag_list,
                "doc_type_tag": doc_type_tag_list,
                "status": chunk.get("status", 0),
                "is_reviewed": chunk.get("is_reviewed", False),
                "page_number": chunk.get("page_number", 0),
                "paragraph": chunk.get("paragraph", ""),
                "content": chunk.get("content", ""),
            }
            points.append({
                "id": chunk["vector_id"],
                "vector": chunk["vector"],
                "payload": payload,
            })
        await client.put(url, json={"points": points}, timeout=30.0)

    @staticmethod
    async def search_vectors(
        query_vector: List[float], qdrant_filter: dict, top_k: int = 5
    ) -> List[dict]:
        """向量检索，返回 top_k 个最相似结果"""
        client = get_shared_client()
        url = f"{settings.QDRANT_URL}/collections/{VectorService.COLLECTION_NAME}/points/search"
        response = await client.post(
            url,
            json={
                "vector": query_vector,
                "limit": top_k,
                "filter": qdrant_filter,
                "with_payload": True,
                "with_vector": False,
            },
            timeout=15.0,
        )
        response.raise_for_status()
        results = response.json().get("result", [])
        return [
            {
                "vector_id": r.get("id", ""),
                "score": r.get("score", 0),
                "payload": r.get("payload", {}),
            }
            for r in results
        ]

    @staticmethod
    async def update_vector_review_status(document_id: int, is_reviewed: bool) -> None:
        """更新指定文档所有向量的 is_reviewed 字段"""
        client = get_shared_client()
        url = f"{settings.QDRANT_URL}/collections/{VectorService.COLLECTION_NAME}/points/payload"
        await client.post(
            url,
            json={
                "payload": {"is_reviewed": is_reviewed, "status": 1},
                "filter": {
                    "must": [
                        {"key": "document_id", "match": {"value": document_id}}
                    ]
                },
            },
            timeout=15.0,
        )

    @staticmethod
    async def check_duplicate(content_bytes: bytes, filename: str, threshold: float = None) -> tuple:
        """
        检查上传文件内容是否与知识库中已有文档高度重复。
        提取文件文本指纹 → 向量化 → Qdrant 搜索 → 余弦相似度比对。

        返回: (is_duplicate: bool, similar_document_name: str, max_similarity: float)
        """
        import re

        # 1. 提取文本指纹（文本文件直接用内容，二进制文件用文件名+大小）
        fingerprint = ""
        try:
            text = content_bytes.decode("utf-8", errors="ignore")
            # 只取前 2000 个有效字符
            cleaned = re.sub(r'\s+', ' ', text).strip()
            fingerprint = cleaned[:2000] if cleaned else filename
        except Exception:
            fingerprint = filename

        if not fingerprint or len(fingerprint) < 10:
            return False, "", 0.0

        # 2. 向量化
        query_vector = await VectorService.embed_text(fingerprint)
        if query_vector is None:
            logger.warning("重复检测跳过：向量化服务不可用")
            return False, "", 0.0

        # 3. Qdrant 搜索（仅搜索已审核通过的文档向量）
        search_results = await VectorService.search_vectors(
            query_vector,
            {"must": [{"key": "is_reviewed", "match": {"value": True}}]},
            top_k=5,
        )
        if not search_results:
            return False, "", 0.0

        # 4. 计算余弦相似度（Qdrant 的 score 即为余弦相似度，范围 0~1）
        if threshold is None:
            from app.config import settings
            threshold = settings.DEDUP_SIMILARITY_THRESHOLD

        best = search_results[0]
        max_score = best.get("score", 0)
        payload = best.get("payload", {})
        doc_name = payload.get("document_name", "")

        if max_score >= threshold:
            logger.info(
                f"文档重复检测命中: {filename} -> {doc_name} (相似度: {max_score:.4f}, 阈值: {threshold})"
            )
            return True, doc_name or "未知文档", round(max_score, 4)

        return False, "", 0.0

    @staticmethod
    async def delete_vectors(document_id: int) -> None:
        """删除指定文档的所有向量（旧方法名，保留向后兼容）"""
        await VectorService.delete_document_vectors(document_id)

    @staticmethod
    async def delete_document_vectors(document_id: int) -> None:
        """删除指定文档的所有向量"""
        client = get_shared_client()
        url = f"{settings.QDRANT_URL}/collections/{VectorService.COLLECTION_NAME}/points/delete"
        await client.post(
            url,
            json={
                "filter": {
                    "must": [
                        {"key": "document_id", "match": {"value": document_id}}
                    ]
                }
            },
            timeout=15.0,
        )

    @staticmethod
    async def clear_all_vectors() -> None:
        """清空整个 collection 的所有向量点（用于全量重建前的清理）"""
        client = get_shared_client()
        url = f"{settings.QDRANT_URL}/collections/{VectorService.COLLECTION_NAME}/points/delete"
        # Qdrant 空 filter = 匹配所有点
        await client.post(
            url,
            json={"filter": {}},
            timeout=30.0,
        )

    @staticmethod
    async def get_collection_status() -> dict:
        """获取 collection 基本信息（点数、状态等），失败返回空字典"""
        try:
            client = get_shared_client()
            resp = await client.get(
                f"{settings.QDRANT_URL}/collections/{VectorService.COLLECTION_NAME}",
                timeout=10.0,
            )
            if resp.status_code == 200:
                return resp.json().get("result", {})
        except Exception as e:
            logger.warning(f"获取 Qdrant 状态失败: {e}")
        return {}

    @staticmethod
    async def update_document_payload(
        document_id: int,
        vector_ids: List[str] = None,
        model_tag: List[str] = None,
        region_tag: List[str] = None,
        doc_type_tag: List[str] = None,
        tags: List[str] = None,
        tags_by_category: dict = None,
    ) -> None:
        """更新指定文档的所有向量点的标签 payload"""
        client = get_shared_client()
        url = f"{settings.QDRANT_URL}/collections/{VectorService.COLLECTION_NAME}/points/payload"
        payload_updates = {}
        
        # 兼容旧参数
        if model_tag is not None:
            payload_updates["model_tag"] = model_tag
        if region_tag is not None:
            payload_updates["region_tag"] = region_tag
        if doc_type_tag is not None:
            payload_updates["doc_type_tag"] = doc_type_tag
            
        # 新动态标签
        if tags is not None:
            payload_updates["tags"] = tags
        if tags_by_category is not None:
            for cat_code, tag_list in tags_by_category.items():
                payload_updates[f"tag_{cat_code}"] = tag_list

        # 可以通过 vector_ids 批量更新，或者通过 document_id filter 更新
        # 使用 document_id filter 更新更高效（不需要知道所有 vector_ids）
        await client.post(
            url,
            json={
                "payload": payload_updates,
                "filter": {
                    "must": [
                        {"key": "document_id", "match": {"value": document_id}}
                    ]
                },
            },
            timeout=15.0,
        )
