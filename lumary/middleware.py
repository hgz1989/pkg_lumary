"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 应用中间件配置
"""
from logging import getLogger
from typing import Callable, Awaitable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from .common import (
    generate_request_id,
    set_request_id,
    request_id_ctx_var
)

logger = getLogger(__name__)


def setup_middlewares(
        app: FastAPI,
        *,
        enable_cors: bool,
        allow_origins: list[str] | None = None,
        allow_methods: list[str] | None = None,
        allow_headers: list[str] | None = None,
) -> None:
    """注册全局中间件

    将日志链路追踪、CORS 等中间件挂载到 FastAPI 实例

    Args:
        app: 当前运行的 FastAPI 应用实例
        enable_cors: 是否启用 CORS 中间件
        allow_origins: 允许的源列表
        allow_methods: 允许的方法列表
        allow_headers: 允许的头列表
    """
    # 动态 CORS 跨域（根据配置开启）
    if enable_cors:
        origins = allow_origins or ['*']
        # 避免 `allow_origins=['*']` 与 `allow_credentials=True` 同时出现引发的兼容和安全风险
        credentials = origins != ['*']

        app.add_middleware(
            CORSMiddleware,  # type: ignore
            allow_origins=origins,
            allow_credentials=credentials,
            allow_methods=allow_methods or ['*'],
            allow_headers=allow_headers or ['*'],
        )
        logger.info(f'[{app.title}] Cross-Origin Resource Sharing enabled')

    # 保留你原来的内联中间件写法，仅加 try/finally 重置上下文
    @app.middleware('http')
    async def request_id_middleware(
            request: Request,
            call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """ 添加请求ID

        Args:
            request: 当前请求对象
            call_next: 下一个中间件或目标应用

        Returns:
            响应对象
        """
        request_id = request.headers.get('X-Request-ID') or generate_request_id()
        token = set_request_id(request_id)
        try:
            response = await call_next(request)
            response.headers['X-Request-ID'] = request_id
            return response
        finally:
            # 关键：清除上下文，防止不同请求ID串数据
            request_id_ctx_var.reset(token)
