"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 全局异常处理器
"""
from logging import getLogger
from typing import Sequence

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.errors import ServerErrorMiddleware

from .schemas import response_fail

logger = getLogger(__name__)


def _is_json_parse_error(errors: list[dict] | Sequence[dict]) -> bool:
    """判断是否为JSON解析错误而非字段校验错误

    JSON格式非法时Pydantic报错 type='json_invalid'、loc含整数位置；
    字段校验失败时 loc 含字段名字符串

    Args:
        errors: Pydantic校验错误列表

    Returns:
        True 表示 JSON 解析错误应返回 400，False 表示字段校验错误应返回 422
    """
    for error in errors:
        err_type = error.get('type', '')

        if err_type == 'json_invalid':
            return True

        loc = error.get('loc', ())

        if len(loc) >= 2 and isinstance(loc[1], int):
            return True

    return False


def setup_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器

    按异常类型从具体到通用依次注册，所有异常统一转换为
    标准 JSON 错误响应格式：{"code": xxx, "message": "...", "data": ...}
    错误码约定：code = HTTP状态码 * 100（如 404 → 40400）

    Args:
        app: 当前运行的 FastAPI 应用实例
    """
    logger.debug(f'[{app.title}] register the global exception handler')

    # ── 第一层：参数校验异常（RequestValidationError 是 HTTPException 的子类，优先匹配）──
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        """处理 Pydantic 请求参数校验失败

        JSON 格式非法 → 返回 400；字段校验失败 → 返回 422
        从 errors 列表中提取首个错误，格式化为用户友好的提示。
        调试模式下在 data 字段返回完整错误列表供前端排查

        Args:
            _request: 当前请求对象（未使用）
            exc: Pydantic 抛出的校验异常实例

        Returns:
            JSON 解析错误时 HTTP 400，字段校验失败时 HTTP 422
        """
        errors = exc.errors()
        if errors:
            first_error = errors[0]
            loc = ' -> '.join(str(x) for x in first_error.get('loc', []))
            msg = first_error.get('msg', '')
            error_msg = f'参数校验失败：{loc} {msg}'
        else:
            error_msg = '参数校验失败'

        # JSON 格式非法（如 {invalid}）→ 400；字段校验失败 → 422
        if _is_json_parse_error(errors):
            http_status = status.HTTP_400_BAD_REQUEST
            business_code = 400
        else:
            http_status = status.HTTP_422_UNPROCESSABLE_CONTENT
            business_code = 422

        logger.warning(f'请求参数校验失败: {error_msg}')

        resp = response_fail(
            code=business_code,
            message=error_msg
        )
        return JSONResponse(
            content=resp.model_dump(),
            status_code=http_status,
        )

    # # ── 第二层：所有 HTTP 协议异常（400/401/402/403/404/405…）──
    # @app.exception_handler(400)
    # @app.exception_handler(401)
    # @app.exception_handler(402)
    # @app.exception_handler(403)
    # @app.exception_handler(404)
    # @app.exception_handler(405)
    # @app.exception_handler(HTTPException)
    # async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    #     """统一处理所有 HTTP 层异常
    #
    #     框架自动抛出的 401/403/404/405 以及用户手动 raise HTTPException
    #     均由此拦截，按 status_code * 100 计算业务错误码
    #
    #     Args:
    #         _request: 当前请求对象（未使用）
    #         exc: FastAPI/Starlette 抛出的 HTTP 异常
    #
    #     Returns:
    #         统一格式的 JSON 错误响应，HTTP 状态码与原异常一致
    #     """
    #     status_code = exc.status_code
    #
    #     logger.warning(f'HTTP {status_code}: {detail}')
    #
    #     resp = response_fail(
    #         code=status_code,
    #         message=detail[:300]
    #     )
    #     return JSONResponse(content=resp.model_dump(), status_code=status_code)

    # ── 第三层：未知异常兜底 ──
    @app.exception_handler(Exception)
    async def exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        """兜底处理器：捕获所有未被上层匹配的未知异常

        记录完整堆栈日志，生产环境对客户端隐藏内部细节

        Args:
            _request: 当前请求对象（未使用）
            exc: 未知的 Python 异常实例

        Returns:
            HTTP 500 + 统一格式的系统错误信息
        """
        logger.critical(
            f'system exceptions not captured exception type:{type(exc).__name__} | error info:{exc}',
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
