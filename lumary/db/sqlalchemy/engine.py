"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 
"""
from typing import Mapping, Any
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

# 定义支持的异步驱动列表
ASYNC_DRIVERS = frozenset({'asyncpg', 'asyncmy', 'aiomysql', 'aiosqlite', 'aioodbc'})


def _is_async_driver(url: str) -> bool:
    """根据URL中的驱动程序判断是否为异步

    Args:
        url: 数据库连接URL

    Returns:
        如果为异步驱动则返回True，否则返回False
    """
    return urlparse(url).scheme.split('+')[-1] in ASYNC_DRIVERS


def _connect_args_from_url(url: str) -> dict:
    """根据 URL 推断适配的 `connect_args`

    Args:
        url: 数据库连接 URL

    Returns:
        适用于该驱动的 `connect_args` 字典
    """
    scheme = urlparse(url).scheme
    if 'sqlite' in scheme:
        # SQLite 共享连接所需配置
        return {'check_same_thread': False}

    if _is_async_driver(url):
        # 异步驱动特定的连接参数（示例：asyncpg）
        if 'asyncpg' in scheme:
            return {
                'statement_cache_size': 0,
                'prepared_statement_cache_size': 0,
            }

    return {}


def create_db_engine(
        url: str,
        *,
        echo: bool = False,
        pool_pre_ping: bool = True,
        connect_args: Mapping[str, Any] | None = None,
        **engine_kwargs: Any
) -> AsyncEngine:
    """自动创建异步引擎

    默认从 settings.sqlalchemy_url 获取配置

    Args:
        url: 数据库连接 URL，默认为 None 时读取配置
        echo: 是否打印 SQL 日志
        pool_pre_ping: 是否在借出连接前测试连接
        connect_args: 传递给驱动的额外连接参数
        **engine_kwargs: 传递给 SQLAlchemy 引擎的额外参数

    Returns:
        返回 AsyncEngine 实例
    """
    if not _is_async_driver(url):
        raise ValueError(
            f'URL "{url}" is not an async driver,only asynchronous drives are supported. Please check your settings.')

    default_args = _connect_args_from_url(url)
    merged_args = {**default_args, **(connect_args or {})}

    return create_async_engine(
        url,
        echo=echo,
        pool_pre_ping=pool_pre_ping,
        connect_args=merged_args,
        **engine_kwargs
    )
