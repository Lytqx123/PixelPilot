# 检索服务：向量+关键词双路检索，RRF融合排序

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from sqlalchemy import select, func, or_ as sa_or
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.document import Document, DocumentChunk

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """统一的检索结果格式"""
    document_id: int
    chunk_id: int
    content: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseRetriever(ABC):
    """检索器抽象基类"""

    @abstractmethod
    async def search(
        self,
        query: str,
        query_vector: Optional[List[float]],
        top_k: int,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        执行检索
        :param query: 原始查询文本
        :param query_vector: 查询向量（可选）
        :param top_k: 返回数量
        :param filters: 过滤条件
        :return: 检索结果列表
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """检索器名称"""
        pass


class VectorRetriever(BaseRetriever):
    """向量语义检索器"""

    def __init__(self):
        from app.services.vector_service import VectorService
        self._vector_svc = VectorService

    @property
    def name(self) -> str:
        return "vector"

    async def search(
        self,
        query: str,
        query_vector: Optional[List[float]],
        top_k: int,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if query_vector is None:
            return []

        results = await self._vector_svc.search_vectors(
            query_vector,
            filters or {},
            top_k=top_k,
        )
        return results


class KeywordRetriever(BaseRetriever):
    """关键词全文检索器"""

    def __init__(self, db: AsyncSession):
        self._db = db

    @property
    def name(self) -> str:
        return "keyword"

    async def search(
        self,
        query: str,
        query_vector: Optional[List[float]],
        top_k: int,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """在 document 名称和 chunk 内容中搜索关键词"""
        filters = filters or {}

        # 构建过滤条件
        # 注意:Document 模型只有 status 字段(0=待审核,1=已通过,2=已拒绝),
        # Qdrant payload 中的 is_reviewed 字段对应数据库中的 status==1
        has_should = bool(filters.get("should"))
        filter_clauses = []
        if filters.get("must"):
            for cond in filters["must"]:
                if cond.get("key") == "is_reviewed":
                    # 仅检索已审核通过的文档(status=1)
                    filter_clauses.append(Document.status == 1)
                elif cond.get("key") == "department_id":
                    # 如果存在 should(OR) 条件，department_id 由 should 处理，此处跳过
                    if has_should:
                        continue
                    if cond.get("is_empty"):
                        filter_clauses.append(Document.department_id.is_(None))
                    elif "match" in cond:
                        filter_clauses.append(Document.department_id == cond["match"]["value"])

        # 处理 should(OR) 条件：本部门文档 OR 全员可见文档
        if has_should:
            should_clauses = []
            for cond in filters["should"]:
                if cond.get("key") == "department_id":
                    if cond.get("is_empty"):
                        should_clauses.append(Document.department_id.is_(None))
                    elif "match" in cond:
                        should_clauses.append(Document.department_id == cond["match"]["value"])
                elif cond.get("key") == "is_public_to_all":
                    should_clauses.append(Document.is_public_to_all == cond["match"]["value"])
            if should_clauses:
                filter_clauses.append(sa_or(*should_clauses))

        # 构建关键词搜索条件
        search_pattern = f"%{query}%"
        keyword_conditions = [
            Document.name.ilike(search_pattern),
        ]

        try:
            stmt = (
                select(Document.id, Document.name, Document.department_id)
                .where(*filter_clauses)
                .where(sa_or(*keyword_conditions))
                .limit(top_k)
            )
            result = await self._db.execute(stmt)
            rows = result.all()

            results = []
            for doc_id, doc_name, dept_id in rows:
                results.append({
                    "id": f"doc_{doc_id}",
                    "score": 1.0,
                    "payload": {
                        "document_id": doc_id,
                        "content": doc_name,
                        "department_id": dept_id,
                    },
                })

            # 搜索 chunk 内容
            chunk_stmt = (
                select(DocumentChunk.id, DocumentChunk.document_id, DocumentChunk.content, DocumentChunk.page_number)
                .join(Document, DocumentChunk.document_id == Document.id)
                .where(*filter_clauses)
                .where(DocumentChunk.content.ilike(search_pattern))
                .limit(top_k)
            )
            chunk_result = await self._db.execute(chunk_stmt)
            chunk_rows = chunk_result.all()

            for chunk_id, doc_id, content, page_num in chunk_rows:
                results.append({
                    "id": f"chunk_{chunk_id}",
                    "score": 0.8,
                    "payload": {
                        "document_id": doc_id,
                        "content": content[:500] if content else "",
                        "page_number": page_num,
                    },
                })

            return results

        except Exception as e:
            logger.warning(f"关键词检索失败: {e}")
            return []


class RetrievalService:
    """
    检索服务：统一接口，支持多检索器融合

    使用策略模式：
    - 可配置启用哪些检索器（向量、关键词）
    - 使用 RRF 算法融合多个检索器结果
    """

    RRF_K = 60  # RRF 融合参数

    def __init__(self, db: AsyncSession):
        self._db = db
        self._retrievers: List[BaseRetriever] = []
        self._init_retrievers(db)

    def _init_retrievers(self, db: AsyncSession):
        """初始化检索器列表"""
        self._retrievers = [
            VectorRetriever(),
            KeywordRetriever(db),
        ]

    def set_retrievers(self, retrievers: List[BaseRetriever]):
        """设置要使用的检索器列表"""
        self._retrievers = retrievers

    async def search(
        self,
        query: str,
        query_vector: Optional[List[float]],
        top_k: int,
        filters: Optional[Dict[str, Any]] = None,
        weights: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        """
        执行融合检索

        :param query: 查询文本
        :param query_vector: 查询向量
        :param top_k: 返回数量
        :param filters: 过滤条件
        :param weights: 各检索器权重，默认为 {"vector": 1.0, "keyword": 1.5}
        :return: 融合排序后的检索结果
        """
        if weights is None:
            weights = {"vector": 1.0, "keyword": 1.5}

        # 并行执行所有检索器
        import asyncio
        tasks = [
            retriever.search(query, query_vector, top_k * 4, filters)
            for retriever in self._retrievers
        ]
        results_by_retriever = await asyncio.gather(*tasks, return_exceptions=True)

        # 收集有效结果
        merged_scores: Dict[int, Dict[str, float]] = {}
        vector_hit_by_doc: Dict[int, dict] = {}

        for retriever, results in zip(self._retrievers, results_by_retriever):
            if isinstance(results, Exception):
                logger.warning(f"检索器 {retriever.name} 执行失败: {results}")
                continue

            weight = weights.get(retriever.name, 1.0)
            for rank, hit in enumerate(results):
                doc_id = hit.get("payload", {}).get("document_id", 0)
                if not doc_id:
                    continue

                # 计算 RRF 分数
                base_rrf = 1.0 / (rank + self.RRF_K)
                retriever_score = hit.get("score", 0)

                if doc_id not in merged_scores:
                    merged_scores[doc_id] = {}

                # 累加加权后的 RRF 分数
                merged_scores[doc_id][retriever.name] = base_rrf * weight + retriever_score * 0.3 * weight

                # 保存最佳 hit 用于后续构建结果
                if doc_id not in vector_hit_by_doc:
                    vector_hit_by_doc[doc_id] = hit

        # 按总分排序
        sorted_doc_ids = sorted(
            merged_scores.keys(),
            key=lambda d: sum(merged_scores[d].values()),
            reverse=True,
        )[:top_k]

        # 构建最终结果
        search_results = []
        for doc_id in sorted_doc_ids:
            hit = vector_hit_by_doc.get(doc_id)
            if hit:
                new_hit = dict(hit)
                new_hit["score"] = sum(merged_scores[doc_id].values())
                new_hit["contribution"] = merged_scores[doc_id]
                search_results.append(new_hit)

        return search_results

    async def keyword_search_only(
        self,
        keywords: List[str],
        top_k: int,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """仅使用关键词检索（用于元数据问题）"""
        keyword_retriever = KeywordRetriever(self._db)

        combined_results = []
        for keyword in keywords:
            results = await keyword_retriever.search(
                keyword, None, top_k, filters
            )
            combined_results.extend(results)

        # 按分数排序去重
        seen = set()
        unique_results = []
        for r in combined_results:
            doc_id = r.get("payload", {}).get("document_id", 0)
            if doc_id and doc_id not in seen:
                seen.add(doc_id)
                unique_results.append(r)

        unique_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return unique_results[:top_k]