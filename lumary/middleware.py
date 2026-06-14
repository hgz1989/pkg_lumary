"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 应用中间件配置
"""
from logging import getLogger

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
