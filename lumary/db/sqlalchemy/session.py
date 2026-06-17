"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: SQLAlchemy 会话工厂
"""
from inspect import signature
from contextlib import asynccontextmanager
from typing import TypeVar, Callable, AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    AsyncSession
)

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
            bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
        )

    def get_service(self, service_cls: type[T]) -> Callable[[], AsyncGenerator[T, None]]:
        """生成服务依赖的工厂方法（旧版，需在路由中使用 Depends(get_service)）

        Args:
            service_cls: 服务类

        Returns:
            服务类实例
        """

        async def dependency() -> AsyncGenerator[T, None]:
            """生成服务依赖的工厂方法

            Returns:
                服务类实例
            """
            async with self.get_session() as db:
                yield service_cls(db=db)

        dependency.__name__ = f'{service_cls.__name__}Service'
        dependency.__doc__ = f'自动注入 {service_cls.__name__}'
        return dependency

    def service(self) -> Callable[[type[T]], type[T]]:
        """类装饰器：为服务类自动注入数据库会话

        通过重写类的 __signature__，使其能在 FastAPI 路由中直接通过 `service: XXXService = Depends()` 使用。
        服务类的 `__init__` 中需包含名为 `db` 或类型为 `AsyncSession` 的参数。

        Returns:
            类装饰器
        """

        def decorator(cls: type[T]) -> type[T]:
            sig = signature(cls)

            async def db_dependency() -> AsyncGenerator[AsyncSession, None]:
                async with self.get_session() as db:
                    yield db

            new_params = []
            for p in sig.parameters.values():
                if p.name == 'db' or p.annotation is AsyncSession:
                    new_params.append(p.replace(default=Depends(db_dependency)))
                else:
                    new_params.append(p)

            cls.__signature__ = sig.replace(parameters=new_params)  # type: ignore
            return cls

        return decorator

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
