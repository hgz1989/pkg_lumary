"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 
"""
from datetime import datetime

from sqlalchemy import DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column


class SoftDeleteMixin:
    """SQLAlchemy 软删除混入类

    为业务模型提供 `is_deleted` 和 `deleted_at` 字段，
    用于实现逻辑删除，以保证数据的完整性和可追溯性
    """
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
