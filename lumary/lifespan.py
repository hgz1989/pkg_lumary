"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 应用生命周期钩子管理
"""
from collections.abc import (
    Callable,
    AsyncGenerator
)
from contextlib import asynccontextmanager
from dataclasses import dataclass
from inspect import signature
from logging import getLogger
from typing import (
    runtime_checkable,
    Protocol,
    overload
)

from fastapi import FastAPI

logger = getLogger(__name__)


# 类型协议
@runtime_checkable
class _NoArgHook(Protocol):
    """无参数钩子协议定义"""
    async def __call__(self) -> None: ...


@runtime_checkable
class _AppArgHook(Protocol):
    """带 FastAPI 实例参数钩子协议定义"""
    async def __call__(self, app: FastAPI) -> None: ...


HookFunc = _NoArgHook | _AppArgHook


# 钩子条目
@dataclass(frozen=True)
class _HookItem:
    func: HookFunc
    priority: int
    abort_on_exception: bool
    needs_app: bool  # 是否需要注入 FastAPI 实例（注册时缓存签名结果）

    def __eq__(self, other: object) -> bool:
        """重写等于判断逻辑，用于去重

        防止同一个初始化函数被重复注册到列表中
        比较依据为函数的内存地址及其名称

        Args:
            other: 需要比较的另一个对象

        Returns:
            若两个钩子内部包装的是同一个函数，则返回 True
        """
        if not isinstance(other, _HookItem):
            return False

        return self.func.__name__ == other.func.__name__ and id(self.func) == id(other.func)


# 钩子注册表
class HookRegistry:
    """生命周期钩子注册表

    管理启动和关闭阶段的钩子函数，支持优先级排序和去重
    每个实例独立维护自己的钩子列表，便于测试隔离和多实例部署

    Examples:
        registry = HookRegistry()

        @registry.on_startup(priority=100)
        async def init_db():
            await create_engine()
    """

    __slots__ = ('_startup_hooks', '_shutdown_hooks')

    def __init__(self):
        """初始化"""
        self._startup_hooks: list[_HookItem] = []
        self._shutdown_hooks: list[_HookItem] = []

    def register_startup(self, func: HookFunc, priority: int, abort_on_exception: bool) -> None:
        """将启动钩子注册到列表中

        按优先级从大到小降序排列，priority 值越大的函数越先执行
        注册时自动检测函数签名并缓存结果，避免运行时重复反射

        Args:
            func: 待执行的异步函数
            priority: 执行优先级
            abort_on_exception: 异常时是否抛出 RuntimeError 终止启动
        """
        needs_app = len(signature(func).parameters) == 1
        item = _HookItem(func, priority, abort_on_exception, needs_app)
        if item not in self._startup_hooks:
            self._startup_hooks.append(item)
            self._startup_hooks.sort(key=lambda x: -x.priority)

    def register_shutdown(self, func: HookFunc, priority: int, abort_on_exception: bool) -> None:
        """将关闭钩子注册到列表中

        按优先级从小到大升序排列，以便进行反向清理
        注册时自动检测函数签名并缓存结果，避免运行时重复反射

        Args:
            func: 待执行的异步函数
            priority: 执行优先级
            abort_on_exception: 异常时是否抛出 RuntimeError
        """
        needs_app = len(signature(func).parameters) == 1
        item = _HookItem(func, priority, abort_on_exception, needs_app)
        if item not in self._shutdown_hooks:
            self._shutdown_hooks.append(item)
            self._shutdown_hooks.sort(key=lambda x: x.priority)

    async def run_startup(self, app: FastAPI) -> None:
        """执行所有启动钩子

        Args:
            app: 当前 FastAPI 应用实例
        """
        hooks_count = len(self._startup_hooks)
        if hooks_count > 0:
            logger.info(f'Executing {hooks_count} startup hooks...')
            await self._run_hooks(self._startup_hooks, app)
            logger.info('Startup hooks executed successfully.')

    async def run_shutdown(self, app: FastAPI) -> None:
        """执行所有关闭钩子

        Args:
            app: 当前 FastAPI 应用实例
        """
        hooks_count = len(self._shutdown_hooks)
        if hooks_count > 0:
            logger.info(f'Executing {hooks_count} shutdown hooks...')
            await self._run_hooks(self._shutdown_hooks, app)
            logger.info('Shutdown hooks executed successfully.')

    @staticmethod
    async def _run_hooks(hooks: list[_HookItem], app: FastAPI) -> None:
        """按序执行给定的生命周期钩子列表

        根据注册时缓存的签名结果决定是否注入 FastAPI 应用实例

        Args:
            hooks: 包含 _HookItem 的列表
            app: 当前 FastAPI 应用实例

        Raises:
            RuntimeError: 当 abort_on_exception=True 且执行发生异常时抛出
        """
        for item in hooks:
            try:
                if item.needs_app:
                    await item.func(app)
                else:
                    await item.func()
            except Exception as e:
                name = item.func.__name__
                logger.error(f'[生命周期钩子执行失败] {name}: {str(e)}')

                if item.abort_on_exception:
                    raise RuntimeError(f'[启动/关闭终止：钩子 {name} 异常]') from e

    def clear(self) -> None:
        """清空所有已注册的钩子（用于测试隔离）"""
        self._startup_hooks.clear()
        self._shutdown_hooks.clear()

    # 实例级装饰器
    @overload
    def on_startup(self, func: HookFunc) -> HookFunc:
        """注册服务启动(Startup)生命周期钩子的装饰器（实例级）
        
        Args:
            func: 挂载此装饰器的异步函数
            
        Returns:
            挂载的装饰器函数
        """
        ...

    @overload
    def on_startup(self, *, priority: int = 50, abort_on_exception: bool = True) -> Callable[[HookFunc], HookFunc]:
        """注册服务启动(Startup)生命周期钩子的装饰器（实例级）
        
        Args:
            priority: 优先级 (默认 50)。值越大，越早被执行
            abort_on_exception: 如果执行报错是否抛出异常阻止启动 (默认 True)
            
        Returns:
            挂载的装饰器函数
        """
        ...

    def on_startup(self, func: HookFunc | None = None, *, priority: int = 50, abort_on_exception: bool = True):
        """注册服务启动(Startup)生命周期钩子的装饰器（实例级）

        Args:
            func: 挂载此装饰器的异步函数
            priority: 优先级 (默认 50)。值越大，越早被执行
            abort_on_exception: 如果执行报错是否抛出异常阻止启动 (默认 True)
        """

        def decorator(fn: HookFunc) -> HookFunc:
            """内部装饰器函数

            Args:
                fn: 被装饰的钩子函数

            Returns:
                原封不动返回被装饰的函数
            """
            self.register_startup(fn, priority, abort_on_exception)
            return fn

        return decorator(func) if func else decorator

    @overload
    def on_shutdown(self, func: HookFunc) -> HookFunc:
        """注册服务关闭(Shutdown)生命周期钩子的装饰器（实例级）
        
        Args:
            func: 挂载此装饰器的异步函数
            
        Returns:
            挂载的装饰器函数
        """
        ...

    @overload
    def on_shutdown(
        self, *, priority: int = 50, abort_on_exception: bool = False
    ) -> Callable[[HookFunc], HookFunc]:
        """注册服务关闭(Shutdown)生命周期钩子的装饰器（实例级）
        
        Args:
            priority: 优先级 (默认 50)
            abort_on_exception: 报错时是否抛出异常 (默认 False)
            
        Returns:
            挂载的装饰器函数
        """
        ...

    def on_shutdown(self, func: HookFunc | None = None, *, priority: int = 50, abort_on_exception: bool = False):
        """注册服务关闭(Shutdown)生命周期钩子的装饰器（实例级）

        Args:
            func: 挂载此装饰器的异步函数
            priority: 优先级 (默认 50)
            abort_on_exception: 报错时是否抛出异常 (默认 False)
        """

        def decorator(fn: HookFunc) -> HookFunc:
            """内部装饰器函数

            Args:
                fn: 被装饰的钩子函数

            Returns:
                原封不动返回被装饰的函数
            """
            self.register_shutdown(fn, priority, abort_on_exception)
            return fn

        return decorator(func) if func else decorator


# 默认全局注册表（向后兼容）
_default_registry = HookRegistry()


# FastAPI 生命周期
@asynccontextmanager
async def fastapi_lifespan(app: FastAPI, registry: HookRegistry | None = None) -> AsyncGenerator[None, None]:
    """FastAPI 应用的生命周期管理函数

    用于处理应用启动前（startup）和关闭后（shutdown）的逻辑，
    例如：数据库连接池的建立与释放、全局资源的初始化与清理等

    Args:
        app: FastAPI 应用实例
        registry: 钩子注册表，为 None 时使用默认全局注册表

    Returns:
        异步生成器
    """
    reg = registry or _default_registry
    await reg.run_startup(app)
    yield
    await reg.run_shutdown(app)


# 模块级装饰器（向后兼容）
@overload
def on_startup(func: HookFunc) -> HookFunc:
    """注册服务启动(Startup)生命周期钩子的装饰器

    Args:
        func: 挂载此装饰器的异步函数

    Returns:
        挂载的装饰器函数
    """
    ...


@overload
def on_startup(*, priority: int = 50, abort_on_exception: bool = True) -> Callable[[HookFunc], HookFunc]:
    """注册服务启动(Startup)生命周期钩子的装饰器

    允许您将应用启动时的初始化逻辑（如数据库连接、数据预热等）分散到具体的业务模块中
    在 FastAPI 实例启动之前，会统一收集并按 `priority` 降序执行所有挂载了该装饰器的函数

    Args:
        priority: 优先级 (默认 50)。值越大，越早被执行
        abort_on_exception: 如果执行报错是否抛出异常阻止启动 (默认 True)

    Returns:
        挂载的装饰器函数
    """
    ...


def on_startup(func: HookFunc | None = None, *, priority: int = 50, abort_on_exception: bool = True):
    """注册服务启动(Startup)生命周期钩子的装饰器

    允许您将应用启动时的初始化逻辑（如数据库连接、数据预热等）分散到具体的业务模块中
    在 FastAPI 实例启动之前，会统一收集并按 `priority` 降序执行所有挂载了该装饰器的函数

    Args:
        func: 挂载此装饰器的异步函数
        priority: 优先级 (默认 50)。值越大，越早被执行
        abort_on_exception: 如果执行报错是否抛出异常阻止启动 (默认 True)

    Examples:
        @on_startup(priority=100)
        async def connect_db():
            await init_db()

        @on_startup
        async def load_cache(app: FastAPI):
            app.state.cache = .
    """

    def decorator(fn: HookFunc) -> HookFunc:
        """内部装饰器函数

        Args:
            fn: 被装饰的钩子函数

        Returns:
            原封不动返回被装饰的函数
        """
        _default_registry.register_startup(fn, priority, abort_on_exception)
        return fn

    return decorator(func) if func else decorator


@overload
def on_shutdown(func: HookFunc) -> HookFunc:
    """注册服务关闭(Shutdown)生命周期钩子的装饰器

    Args:
        func: 挂载此装饰器的异步函数

    Returns:
        挂载的装饰器函数
    """
    ...


@overload
def on_shutdown(*, priority: int = 50, abort_on_exception: bool = False) -> Callable[[HookFunc], HookFunc]:
    """注册服务关闭(Shutdown)生命周期钩子的装饰器

    Args:
        priority: 优先级 (默认 50)。启动时优先级越大的，关闭时优先级也应设为越大，它会越晚被清理
        abort_on_exception: 报错时是否抛出异常 (默认 False。关闭通常不应因局部报错而中断全局清理)

    Returns:
        挂载的装饰器函数
    """
    ...


def on_shutdown(func: HookFunc | None = None, *, priority: int = 50, abort_on_exception: bool = False):
    """注册服务关闭(Shutdown)生命周期钩子的装饰器

    允许您将应用关闭时的清理逻辑（如释放连接池、刷新日志等）分散到具体的业务模块中
    在 FastAPI 实例关闭之前，会统一收集并按 `priority` 升序执行所有挂载了该装饰器的函数
    （与启动时的顺序刚好相反，优先清理后初始化的资源）

    Args:
        func: 挂载此装饰器的异步函数
        priority: 优先级 (默认 50)。启动时优先级越大的，关闭时优先级也应设为越大，它会越晚被清理
        abort_on_exception: 报错时是否抛出异常 (默认 False。关闭通常不应因局部报错而中断全局清理)

    Examples:
        @on_shutdown
        async def close_db():
            await engine.dispose()
    """

    def decorator(fn: HookFunc) -> HookFunc:
        """内部装饰器函数

        Args:
            fn: 被装饰的钩子函数

        Returns:
            原封不动返回被装饰的函数
        """
        _default_registry.register_shutdown(fn, priority, abort_on_exception)
        return fn

    return decorator(func) if func else decorator


def clear_hooks() -> None:
    """清空默认全局注册表中的所有钩子（用于测试隔离）"""
    _default_registry.clear()
