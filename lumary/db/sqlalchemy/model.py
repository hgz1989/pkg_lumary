"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 
"""
from datetime import datetime

from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from ulid import ULID

from .base import Base


class ModelBase(Base):
    """SQLAlchemy 模型基础类

    提供通用的主键、创建时间和更新时间字段
    """
    __abstract__ = True

    id: Mapped[str] = mapped_column(
        String(26),
        default=lambda: str(ULID()).lower(),
        primary_key=True,
        comment='主键ID',
        sort_order=-10000
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment='创建时间'
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment='更新时间'
    )