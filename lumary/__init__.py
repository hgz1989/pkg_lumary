"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 
"""
from .common.enums import BaseEnum
from .common.mixins.sqlalchemy import SoftDeleteMixin
from .application import Lumary
from .lifespan import on_startup, on_shutdown
from .exceptions import BusinessException
from .schemas import (
    BaseSchema,
    APIResponse,
    PageData,
    PageQuery,
    response_success,
    response_fail
)
from .websocket import WSConnectionManager

__version__ = '0.1.0'

__all__ = [
    # 枚举基类
    'BaseEnum',
    # SQLAlchemy 混入类
    'SoftDeleteMixin',
    # 核心
    'Lumary',
    # 生命周期
    'on_startup',
    'on_shutdown',
    # 异常
    'BusinessException',
    # Schema
    'BaseSchema',
    'APIResponse',
    'PageQuery',
    'PageData',
    # 快捷函数
    'response_success',
    'response_fail',
    # WebSocket连接管理器
    'WSConnectionManager'
]
