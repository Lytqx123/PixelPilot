import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import datetime

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models.user import User
from app.schemas.document import ExportRequest
from app.services.export_service import ExportService
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data", tags=["数据导出"])


@router.post("/export")
async def export_data(
    request: ExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """导出问答数据：PDF/CSV"""
    export_svc = ExportService(db)
    audit_svc = AuditService(db)

    try:
        data = await export_svc.export_qa_results(
            current_user, request.query, request.document_ids, request.format
        )
    except Exception as e:
        logger.error(f"导出失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"导出失败：{str(e)}", "code": 500},
        )

    if not data or len(data) == 0:
        return JSONResponse(
            status_code=400,
            content={"detail": "导出内容为空，请确认对话内容后重试", "code": 400},
        )

    try:
        await audit_svc.create_audit_log(
            user_id=current_user.id,
            operation_type="EXPORT",
            operation_content={
                "query": (request.query or "")[:200],
                "document_ids": request.document_ids,
                "format": request.format,
            },
        )
    except Exception as e:
        logger.warning(f"审计日志记录失败（非致命）: {e}")

    user_id_str = str(current_user.id)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    ext = "pdf" if request.format != "csv" else "csv"
    media_type = "application/pdf" if request.format != "csv" else "text/csv"
    filename = f"{user_id_str}_{timestamp}.{ext}"

    return StreamingResponse(
        content=iter([data]),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )