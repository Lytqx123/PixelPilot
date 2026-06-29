# 检索权限过滤：按部门隔离数据，防止跨部门信息泄露

from typing import Dict, Any, Optional, List


class VectorQueryFilterBuilder:
    """
    向量检索权限过滤构建器

    策略（与 permissions.py 的 resolve_document_access 保持一致）：
    - 超级管理员（SUPER_ADMIN）：不做部门过滤，可见所有已审核文档
    - 非超级管理员（ADMIN/REVIEWER/普通员工）：可见所在部门的已审核文档
      + 超级管理员上传的全员可见文档（is_public_to_all=1）
    - 同时始终过滤 is_reviewed=True（仅展示已审核发布的文档）
    """

    @staticmethod
    def _is_super_admin(user) -> bool:
        role_code = user.role.role_code if user.role and user.role.role_code else ""
        return role_code == "SUPER_ADMIN"

    @staticmethod
    def build(user) -> Dict[str, Any]:
        """
        构建 Qdrant 过滤条件

        :param user: 当前用户对象
        :return: Qdrant 格式的过滤条件字典
        """
        # must: 必须满足的条件 - 仅检索已审核发布的文档
        must_clauses: List[Dict[str, Any]] = [
            {"key": "is_reviewed", "match": {"value": True}}
        ]

        # 超级管理员：不做部门过滤，可见所有部门所有已审核文档
        if VectorQueryFilterBuilder._is_super_admin(user):
            return {"must": must_clauses}

        # 非超级管理员：本部门文档 OR 全员可见文档（超级管理员上传）
        should_clauses: List[Dict[str, Any]] = []

        # 条件1: 本部门文档 / 未分配部门文档
        if user.department_id is not None:
            should_clauses.append(
                {"key": "department_id", "match": {"value": user.department_id}}
            )
        else:
            should_clauses.append(
                {"key": "department_id", "is_empty": True}
            )

        # 条件2: 全员可见文档（超级管理员上传的文档）
        should_clauses.append(
            {"key": "is_public_to_all", "match": {"value": 1}}
        )

        return {"must": must_clauses, "should": should_clauses}

    @staticmethod
    def build_sql_filter(user, Document) -> list:
        """
        构建 SQLAlchemy 过滤条件（用于关键词检索）

        与 build() 保持一致的权限逻辑：非超级管理员检索本部门文档 + 全员可见文档

        :param user: 当前用户对象
        :param Document: Document 模型类
        :return: SQLAlchemy 条件列表（各条件为 AND 关系，最后一个为 OR 组合的访问条件）
        """
        from sqlalchemy import or_

        # 仅检索已审核通过的文档(status=1)
        conditions = [Document.status == 1]

        if VectorQueryFilterBuilder._is_super_admin(user):
            return conditions

        # 非超级管理员：本部门文档 OR 全员可见文档
        access_conditions = []

        # 条件1: 本部门文档 / 未分配部门文档
        if user.department_id is not None:
            access_conditions.append(Document.department_id == user.department_id)
        else:
            access_conditions.append(Document.department_id.is_(None))

        # 条件2: 全员可见文档（超级管理员上传的文档）
        access_conditions.append(Document.is_public_to_all == 1)

        conditions.append(or_(*access_conditions))

        return conditions
