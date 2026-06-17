"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 全局异常处理器
"""
from functools import cache
from logging import getLogger
from typing import Any, Callable, Awaitable, Sequence

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.responses import Response

from .schemas import response_fail, response_with_extra_fail

_logger = getLogger(__name__)

ExceptionHandlers = dict[Any, Callable[[Request, Any], Response | Awaitable[Response]]]


def _is_json_parse_error(errors: list[dict] | Sequence[dict]) -> bool:
    """判断是否为JSON解析错误而非字段校验错误

    仅当 Pydantic 报告 type='json_invalid' 时才返回 True，
    避免将 list 类型字段校验失败（loc 中含整数索引）误判为 JSON 解析错误

    Args:
        errors: Pydantic校验错误列表

    Returns:
        True 表示 JSON 解析错误应返回 400，False 表示字段校验错误应返回 422
    """
    for error in errors:
        if error.get('type', '') == 'json_invalid':
            return True

    return False


@cache
def build_exception_handlers() -> ExceptionHandlers:
    """构建全局异常处理器字典

    返回异常类型到处理函数的映射字典，供 FastAPI 在初始化时通过
    exception_handlers 参数传入，确保 middleware stack 构建时已包含自定义处理器

    所有异常统一转换为标准 JSON 错误响应格式：
    {"code": xxx, "message": "...", "data": ...}

    Returns:
        异常处理器字典
    """

    # ── 第一层：参数校验异常 ──
    async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        """处理 Pydantic 请求参数校验失败

        JSON 格式非法 → 返回 400；字段校验失败 → 返回 422
        收集全部错误并将其展开为用户可读的提示

        Args:
            _request: 当前请求对象（未使用）
            exc: Pydantic 抛出的校验异常实例

        Returns:
            JSON 解析错误时 HTTP 400，字段校验失败时 HTTP 422
        """
        errors = exc.errors()
        if errors:
            error_parts = []
            for err in errors:
                loc = ' -> '.join(str(x) for x in err.get('loc', []))
                msg = err.get('msg', '')
                error_parts.append(f'{loc} {msg}' if loc else msg)
            error_msg = '参数校验失败：' + '；'.join(error_parts)
        else:
            error_msg = '参数校验失败'

        # JSON 格式非法（如 {invalid}）→ 400；字段校验失败 → 422
        if _is_json_parse_error(errors):
            http_status = status.HTTP_400_BAD_REQUEST
            business_code = status.HTTP_400_BAD_REQUEST
        else:
            http_status = status.HTTP_422_UNPROCESSABLE_CONTENT
            business_code = status.HTTP_422_UNPROCESSABLE_CONTENT

        _logger.error(f'请求参数校验失败: {error_msg}')

        resp = response_fail(
            code=business_code,
            message=error_msg
        )
        return JSONResponse(
            content=resp.model_dump(),
            status_code=http_status
        )

    # ── 第二层：所有 HTTP 协议异常（使用 starlette.HTTPException 作为基类，确保捕获框架自动抛出的 404/405 等）──
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        """统一处理所有 HTTP 层异常

        框架自动抛出的 400/401/403/404/405 以及用户手动 raise HTTPException
        均由此拦截。

        Args:
            _request: 当前请求对象（未使用）
            exc: FastAPI/Starlette 抛出的 HTTP 异常

        Returns:
            统一格式的 JSON 错误响应，HTTP 状态码与原异常一致
        """
        status_code = exc.status_code
        data: dict[str, Any] = {'code': status_code}

        if exc.detail:
            data['message'] = str(exc.detail)

        if exc.headers:
            extra = dict(exc.headers)
        else:
            extra = None

        _logger.error(
            f'HTTP Exception: Status Code = {status_code}, Detail = {exc.detail}, Headers = {extra}'
        )

        if extra:
            data['extra'] = extra
            resp = response_with_extra_fail(**data)
        else:
            resp = response_fail(**data)
        return JSONResponse(content=resp.model_dump(), status_code=status_code)

    # ── 第三层：未知异常兜底 ──
    async def exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        """兜底处理器：捕获所有未被上层匹配的未知异常

        记录完整堆栈日志，生产环境对客户端隐藏内部细节。

        Args:
            _request: 当前请求对象（未使用）
            exc: 未知的 Python 异常实例

        Returns:
            HTTP 500 + 统一格式的系统错误信息
        """
        _logger.critical(
            f'系统未捕获异常 类型:{type(exc).__name__} | 详情:{exc}',
            exc_info=True
        )
        resp = response_fail(
            code=500,
            message='系统内部错误，请联系管理员'
        )
        return JSONResponse(
            content=resp.model_dump(),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return {
        RequestValidationError: validation_exception_handler,
        HTTPException: http_exception_handler,
        Exception: exception_handler
    }
