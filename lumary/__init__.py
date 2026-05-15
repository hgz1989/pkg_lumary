"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 
"""
from .application import Lumary
from .common.enums import BaseEnum
from .lifespan import HookRegistry, on_startup, on_shutdown, clear_hooks
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
    # 核心
    'Lumary',
    # 枚举基类
    'BaseEnum',
    # 生命周期
    'HookRegistry',
    'on_startup',
    'on_shutdown',
    'clear_hooks',
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
