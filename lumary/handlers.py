"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 
"""
from logging import getLogger

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException

from .exceptions import BusinessException
from .schemas import response_fail

logger = getLogger(__name__)


def setup_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器

    将各类异常（业务异常、参数校验、数据库错误、框架内部 HTTP 错误及未知异常）
    的拦截逻辑挂载到 FastAPI 应用实例上，实现统一响应格式和日志记录

    Args:
        app: 当前运行的 FastAPI 应用实例
    """

    @app.exception_handler(BusinessException)
    async def business_exception_handler(_request: Request, exc: BusinessException) -> JSONResponse:
        """处理自定义业务异常

        将 `BusinessException` 转换为 `JSONResponse` 返回给客户端
        业务错误属于正常逻辑流转，HTTP 状态码始终返回 200 OK

        Args:
            _request: 当前请求对象（未使用）
            exc: 捕获到的业务异常实例

        Returns:
            包含错误码和错误信息的 JSON 响应
        """
        logger.warning(f'Business exception occurred: {exc.message}')
        # 👇 直接用 fail() → 自动生成标准 APIResponse
        resp = response_fail(code=exc.code, message=exc.message, data=exc.data)
        return JSONResponse(content=resp.model_dump())

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

        # 👇 直接用 fail() → 自动生成标准 APIResponse
        resp = response_fail(code=status.HTTP_422_UNPROCESSABLE_CONTENT, message=error_msg, data=errors)
        return JSONResponse(resp.model_dump(), status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)

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
        # 👇 直接用 fail() → 自动生成标准 APIResponse
        resp = response_fail(code=exc.status_code, message=str(exc.detail))
        return JSONResponse(resp.model_dump(), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def global_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        """处理未捕获的全局异常 (兜底方案)

        拦截所有未被显式捕获的 Python 运行时错误（如空指针、索引越界、除零错误等）
        记录完整的异常堆栈日志，并向客户端返回 500 系统错误提示

        Args:
            _request: 当前请求对象（未使用）
            exc: 未捕获的任意 Python 异常实例

        Returns:
            HTTP 500 及系统内部错误提示
        """
        logger.critical(f'❌ Global anomalies occur: {exc}')

        # 👇 直接用 fail() → 自动生成标准 APIResponse
        resp = response_fail(code=status.HTTP_500_INTERNAL_SERVER_ERROR, message='系统内部错误，请联系管理员')
        return JSONResponse(resp.model_dump(), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
