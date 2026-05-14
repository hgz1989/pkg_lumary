"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


class SessionFactory:
    """数据库会话管理（无全局变量、传入 engine、更安全）"""

    def __init__(self, engine: AsyncEngine):
        """初始化

        Args:
            engine:数据库异步引擎对象
        """
        self.engine = engine
        self.session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False
        )

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

    async def get_db(self) -> AsyncGenerator[AsyncSession, None]:
        """FastAPI 依赖注入专用

        Returns:
            数据库异步会话对象
        """
        async with self.get_session() as session:
            yield session