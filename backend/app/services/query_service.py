# 问答服务：处理检索、重排、LLM调用，支持流式输出

import logging
from typing import List, Optional, Tuple, AsyncGenerator

import httpx
from sqlalchemy import select, and_, or_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.permissions import (
    get_user_data_scopes,
    is_privileged_role,
    resolve_document_access,
)
from app.models.user import User
from app.models.document import Document, DocumentChunk
from app.models.user_favorite import UserFavorite
from app.schemas.query import QueryRequest, QAResponse, SourceInfo
from app.services.audit_service import AuditService
from app.services.vector_service import VectorService
from app.services.filters import VectorQueryFilterBuilder
from app.services.keyword_extractor import KeywordExtractor, IDENTITY_ANSWER, METADATA_KEYWORDS
from app.services.retrieval_service import RetrievalService
from app.services.reranker_service import RerankerService

logger = logging.getLogger(__name__)


class QueryService:
    """问答服务：协调检索和生成"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit_svc = AuditService(db)
        self.retrieval = RetrievalService(db)
        self.reranker = RerankerService()

    async def query_knowledge(
        self,
        user: User,
        question: str,
        top_k: int = 5,
        use_large_model: bool = False,
        conversation_id: Optional[int] = None,
    ) -> QAResponse:
        """非流式问答入口"""
        try:
            user_scopes = await get_user_data_scopes(self.db, user.id)
            is_privileged = bool(user.role and is_privileged_role(user.role.role_code))
            is_super_admin = bool(user.role and user.role.role_code == "SUPER_ADMIN")

            # 获取对话历史（多轮记忆）
            conversation_history = ""
            if conversation_id:
                conversation_history = await self._fetch_conversation_history(
                    conversation_id, user.id
                )

            # 1. 处理特殊问题类型
            answer = self._handle_special_question(question)
            if answer:
                return QAResponse(answer=answer, sources=[])

            # 2. 元数据问题
            answer = await self._handle_metadata_question(user, user_scopes, question, is_super_admin)
            if answer:
                return QAResponse(answer=answer, sources=[])

            # 3. 构建检索过滤
            filters = VectorQueryFilterBuilder.build(user)

            # 4. 向量化
            query_vector = await VectorService.embed_text(question)
            if query_vector is None and not KeywordExtractor.extract_keywords(question):
                fallback = await self._get_fallback_answer(user, user_scopes, is_super_admin)
                return QAResponse(answer=fallback, sources=[])

            # 5. 混合检索 + Reranker
            keywords = KeywordExtractor.extract_keywords(question)
            search_results = await self.retrieval.search(
                question, query_vector, top_k * 4, filters
            )

            # 6. 构建来源和上下文
            sources, context_chunks = await self._build_sources_and_context(
                user, user_scopes, search_results, question, keywords
            )

            # 7. 调用 LLM 生成
            answer = await self._call_llm(
                question, context_chunks, user_scopes, is_privileged, use_large_model, conversation_history
            )

            # 8. 审计日志
            await self.audit_svc.create_audit_log(
                user_id=user.id,
                operation_type="QUERY",
                operation_content={
                    "question": question[:200],
                    "result_count": len(sources),
                    "keywords": keywords[:5],
                },
            )

            return QAResponse(answer=answer, sources=sources)

        except Exception as e:
            logger.error(f"问答流程异常: {e}")
            return QAResponse(answer="抱歉，系统处理您的问题时出现了错误，请稍后重试。", sources=[])

    async def query_knowledge_stream(
        self,
        user: User,
        question: str,
        top_k: int = 5,
        use_large_model: bool = False,
        conversation_id: Optional[int] = None,
    ) -> Tuple[List[SourceInfo], AsyncGenerator]:
        """流式问答入口"""
        user_scopes = await get_user_data_scopes(self.db, user.id)
        is_privileged = bool(user.role and is_privileged_role(user.role.role_code))
        is_super_admin = bool(user.role and user.role.role_code == "SUPER_ADMIN")

        # 获取对话历史（多轮记忆）
        conversation_history = ""
        if conversation_id:
            conversation_history = await self._fetch_conversation_history(
                conversation_id, user.id
            )

        # 1. 处理特殊问题
        answer = self._handle_special_question(question)
        if answer:
            async def gen():
                yield answer
            return [], gen()

        # 2. 元数据问题
        answer = await self._handle_metadata_question(user, user_scopes, question, is_super_admin)
        if answer:
            async def gen():
                yield answer
            return [], gen()

        # 3. 检索流程
        filters = VectorQueryFilterBuilder.build(user)
        query_vector = await VectorService.embed_text(question)
        keywords = KeywordExtractor.extract_keywords(question)

        # 向量化失败且无有效关键词 → 返回友好兜底（与非流式一致）
        if query_vector is None and not keywords:
            fallback = await self._get_fallback_answer(user, user_scopes, is_super_admin)

            async def gen_fallback():
                yield fallback
            return [], gen_fallback()

        search_results = await self.retrieval.search(
            question, query_vector, top_k * 4, filters
        )

        sources, context_chunks = await self._build_sources_and_context(
            user, user_scopes, search_results, question, keywords
        )

        await self.audit_svc.create_audit_log(
            user_id=user.id,
            operation_type="QUERY_STREAM",
            operation_content={"question": question[:200], "result_count": len(sources)},
        )

        async def answer_gen():
            async for chunk in self._call_llm_stream(
                question, context_chunks, user_scopes, is_privileged, use_large_model, conversation_history
            ):
                yield chunk

        return sources, answer_gen()

    def _handle_special_question(self, question: str) -> Optional[str]:
        """处理身份类问题"""
        if KeywordExtractor.is_identity_question(question):
            return IDENTITY_ANSWER
        return None

    async def _handle_metadata_question(
        self,
        user: User,
        user_scopes: List[dict],
        question: str,
        is_super_admin: bool,
    ) -> Optional[str]:
        """处理元数据/统计类问题"""
        if not any(kw in question.lower() for kw in METADATA_KEYWORDS):
            return None

        stats = await self._get_document_stats(user, user_scopes, is_super_admin)
        return self._format_knowledge_overview(stats)

    async def _build_sources_and_context(
        self,
        user: User,
        user_scopes: List[dict],
        search_results: List[dict],
        question: str,
        keywords: List[str],
    ) -> Tuple[List[SourceInfo], List[str]]:
        """构建来源文档列表和上下文"""
        if not search_results:
            return [], []

        # Reranker 精排
        candidates = [
            {
                "document_id": hit.get("payload", {}).get("document_id", 0),
                "vector_id": hit.get("vector_id", ""),
                "score": hit.get("score", 0),
                "content": hit.get("payload", {}).get("content", ""),
                "payload": hit.get("payload", {}),
            }
            for hit in search_results
        ]
        candidates = [c for c in candidates if c["document_id"] and c["content"].strip()]

        if len(candidates) > settings.RERANKER_TOP_K:
            candidates = await self.reranker.rerank_with_fallback(question, candidates)

        # 批量获取文档信息
        doc_ids = list(set(c["document_id"] for c in candidates))
        docs_result = await self.db.execute(select(Document).where(Document.id.in_(doc_ids)))
        docs_by_id = {d.id: d for d in docs_result.scalars().all()}

        chunks_result = await self.db.execute(
            select(DocumentChunk).where(
                DocumentChunk.vector_id.in_(c["vector_id"] for c in candidates if c["vector_id"])
            )
        )
        chunks_by_vid = {c.vector_id: c for c in chunks_result.scalars().all()}

        fav_result = await self.db.execute(
            select(UserFavorite.document_id).where(UserFavorite.user_id == user.id)
        )
        fav_doc_ids = {row[0] for row in fav_result.all()}

        # 批量查询 pending 申请状态
        from app.models.access_application import AccessApplication
        from app.core.constants import APPLICATION_STATUS_PENDING

        pending_result = await self.db.execute(
            select(AccessApplication.document_id).where(
                AccessApplication.applicant_id == user.id,
                AccessApplication.status == APPLICATION_STATUS_PENDING,
                AccessApplication.document_id.in_(doc_ids),
            )
        )
        pending_doc_ids = {row[0] for row in pending_result.all()}

        sources = []
        context_chunks = []

        for rank, cand in enumerate(candidates[:settings.RERANKER_TOP_K + 2]):
            doc = docs_by_id.get(cand["document_id"])
            if not doc:
                continue

            # 权限统一入口：由 resolve_document_access 统一处理（含手动授权、临时令牌等）
            doc_is_public = bool(getattr(doc, "is_public_to_all", 0))
            user_role = user.role.role_code if user.role else ""

            perm = await resolve_document_access(
                self.db, user.id, user_role, user.department_id,
                doc.uploader_id == user.id, doc.department_id,
                doc.access_mode, doc.id, is_public_to_all=doc_is_public,
            )

            chunk = chunks_by_vid.get(cand["vector_id"])
            content = chunk.content if chunk else cand["content"]

            # 关键词高亮
            snippet = self._extract_snippet(content, keywords)

            import os
            file_ext = os.path.splitext(doc.name.lower())[1] if doc.name else ""
            file_format = file_ext.lstrip(".") if file_ext else "-"

            source = SourceInfo(
                document_id=doc.id,
                document_name=doc.name,
                format=file_format,
                page_number=chunk.page_number if chunk else None,
                paragraph=chunk.paragraph if chunk else None,
                content_snippet=snippet,
                highlighted_snippet=snippet,
                access_type=perm["access_type"],
                score=round(cand["score"], 4),
                can_download=perm["can_download"],
                can_view=perm["can_view"],
                is_favorited=doc.id in fav_doc_ids,
                permission_expires_at=perm.get("permission_expires_at"),
                has_pending_application=doc.id in pending_doc_ids,
            )
            sources.append(source)
            context_chunks.append(f"[来源{rank + 1}]《{doc.name}》 {content}")

        return sources, context_chunks

    def _extract_snippet(self, content: str, keywords: List[str], max_len: int = 200) -> str:
        """提取包含关键词的内容片段"""
        import html
        if not keywords or not content:
            return html.escape(content[:max_len])

        content_lower = content.lower()
        best_pos = -1
        for kw in keywords:
            pos = content_lower.find(kw.lower())
            if pos >= 0:
                best_pos = pos
                break

        if best_pos < 0:
            return html.escape(content[:max_len])

        start = max(0, best_pos - 30)
        end = min(len(content), start + max_len)
        snippet = content[start:end]
        return html.escape(snippet)

    async def _call_llm(
        self,
        question: str,
        context_chunks: List[str],
        user_scopes: List[dict],
        is_privileged: bool,
        use_large_model: bool,
        conversation_history: str = "",
    ) -> str:
        """调用 LLM 生成回答（非流式）"""
        prompt, no_context_answer = self._build_prompt(
            question, context_chunks, user_scopes, is_privileged, conversation_history
        )
        if not prompt:
            return no_context_answer

        try:
            model_name, api_url, options = self._select_llm_model(use_large_model)
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    api_url,
                    json={"model": model_name, "prompt": prompt, "stream": False, "options": options},
                    timeout=180.0,
                )
                response.raise_for_status()
                answer = response.json().get("response", "")
                if answer:
                    return answer
        except Exception as e:
            logger.warning(f"LLM 调用失败: {e}")

        return no_context_answer

    async def _call_llm_stream(
        self,
        question: str,
        context_chunks: List[str],
        user_scopes: List[dict],
        is_privileged: bool,
        use_large_model: bool,
        conversation_history: str = "",
    ) -> AsyncGenerator[str, None]:
        """调用 LLM 生成回答（流式）"""
        prompt, no_context_answer = self._build_prompt(
            question, context_chunks, user_scopes, is_privileged, conversation_history
        )
        if not prompt:
            yield no_context_answer
            return

        try:
            model_name, api_url, options = self._select_llm_model(use_large_model)
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST", api_url,
                    json={"model": model_name, "prompt": prompt, "stream": True, "options": options},
                    timeout=180.0,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            import json as _json
                            data = _json.loads(line)
                            if data.get("done", False):
                                break
                            chunk = data.get("response", "")
                            if chunk:
                                yield chunk
                        except _json.JSONDecodeError:
                            pass
        except Exception as e:
            logger.warning(f"LLM 流式调用失败: {e}")
            yield "抱歉，AI 模型暂时不可用，请稍后重试或联系管理员检查 Ollama 服务状态。"

    async def _fetch_conversation_history(
        self,
        conversation_id: int,
        user_id: int,
        max_rounds: int = 5,
    ) -> str:
        """
        获取指定会话的最近 N 轮对话历史，格式化为 Prompt 片段。

        :param conversation_id: 会话ID
        :param user_id: 用户ID（用于权限校验）
        :param max_rounds: 最多取最近 N 轮对话
        :return: 格式化的历史文本，无历史时返回空字符串
        """
        from app.models.conversation import Conversation as _Conv, ConversationMessage as _Msg
        from sqlalchemy import desc

        conv_result = await self.db.execute(
            select(_Conv).where(_Conv.id == conversation_id, _Conv.user_id == user_id)
        )
        conv = conv_result.scalar_one_or_none()
        if not conv:
            return ""

        msg_result = await self.db.execute(
            select(_Msg)
            .where(_Msg.conversation_id == conversation_id)
            .order_by(desc(_Msg.created_at))
            .limit(max_rounds * 2)  # N 轮 = 2N 条消息
        )
        messages = list(msg_result.scalars().all())

        if not messages:
            return ""

        # 按时间正序排列（从旧到新）
        messages.reverse()

        history_lines = []
        for m in messages:
            history_lines.append(f"用户：{m.question}")
            if m.answer:
                # 截断过长的历史回答，避免超出上下文窗口
                answer_preview = m.answer[:300] + ("..." if len(m.answer) > 300 else "")
                history_lines.append(f"AI助手：{answer_preview}")

        return "\n".join(history_lines)

    def _build_prompt(
        self,
        question: str,
        context_chunks: List[str],
        user_scopes: List[dict],
        is_privileged: bool,
        conversation_history: str = "",
    ) -> Tuple[str, str]:
        """构建 Prompt（含多轮对话历史）"""
        if not context_chunks:
            return "", (
                "抱歉，在您的权限范围内未找到与问题直接相关的文档信息。\n"
                "建议：\n1. 尝试使用不同关键词重新提问\n2. 上传相关文档来扩展知识库"
            )

        context = "\n\n".join(context_chunks)

        # 拼接对话历史（如有）
        history_section = ""
        if conversation_history:
            history_section = f"对话历史（请结合上下文理解用户意图）：\n{conversation_history}\n\n"

        prompt = (
            "你是PixelPulse AI智能助手小妤，负责基于企业知识库为用户提供专业的技术支持与知识服务。\n"
            "请根据以下参考资料回答用户的问题。\n"
            "如果参考资料中没有相关信息，请明确告知用户。\n"
            "回答时请准确引用参考资料的内容和数据，回答开头可以使用'我是小妤'或亲切自称。\n\n"
            f"{history_section}"
            f"参考资料：\n{context}\n\n"
            f"用户问题：{question}\n\n"
            "请用中文回答："
        )
        return prompt, ""

    def _select_llm_model(self, use_large_model: bool) -> Tuple[str, str, dict]:
        """选择 LLM 模型"""
        if use_large_model and settings.LLM_LARGE_ENABLED:
            return settings.LLM_LARGE_MODEL, settings.LLM_LARGE_API_URL, {
                "temperature": settings.LLM_LARGE_TEMPERATURE, "num_ctx": settings.LLM_NUM_CTX
            }
        return settings.LLM_MODEL, settings.LLM_API_URL, {"temperature": 0.7, "num_ctx": settings.LLM_NUM_CTX}

    async def _get_document_stats(
        self,
        user: User,
        user_scopes: List[dict],
        is_super_admin: bool,
    ) -> dict:
        """获取文档统计"""
        stats = {"total_count": 0, "doc_types": {}, "model_tags": {}, "region_tags": {}, "document_names": []}
        conditions = [Document.status == 1]

        if not is_super_admin:
            # 非超级管理员：本部门文档 OR 全员可见文档（超级管理员上传）
            access_conds = []
            if user.department_id is not None:
                access_conds.append(Document.department_id == user.department_id)
            else:
                access_conds.append(Document.uploader_id == user.id)
            access_conds.append(Document.is_public_to_all == 1)
            conditions.append(or_(*access_conds))

        base_cond = and_(*conditions) if len(conditions) > 1 else conditions[0]
        result = await self.db.execute(select(Document).where(base_cond).order_by(Document.created_at.desc()))
        documents = result.scalars().all()
        stats["total_count"] = len(documents)

        for doc in documents:
            stats["document_names"].append(doc.name)
            for tag_type, field in [("doc_types", doc.doc_type_tag), ("model_tags", doc.model_tag), ("region_tags", doc.region_tag)]:
                if field:
                    for tag in [t.strip() for t in field.split(",") if t.strip()]:
                        stats[tag_type][tag] = stats[tag_type].get(tag, 0) + 1
        return stats

    async def _get_fallback_answer(
        self,
        user: User,
        user_scopes: List[dict],
        is_super_admin: bool,
    ) -> str:
        """向量化失败时的兜底回答"""
        stats = await self._get_document_stats(user, user_scopes, is_super_admin)
        overview = self._format_knowledge_overview(stats)
        return (
            "抱歉，向量化服务当前不可用，无法进行语义检索。\n\n"
            f"{overview}\n\n"
            "请检查 Ollama Embedding 服务是否正常运行，然后重试。"
        )

    def _format_knowledge_overview(self, stats: dict) -> str:
        """格式化知识库概况"""
        lines = ["📚 **知识库概况**\n", f"- 文档总数：{stats['total_count']} 个\n"]

        if stats["doc_types"]:
            lines.append("- 按文档类型：")
            for tag, count in sorted(stats["doc_types"].items(), key=lambda x: -x[1]):
                emoji = {"ENGINEERING_DRAWING": "🔧", "TEST_REPORT": "📊", "BUG_REPORT": "🐛", "REGULATION": "📜"}.get(tag, "📄")
                lines.append(f"  {emoji} {tag}：{count} 个")

        if stats["model_tags"]:
            lines.append("- 按车型：")
            for tag, count in sorted(stats["model_tags"].items(), key=lambda x: -x[1]):
                lines.append(f"  🏎️ {tag}：{count} 个")

        if stats["document_names"] and len(stats["document_names"]) <= 20:
            lines.append("\n**文档列表：**")
            for i, name in enumerate(stats["document_names"], 1):
                lines.append(f"  {i}. {name}")

        if stats["total_count"] == 0:
            lines.append("\n⚠️ 知识库当前为空，您可以上传文档来构建知识库。")

        return "\n".join(lines)
