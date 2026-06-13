"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 全局异常处理器
"""
from logging import getLogger

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError, HTTPException
from fastapi.responses import JSONResponse
from .schemas import response_fail

logger = getLogger(__name__)


def setup_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器

    将各类异常（业务异常、参数校验、数据库错误、框架内部 HTTP 错误及未知异常）
    的拦截逻辑挂载到 FastAPI 应用实例上，实现统一响应格式和日志记录

    Args:
        app: 当前运行的 FastAPI 应用实例
    """

    @app.exception_handler(Exception)
    async def global_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        """处理未捕获的全局异常 (兜底方案)

        Args:
            _request: 当前请求对象（未使用）
            exc: 异常实例

        Returns:
            HTTP 500 及统一错误格式的 JSON 响应
        """
        logger.critical(f'Global anomalies occur: {exc}', exc_info=True)
        # 调试模式截取异常信息，避免内容过长
        err_detail = str(exc)[:300] if app.debug else None
        # 构建统一错误响应
        resp = response_fail(
            code=500,
            message='System internal errors; please contact your administrator',
            data=err_detail
        )

        return JSONResponse(
            content=resp.model_dump(),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        """处理 Pydantic 参数校验异常 (HTTP 422)

        当请求体、路径参数或查询参数不符合 Pydantic 模型定义时触发
        自动提取第一个具体地校验错误信息并拼接，以对用户友好的形式返回

        Args:
            _request: 当前请求对象（未使用）
            exc: Pydantic 抛出的校验异常实例

        Returns:
            HTTP 400 及格式化后的参数错误信息
        """
        # 提取第一个错误的详细信息
        errors = exc.errors()
        if errors:
            first_error = errors[0]
            loc = ' -> '.join([str(x) for x in first_error.get('loc', [])])
            msg = first_error.get('msg', '')
            error_msg = f'Parameter verification failed: [{loc}] {msg}'
        else:
            error_msg = 'Parameter verification error'

        logger.error(f'Request validation error: {exc}', exc_info=True)
        # 调试模式截取异常信息，避免内容过长
        err_detail = error_msg if app.debug else None

        # 将参数校验错误转化为内置 HTTP 异常，再交由 http_exception_handler 处理
        # HTTP 422 Unprocessable Entity
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=error_msg
        )

    @app.exception_handler(400)
    @app.exception_handler(401)
    @app.exception_handler(403)
    @app.exception_handler(404)
    @app.exception_handler(405)
    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        """处理 FastAPI 内置的 HTTP 异常

        捕获框架自动抛出或通过 `raise HTTPException` 抛出的错误（如 401 鉴权失败、404 路由不存在）
        将其重新封装为符合项目规范的 JSON 结构

        Args:
            _request: 当前请求对象（未使用）
            exc: FastAPI 抛出的 HTTP 异常实例

        Returns:
            继承原状态码及统一错误格式的 JSON 响应
        """
        logger.error(f'HTTP exception occur: {exc.detail}', exc_info=True)
        # 调试模式截取异常信息，避免内容过长
        err_detail = str(exc.detail)[:300] if app.debug else None
        resp = response_fail(
            code=exc.status_code * 100,
            message=str(exc.detail),
            data=err_detail
        )
        return JSONResponse(resp.model_dump(), status_code=exc.status_code)
