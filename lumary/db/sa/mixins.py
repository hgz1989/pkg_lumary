"""
@Author     : zarkhan
@CreateDate : 2026/6/30
@Description: SQLAlchemy混入类
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column


class AuditMixin:
    """SQLAlchemy审计混入类

    为业务模型提供 `created_by` 和 `updated_by` 字段，
    用于记录数据的创建和修改人信息
    """
    __abstract__ = True

    created_by: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment='创建人'
    )
    updated_by: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment='最后修改人'
    )


class SoftDeleteMixin:
    """SQLAlchemy软删除混入类

    为业务模型提供 `is_deleted` 和 `deleted_at` 字段，
    用于实现逻辑删除，以保证数据的完整性和可追溯性
    """
    __abstract__ = True

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment='是否删除'
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment='删除时间'
    )
    deleted_by: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment='删除人'
    )
