"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 
"""
from contextlib import asynccontextmanager
from typing import TypeVar, AsyncGenerator, Callable

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

T = TypeVar('T')


class SessionFactory:
    """数据库会话管理（无全局变量、传入 engine、更安全）"""

    def __init__(self, engine: AsyncEngine):
        """初始化

        Args:
            engine: 数据库异步引擎对象
        """
        self.engine = engine
        self.session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False
        )

    def get_service(self, service_cls: type[T]) -> Callable[[], T]:
        """生成服务依赖的工厂方法

        Args:
            service_cls: 服务类

        Returns:
            服务类实例
        """

        async def dependency() -> T:
            async with self.get_session() as db:
                return service_cls(db=db)

        dependency.__name__ = f'{service_cls.__name__}Service'
        dependency.__doc__ = f'自动注入 {service_cls.__name__}'
        return dependency

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """获取会话上下文（自动事务、自动回滚、自动关闭）

        Returns:
            数据库异步会话对象
        """
        async with self.session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
