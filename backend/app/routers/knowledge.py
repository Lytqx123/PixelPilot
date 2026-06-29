import json
import logging
from typing import List, Any
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models.user import User
from app.models.conversation import Conversation, ConversationMessage
from app.schemas.query import QueryRequest, QAResponse
from app.services.query_service import QueryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge", tags=["智能问答"])


def _format_sources_for_sse(sources: List[Any]) -> List[dict]:
    """将来源对象列表转为 SSE 事件发送的 JSON 数据"""
    return [
        {
            "document_id": s.document_id,
            "document_name": s.document_name,
            "format": s.format,
            "page_number": s.page_number,
            "access_type": s.access_type,
            "score": round(s.score, 4),
            "can_download": s.can_download,
            "can_view": s.can_view,
            "is_favorited": s.is_favorited,
            "content_snippet": getattr(s, "content_snippet", ""),
            "highlighted_snippet": getattr(s, "highlighted_snippet", ""),
            "permission_expires_at": s.permission_expires_at.isoformat() if s.permission_expires_at else None,
            "has_pending_application": s.has_pending_application,
        }
        for s in sources
    ]


@router.post("/query/stream")
async def query_knowledge_stream(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """流式智能问答：逐字返回 AI 回答 → 来源文档 → 保存消息 → 发送 done"""
    svc = QueryService(db)
    try:
        sources, answer_gen = await svc.query_knowledge_stream(
            current_user, request.question, request.top_k, request.use_large_model, request.conversation_id
        )
    except Exception as e:
        logger.error(f"流式问答接口异常: {e}")
        async def _error_gen():
            yield f'event: error\ndata: {{"message": "系统处理您的问题时出现了错误，请稍后重试。"}}\n\n'
            yield 'event: done\ndata: {"status": "error"}\n\n'
        return StreamingResponse(_error_gen(), media_type="text/event-stream")

    sse_sources_json = json.dumps(_format_sources_for_sse(sources), ensure_ascii=False)
    saved_sources = [s.model_dump() for s in sources]
    conversation_id = request.conversation_id
    user_id = current_user.id
    question = request.question

    async def _stream_and_save():
        """生成 SSE 事件流：先逐字返回 AI 回答，再返回来源文档，保存消息后再发送 done"""
        full_answer = ""

        try:
            async for text_chunk in answer_gen:
                if text_chunk:
                    full_answer += text_chunk
                    encoded = json.dumps(text_chunk, ensure_ascii=False)
                    yield f"event: text\ndata: {encoded}\n\n"
        except Exception as e:
            logger.warning(f"流式回答生成异常: {e}")
            yield f'event: error\ndata: {{"message": "回答生成中断"}}\n\n'

        yield f"event: sources\ndata: {sse_sources_json}\n\n"

        # 先保存对话消息到数据库，再发送 done（避免客户端断开导致保存失败）
        if conversation_id and (full_answer or saved_sources):
            try:
                conv_result = await db.execute(
                    select(Conversation).where(
                        Conversation.id == conversation_id,
                        Conversation.user_id == user_id,
                    )
                )
                conv = conv_result.scalar_one_or_none()
                if conv:
                    msg = ConversationMessage(
                        conversation_id=conversation_id,
                        question=question,
                        answer=full_answer,
                        sources=saved_sources,
                    )
                    db.add(msg)
                    conv.title = conv.title if conv.title != "新对话" else question[:30]
                    await db.commit()
            except Exception as save_err:
                logger.warning(f"保存对话消息失败: {save_err}")

        yield 'event: done\ndata: {"status": "ok"}\n\n'

    return StreamingResponse(
        _stream_and_save(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/query", response_model=QAResponse)
async def query_knowledge(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """智能问答：权限过滤 → 向量检索 → LLM 生成 → 溯源"""
    svc = QueryService(db)
    try:
        result = await svc.query_knowledge(
            current_user, request.question, request.top_k, request.use_large_model, request.conversation_id
        )
        if request.conversation_id:
            conv_result = await db.execute(
                select(Conversation).where(
                    Conversation.id == request.conversation_id,
                    Conversation.user_id == current_user.id,
                )
            )
            conv = conv_result.scalar_one_or_none()
            if conv:
                msg = ConversationMessage(
                    conversation_id=conv.id,
                    question=request.question,
                    answer=result.answer,
                    sources=[s.model_dump() for s in result.sources],
                )
                db.add(msg)
                conv.title = conv.title if conv.title != "新对话" else request.question[:30]
                await db.commit()
        return result
    except Exception as e:
        logger.error(f"问答接口异常: {e}")
        return QAResponse(
            answer="抱歉，系统处理您的问题时出现了错误，请稍后重试。",
            sources=[],
        )


@router.get("/conversations")
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取当前用户所有对话会话"""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
    )
    convs = list(result.scalars().all())
    return {
        "items": [
            {
                "id": c.id,
                "title": c.title,
                "created_at": c.created_at.isoformat() if c.created_at else "",
                "updated_at": c.updated_at.isoformat() if c.updated_at else "",
            }
            for c in convs
        ]
    }


@router.post("/conversations")
async def create_conversation(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """创建新的对话会话"""
    conv = Conversation(user_id=current_user.id, title="新对话")
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return {
        "id": conv.id,
        "title": conv.title,
        "created_at": conv.created_at.isoformat() if conv.created_at else "",
    }


@router.get("/conversations/{conv_id}/messages")
async def get_conversation_messages(
    conv_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取指定会话的所有消息"""
    conv_result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.user_id == current_user.id,
        )
    )
    conv = conv_result.scalar_one_or_none()
    if not conv:
        return {"items": []}

    msg_result = await db.execute(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conv_id)
        .order_by(ConversationMessage.created_at.asc())
    )
    msgs = list(msg_result.scalars().all())
    return {
        "items": [
            {
                "id": m.id,
                "question": m.question,
                "answer": m.answer,
                "sources": m.sources or [],
                "created_at": m.created_at.isoformat() if m.created_at else "",
            }
            for m in msgs
        ]
    }


@router.delete("/conversations/{conv_id}")
async def delete_conversation(
    conv_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """删除对话会话及其所有消息"""
    conv_result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.user_id == current_user.id,
        )
    )
    conv = conv_result.scalar_one_or_none()
    if not conv:
        return {"detail": "会话不存在"}
    await db.delete(conv)
    await db.commit()
    return {"detail": "已删除"}