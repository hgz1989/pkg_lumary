"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: Lumary 模块
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
    WebSocketDisconnect
)
from fastapi.encoders import jsonable_encoder
from fastapi.responses import (
    JSONResponse,
    HTMLResponse,
    StreamingResponse,
    RedirectResponse,
    FileResponse
)
from pydantic import (
    BaseModel,
    Field,
    ConfigDict,
    field_validator,
    model_validator,
    ValidationError
)

from .__version__ import __version__
from .application import Lumary
from .common.utils import (
    camel_to_snake,
    snake_to_camel,
    random_string,
    json_dumps,
    json_loads
)
from .exceptions import (
    BadRequestError,
    UnauthorizedError,
    PaymentRequiredError,
    ForbiddenError,
    NotFoundError,
    MethodNotAllowedError,
    NotAcceptableError,
    RequestTimeoutError,
    ConflictError,
    GoneError,
    PreconditionFailedError,
    PayloadTooLargeError,
    URITooLongError,
    UnsupportedMediaTypeError,
    LockedError,
    TooManyRequestsError
)
from .lifespan import (
    HookRegistry,
    on_startup,
    on_shutdown,
    clear_hooks
)
from .schemas import (
    SchemaBase,
    PageQuery,
    TimeRangeQuery,
    KeywordQuery,
    BatchIds,
    APIResponse,
    PageData,
    response_success,
    response_fail
)

__all__ = [
    # 核心
    'Lumary',
    '__version__',
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
    # 常用异常
    'BadRequestError',
    'UnauthorizedError',
    'PaymentRequiredError',
    'ForbiddenError',
    'NotFoundError',
    'MethodNotAllowedError',
    'NotAcceptableError',
    'RequestTimeoutError',
    'ConflictError',
    'GoneError',
    'PreconditionFailedError',
    'PayloadTooLargeError',
    'URITooLongError',
    'UnsupportedMediaTypeError',
    'LockedError',
    'TooManyRequestsError',
    # 生命周期
    'HookRegistry',
    'on_startup',
    'on_shutdown',
    'clear_hooks',
    # Schema
    'SchemaBase',
    'PageQuery',
    'TimeRangeQuery',
    'KeywordQuery',
    'BatchIds',
    'APIResponse',
    'PageData',
    'response_success',
    'response_fail'
]
