"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 
"""
from logging import getLogger
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = getLogger(__name__)


def setup_middlewares(
        app: FastAPI,
        *,
        enable_cors: bool,
        allow_origins: List[str] | None = None,
        allow_methods: List[str] | None = None,
        allow_headers: List[str] | None = None,
) -> None:
    """注册全局中间件

    将日志链路追踪、CORS 等中间件挂载到 FastAPI 实例。

    Args:
        app: 当前运行的 FastAPI 应用实例
        enable_cors: 是否启用 CORS 中间件
        allow_origins: 允许的源列表
        allow_methods: 允许的方法列表
        allow_headers: 允许的头列表
    """
    # 🔥 动态 CORS 跨域（根据配置开启）
    if enable_cors:
        app.add_middleware(
            CORSMiddleware,  # type: ignore
            allow_origins=allow_origins or ['*'],
            allow_credentials=True,
            allow_methods=allow_methods or ['*'],
            allow_headers=allow_headers or ['*']
        )
        logger.info('✅ CORS 跨域已启用')
