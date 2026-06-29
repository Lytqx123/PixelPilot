import csv
import io
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogQuery


class AuditService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_audit_log(
        self,
        user_id: int,
        operation_type: str,
        operation_content: Dict[str, Any] = None,
        ip_address: str = "",
    ) -> AuditLog:
        """创建审计日志记录"""
        audit_log = AuditLog(
            user_id=user_id,
            operation_type=operation_type,
            operation_content=operation_content or {},
            ip_address=ip_address,
        )
        self.db.add(audit_log)
        await self.db.flush()
        return audit_log

    async def get_audit_logs(self, query: AuditLogQuery) -> dict:
        """分页查询审计日志，关联用户信息，按 created_at 降序"""
        base_query = select(AuditLog)
        count_query = select(func.count(AuditLog.id))

        if query.user_id is not None:
            base_query = base_query.where(AuditLog.user_id == query.user_id)
            count_query = count_query.where(AuditLog.user_id == query.user_id)
        if query.operation_type is not None:
            base_query = base_query.where(AuditLog.operation_type == query.operation_type)
            count_query = count_query.where(AuditLog.operation_type == query.operation_type)
        if query.start_time is not None:
            base_query = base_query.where(AuditLog.created_at >= query.start_time)
            count_query = count_query.where(AuditLog.created_at >= query.start_time)
        if query.end_time is not None:
            base_query = base_query.where(AuditLog.created_at <= query.end_time)
            count_query = count_query.where(AuditLog.created_at <= query.end_time)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (query.page - 1) * query.page_size
        result = await self.db.execute(
            base_query.order_by(AuditLog.created_at.desc()).offset(offset).limit(query.page_size)
        )
        logs: List[AuditLog] = list(result.scalars().all())

        items = []
        for log in logs:
            items.append({
                "id": log.id,
                "user_id": log.user_id,
                "username": log.user.username if log.user else "",
                "real_name": log.user.real_name if log.user else "",
                "operation_type": log.operation_type,
                "operation_content": log.operation_content,
                "ip_address": log.ip_address,
                "created_at": log.created_at,
            })

        return {"total": total, "items": items}

    async def export_audit_logs_csv(self, query: AuditLogQuery) -> bytes:
        """导出审计日志为 CSV 格式（不分页，返回全部筛选结果）"""
        base_query = select(AuditLog)

        if query.user_id is not None:
            base_query = base_query.where(AuditLog.user_id == query.user_id)
        if query.operation_type is not None:
            base_query = base_query.where(AuditLog.operation_type == query.operation_type)
        if query.start_time is not None:
            base_query = base_query.where(AuditLog.created_at >= query.start_time)
        if query.end_time is not None:
            base_query = base_query.where(AuditLog.created_at <= query.end_time)

        result = await self.db.execute(base_query.order_by(AuditLog.created_at.desc()))
        logs: List[AuditLog] = list(result.scalars().all())

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "操作人", "操作类型", "操作内容", "IP地址", "操作时间"])

        import json
        for log in logs:
            user_info = ""
            if log.user:
                user_info = f"{log.user.username}|{log.user.real_name}"
            writer.writerow([
                log.id,
                user_info,
                log.operation_type,
                json.dumps(log.operation_content or {}, ensure_ascii=False),
                log.ip_address,
                log.created_at.isoformat() if log.created_at else "",
            ])

        return output.getvalue().encode("utf-8-sig")