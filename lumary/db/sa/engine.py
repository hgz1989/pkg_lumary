"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: SQLAlchemy引擎与连接管理
"""
from typing import Any
from collections.abc import Mapping
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
    """根据URL推断适配的connect_args

    Args:
        url: 数据库连接URL

    Returns:
        适用于该驱动的connect_args字典
    """
    scheme = urlparse(url).scheme
    if 'sqlite' in scheme:
        # SQLite共享连接所需配置
        return {'check_same_thread': False}

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
        **engine_kwargs: Any,
) -> AsyncEngine:
    """创建异步数据库引擎

    根据传入的URL自动推断驱动类型并配置对应的连接参数

    Args:
        url: 数据库连接URL
        echo: 是否打印SQL日志
        pool_pre_ping: 是否在借出连接前测试连接
        connect_args: 传递给驱动的额外连接参数
        **engine_kwargs: 传递给SQLAlchemy引擎的额外参数

    Returns:
        返回AsyncEngine实例
    """
    if not _is_async_driver(url):
        raise ValueError(
            f'URL "{url}" 不是异步驱动，仅支持异步驱动，请检查配置'
        )

    default_args = _connect_args_from_url(url)
    merged_args = {**default_args, **(connect_args or {})}

    return create_async_engine(url, echo=echo, pool_pre_ping=pool_pre_ping, connect_args=merged_args, **engine_kwargs)


def create_routing_engines(
        primary_url: str,
        replica_urls: list[str] | None = None,
        *,
        echo: bool = False,
        pool_pre_ping: bool = True,
        connect_args: Mapping[str, Any] | None = None,
        **engine_kwargs: Any,
) -> tuple[AsyncEngine, list[AsyncEngine]]:
    """创建支持读写分离的主从异步数据库引擎组

    Args:
        primary_url: 主库连接URL
        replica_urls: 从库连接URL列表
        echo: 是否打印SQL日志
        pool_pre_ping: 是否在借出连接前测试连接
        connect_args: 传递给驱动的额外连接参数
        **engine_kwargs: 传递给SQLAlchemy引擎的额外参数

    Returns:
        包含主引擎和从引擎列表的元组
    """
    primary_engine = create_db_engine(
        primary_url,
        echo=echo,
        pool_pre_ping=pool_pre_ping,
        connect_args=connect_args,
        **engine_kwargs,
    )

    replica_engines = []

    if replica_urls:
        for rep_url in replica_urls:
            replica_engines.append(
                create_db_engine(
                    rep_url,
                    echo=echo,
                    pool_pre_ping=pool_pre_ping,
                    connect_args=connect_args,
                    **engine_kwargs,
                )
            )

    return primary_engine, replica_engines
