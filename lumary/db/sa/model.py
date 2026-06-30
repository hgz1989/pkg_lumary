"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: SQLAlchemy ORM基础模型
"""
from datetime import datetime
from typing import Any

from sqlalchemy import String, func, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from ulid import ULID
from .base import Base


def _generate_ulid(_ctx: Any = None) -> str:
    """生成ULID

    Args:
        _ctx: 上下文

    Returns:
        ULID字符串
    """
    return str(ULID()).lower()


class ModelBase(Base):
    """SQLAlchemy模型基础类

    提供通用的主键、创建时间和更新时间字段
    """
    __abstract__ = True

    id: Mapped[str] = mapped_column(
        String(26),
        default=_generate_ulid,
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
