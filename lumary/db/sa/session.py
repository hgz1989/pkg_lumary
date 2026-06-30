"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: SQLAlchemy会话工厂
"""
import random
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from inspect import signature
from typing import (
    TypeVar,
    Any
)
from collections.abc import Generator, Callable, AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    AsyncSession
)
from sqlalchemy.orm import Session, Mapper
from sqlalchemy.sql import ClauseElement

T = TypeVar('T')

# 路由上下文：默认走 'primary' 主库
routing_context: ContextVar[str] = ContextVar('routing_context', default='primary')


@contextmanager
def use_replica() -> Generator[None, None, None]:
    """上下文管理器：强制当前代码块内的查询走从库（如果存在）"""
    token = routing_context.set('replica')

    try:
        yield
    finally:
        routing_context.reset(token)


@contextmanager
def use_primary() -> Generator[None, None, None]:
    """上下文管理器：强制当前代码块内的查询走主库"""
    token = routing_context.set('primary')
    
    try:
        yield
    finally:
        routing_context.reset(token)


class RoutingSession(Session):
    """读写分离的底层同步会话拦截器

    拦截所有的数据库操作，根据 `routing_context` 上下文变量和是否在写入，
    决定返回主库还是从库的Engine
    """

    def get_bind(self, mapper: Mapper | None = None, clause: ClauseElement | None = None, **kw: Any):
        state = routing_context.get()

        # 如果正在进行flush操作（写入）或上下文明确要求主库，返回主库
        if self._flushing or state == 'primary':
            return self.info['primary'].sync_engine

        replicas = self.info.get('replicas', [])
        if replicas:
            # 如果配置了从库且上下文要求走从库，随机挑选一个从库
            return random.choice(replicas).sync_engine

        # 退级：没有从库则走主库
        return self.info['primary'].sync_engine


class SessionFactory:
    """数据库会话管理（支持读写分离主从架构）"""

    def __init__(self, engine: AsyncEngine | None = None, replica_engines: list[AsyncEngine] | None = None):
        """初始化

        Args:
            engine: 主库异步引擎对象（可为空，支持通过 init 延迟初始化）
            replica_engines: 可选的从库异步引擎列表
        """
        self.engine: AsyncEngine | None = None
        self.replica_engines: list[AsyncEngine] = []
        self.session_factory: async_sessionmaker[AsyncSession] | None = None
        
        if engine is not None:
            self.init(engine, replica_engines)

    def init(self, engine: AsyncEngine, replica_engines: list[AsyncEngine] | None = None) -> None:
        """延迟初始化引擎和会话工厂
        
        用于在生命周期钩子中初始化数据库连接
        """
        self.engine = engine
        self.replica_engines = replica_engines or []
        self.session_factory = async_sessionmaker(
            class_=AsyncSession,
            sync_session_class=RoutingSession,
            info={'primary': engine, 'replicas': self.replica_engines},
            expire_on_commit=False,
            autoflush=False
        )

    def get_service(self, service_cls: type[T]) -> Callable[[], AsyncGenerator[T, None]]:
        """生成服务依赖的工厂方法（旧版，需在路由中使用Depends(get_service)）

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

        通过重写类的__signature__，使其能在FastAPI路由中直接通过 `service: XXXService = Depends()` 使用
        服务类的__init__中需包含名为db或类型为AsyncSession的参数

        Returns:
            类装饰器
        """

        def decorator(cls: type[T]) -> type[T]:
            """装饰器：为服务类自动注入数据库会话

            Args:
                cls: 服务类

            Returns:
                装饰后的服务类
            """
            sig = signature(cls)

            async def db_dependency() -> AsyncGenerator[AsyncSession, None]:
                """数据库会话依赖

                Returns:
                    数据库会话
                """
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
        if self.session_factory is None:
            raise RuntimeError("数据库引擎未初始化，请在系统启动时调用 SessionFactory.init(engine)")

        async with self.session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
