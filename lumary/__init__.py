"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 
"""
from fastapi import (
    FastAPI,
    APIRouter,
    Depends,
    Query,
    Path,
    Body,
    Header,
    Cookie,
    Form,
    File,
    UploadFile,
    Request,
    Response,
    HTTPException,
    BackgroundTasks,
    status,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import (
    JSONResponse,
    HTMLResponse,
    StreamingResponse,
    RedirectResponse,
    FileResponse,
)
from fastapi.encoders import jsonable_encoder
from pydantic import (
    BaseModel,
    Field,
    ConfigDict,
    field_validator,
    model_validator,
    ValidationError,
)

from .application import Lumary
from .lifespan import (
    HookRegistry,
    on_startup,
    on_shutdown,
    clear_hooks
)
from .exceptions import BusinessException
from .schemas import (
    SchemaBase,
    PageData,
    PageQuery,
    APIResponse,
    response_success,
    response_fail
)
from .websocket import WSConnectionManager

__version__ = '0.1.5'

__all__ = [
    # 核心
    'Lumary',

    # FastAPI 常用对象
    'FastAPI',
    'APIRouter',
    'Depends',
    'Query',
    'Path',
    'Body',
    'Header',
    'Cookie',
    'Form',
    'File',
    'UploadFile',
    'Request',
    'Response',
    'HTTPException',
    'BackgroundTasks',
    'status',
    'WebSocket',
    'WebSocketDisconnect',

    # FastAPI 常用响应类与工具
    'JSONResponse',
    'HTMLResponse',
    'StreamingResponse',
    'RedirectResponse',
    'FileResponse',
    'jsonable_encoder',

    # Pydantic 常用对象
    'BaseModel',
    'Field',
    'ConfigDict',
    'field_validator',
    'model_validator',
    'ValidationError',

    # 生命周期
    'HookRegistry',
    'on_startup',
    'on_shutdown',
    'clear_hooks',

    # 异常
    'BusinessException',

    # Schema
    'SchemaBase',
    'PageQuery',
    'PageData',
    'APIResponse',
    # 快捷函数
    'response_success',
    'response_fail',

    # WebSocket连接管理器
    'WSConnectionManager'
]
