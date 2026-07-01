"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 全局异常处理器
"""
from functools import cache
from logging import getLogger
from typing import TypeAlias, Any
from collections.abc import Callable, Awaitable, Sequence, Mapping

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from .schemas import response_fail

_logger = getLogger(__name__)

ExceptionHandlerFunc: TypeAlias = Callable[[Request, Any], Awaitable[JSONResponse]]
ExceptionHandlers: TypeAlias = dict[type[Exception], ExceptionHandlerFunc]

# 过滤监控接口，减少4xx日志刷屏
MONITOR_PATH_PREFIXES = ('/system/', '/health')


def _is_monitor_path(path: str) -> bool:
    """判断是否为监控接口，客户端错误日志降级

    Args:
        path: 当前请求路径

    Returns:
        是否为监控接口
    """
    return path.startswith(MONITOR_PATH_PREFIXES)


def _is_json_parse_error(errors: Sequence[dict]) -> bool:
    """判断是否为JSON解析错误而非字段校验错误

    Args:
        errors: Pydantic校验错误列表

    Returns:

    """
    return any(err.get('type', '') == 'json_invalid' for err in errors)


def _build_json_resp(
        status_code: int,
        code: int,
        message: str,
        extra: Any | None = None,
        headers: Mapping[str, str] | None = None
) -> JSONResponse:
    """构建JSON响应

    Args:
        status_code: HTTP状态码
        code: 状态码
        message: 提示信息
        extra: 扩展信息
        headers: 额外的HTTP头

    Returns:
        JSON响应
    """
    resp_model = response_fail(code=code, message=message, extra=extra)
    return JSONResponse(
        content=resp_model.model_dump(exclude_none=True),
        status_code=status_code,
        headers=headers
    )


@cache
def build_exception_handlers() -> ExceptionHandlers:
    """构建全局异常处理器字典

    返回异常类型到处理函数的映射字典，供FastAPI在初始化时通过
    exception_handlers参数传入，确保middleware stack构建时已包含自定义处理器

    所有异常统一转换为标准JSON错误响应格式：
    {"code": xxx, "message": "...", "data": ...}

    Returns:
        异常处理器字典
    """

    # ── 第一层：参数校验异常 ──
    async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        """处理Pydantic请求参数校验失败

        JSON格式非法 → 返回400；字段校验失败 → 返回422
        收集全部错误并将其展开为用户可读的提示

        Args:
            _request: 当前请求对象（未使用）
            exc: Pydantic抛出的校验异常实例

        Returns:
            JSON解析错误时HTTP 400，字段校验失败时HTTP 422
        """
        errors = exc.errors()
        extra_data = None

        if errors:
            error_parts = []
            error_details = []

            for err in errors:
                loc = ' -> '.join(str(x) for x in err.get('loc', []))
                msg = err.get('msg', '')
                err_type = err.get('type', '')
                error_parts.append(f'{loc} {msg}' if loc else msg)
                error_details.append({'loc': loc, 'msg': msg, 'type': err_type})

            error_msg = '参数校验失败：' + '；'.join(error_parts)
            extra_data = {'errors': error_details}
        else:
            error_msg = '参数校验失败'

        # JSON格式非法（如 {invalid}）→ 400；字段校验失败 → 422
        if _is_json_parse_error(errors):
            http_status = status.HTTP_400_BAD_REQUEST
        else:
            http_status = status.HTTP_422_UNPROCESSABLE_CONTENT

        log_message = (
            f'Validation Exception: Status Code = {http_status}, Biz Code = {http_status}, '
            f'Message = {error_msg}, Extra = {extra_data}'
        )

        # 如果是监控探针请求导致的 4xx/5xx，降级为 DEBUG 日志防止刷屏
        if _is_monitor_path(_request.url.path):
            _logger.debug(log_message)
        else:
            _logger.error(log_message)

        return _build_json_resp(
            status_code=http_status,
            code=http_status,
            message=error_msg,
            extra=extra_data
        )

    # ── 第二层：所有HTTP协议异常（使用starlette.HTTPException作为基类，确保捕获框架自动抛出的404/405等）──
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        """统一处理所有HTTP层异常

        框架自动抛出的400/401/403/404/405以及用户手动raise HTTPException
        均由此拦截

        Args:
            _request: 当前请求对象（未使用）
            exc: FastAPI/Starlette抛出的HTTP异常

        Returns:
            统一格式的JSON错误响应，HTTP状态码与原异常一致
        """
        status_code = exc.status_code
        detail = exc.detail
        headers = exc.headers
        code = status_code
        message = '请求失败'
        extra = None

        if isinstance(detail, dict):
            # 复制字典以防污染原始异常对象
            detail_data = detail.copy()
            code = detail_data.pop('code', status_code)
            message = detail_data.pop('message', None) or detail.pop('msg', '请求失败')
            extra = detail_data or None
        elif isinstance(detail, str):
            message = detail or '请求失败'

        log_message = (
            f'HTTP Exception: Status Code = {status_code}, Biz Code = {code}, Message = {message}, Extra = {extra}, '
            f'Headers = {dict(headers) if headers else None}'
        )

        if _is_monitor_path(_request.url.path):
            _logger.debug(log_message)
        else:
            _logger.error(log_message)

        return _build_json_resp(
            status_code=status_code,
            code=code,
            message=message,
            extra=extra,
            headers=headers
        )

    # ── 第三层：未知异常兜底 ──
    async def exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        """兜底处理器：捕获所有未被上层匹配的未知异常

        记录完整堆栈日志，生产环境对客户端隐藏内部细节

        Args:
            _request: 当前请求对象（未使用）
            exc: 未知的Python异常实例

        Returns:
            HTTP 500 + 统一格式的系统错误信息
        """
        _logger.error(
            f'系统未捕获异常 类型:{type(exc).__name__} | 详情:{exc}',
            exc_info=True
        )
        return _build_json_resp(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code=500,
            message='系统内部错误，请联系管理员'
        )

    return {
        RequestValidationError: validation_exception_handler,
        HTTPException: http_exception_handler,
        Exception: exception_handler
    }
