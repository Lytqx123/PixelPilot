# Reranker重排服务：Qwen3做精排，可配置开关

import asyncio
import logging
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

import httpx

from app.core.http_client import get_shared_client

from app.config import settings

logger = logging.getLogger(__name__)


class BaseReranker(ABC):
    """Reranker 抽象基类"""

    @abstractmethod
    async def rerank(
        self,
        question: str,
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        对候选文档进行重排序
        :param question: 用户问题
        :param candidates: 候选列表，每项需包含 "content" 字段
        :return: 按相关性分数降序排列的列表
        """
        pass


class QwenReranker(BaseReranker):
    """
    Qwen3-Reranker 实现

    工作原理:
        1. 粗检索获取 top-N 候选 chunk
        2. 将每个 (question, chunk_text) 对送入 Reranker 模型打分
        3. 按 Reranker 分数重新排序，取 top-K 送入 LLM 生成
    """

    MAX_CHUNK_CHARS = 800
    BATCH_SIZE = 8

    async def rerank(
        self,
        question: str,
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not settings.RERANKER_ENABLED:
            return candidates
        if not candidates:
            return []
        if len(candidates) <= settings.RERANKER_TOP_K:
            return candidates

        # 过滤无效候选
        valid = [c for c in candidates if c.get("content") and str(c["content"]).strip()]
        if not valid:
            return candidates

        prefetch = min(len(valid), settings.RERANKER_PREFETCH)
        subset = valid[:prefetch]

        scored = await self._score_candidates(question, subset)
        scored.sort(key=lambda x: (x.get("reranker_score", 0.0), x.get("score", 0.0)), reverse=True)

        # 追加未参与评分的候选
        remaining = [c for c in candidates if c not in subset]
        return scored + remaining

    async def _score_candidates(
        self,
        question: str,
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """批量并发调用 Reranker 打分，避免串行请求导致的性能瓶颈"""
        client = get_shared_client()

        async def score_one(cand: Dict[str, Any]) -> Dict[str, Any]:
            content = str(cand["content"])[: self.MAX_CHUNK_CHARS]
            score = await self._call_reranker(client, question, content)
            item = dict(cand)
            item["reranker_score"] = score if score is not None else item.get("score", 0.5)
            return item

        # 按 BATCH_SIZE 分组并发执行，控制并发度避免压垮模型服务
        scored: List[Dict[str, Any]] = []
        for i in range(0, len(candidates), self.BATCH_SIZE):
            batch = candidates[i : i + self.BATCH_SIZE]
            batch_results = await asyncio.gather(
                *(score_one(c) for c in batch), return_exceptions=True
            )
            for res in batch_results:
                if isinstance(res, Exception):
                    logger.warning(f"Reranker 批量评分中某项失败: {res}")
                    continue
                scored.append(res)

        return scored

    async def _call_reranker(
        self,
        client: httpx.AsyncClient,
        question: str,
        content: str,
    ) -> Optional[float]:
        """调用 Ollama Reranker API"""
        prompt = (
            "你是一个文档相关性评估专家。请判断下面的文档片段是否与用户问题相关。\n"
            f"用户问题: {question}\n"
            f"文档片段:\n{content}\n"
            "请只输出一个 0 到 1 之间的小数，表示相关性分数（1 表示完全相关，0 表示完全不相关）。\n"
            "输出格式：只输出数字，不要输出任何其他文字、解释或标点。"
        )

        try:
            response = await client.post(
                settings.RERANKER_API_URL,
                json={
                    "model": settings.RERANKER_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.0, "num_ctx": 2048},
                },
            )
            response.raise_for_status()
            raw = response.json().get("response", "").strip()
            return self._parse_score(raw)
        except Exception as e:
            logger.warning(f"Reranker 调用失败: {e}")
            return None

    @staticmethod
    def _parse_score(text: str) -> Optional[float]:
        """从模型输出中解析 0~1 之间的数字"""
        if not text:
            return None

        matches = re.findall(r"\b(0(?:\.\d+)?|1(?:\.0+)?|\.\d+)\b", text)
        if matches:
            try:
                val = float(matches[0])
                if 0.0 <= val <= 1.0:
                    return val
            except (ValueError, TypeError):
                pass

        # 兜底：基于关键词判断
        lower = text.lower()
        if any(k in lower for k in ["是", "相关", "yes", "relevant", "true"]):
            return 0.9
        if any(k in lower for k in ["否", "不相关", "no", "irrelevant", "false"]):
            return 0.1
        return None


class RerankerService:
    """
    Reranker 服务门面

    支持禁用、启用、可插拔不同 Reranker 实现
    """

    def __init__(self):
        self._reranker: BaseReranker = QwenReranker()

    def set_reranker(self, reranker: BaseReranker):
        """更换 Reranker 实现"""
        self._reranker = reranker

    async def rerank(
        self,
        question: str,
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """对候选列表进行重排序"""
        return await self._reranker.rerank(question, candidates)

    async def rerank_with_fallback(
        self,
        question: str,
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """带兜底的重排序：Reranker 失败时返回原列表"""
        try:
            return await self.rerank(question, candidates)
        except Exception as e:
            logger.warning(f"Reranker 服务异常，回退到原排序: {e}")
            return candidates