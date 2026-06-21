"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 应用生命周期钉子管理
"""
import asyncio
from collections.abc import (
    Callable,
    AsyncGenerator
)
from contextlib import asynccontextmanager
from dataclasses import dataclass
from logging import getLogger
from typing import runtime_checkable, Protocol, overload

from fastapi import FastAPI

_logger = getLogger(__name__)


# 类型协议
@runtime_checkable
class _NoArgHook(Protocol):
    """无参数钉子协议定义"""

    async def __call__(self) -> None: ...


@runtime_checkable
class _AppArgHook(Protocol):
    """带 FastAPI 实例参数钉子协议定义"""

    async def __call__(self, app: FastAPI) -> None: ...


HookFunc = _NoArgHook | _AppArgHook


# 钉子条目
@dataclass(frozen=True)
class _HookItem:
    func: HookFunc
    priority: int
    abort_on_exception: bool
    needs_app: bool  # 是否需要注入 FastAPI 实例（注册时缓存签名结果）
    timeout: float | None = None  # 单个钉子执行超时（秒），None 表示不限制

    def __eq__(self, other: object) -> bool:
        """重写等于判断逻辑，用于去重

        防止同一个初始化函数被重复注册到列表中
        比较依据为函数的内存地址及其名称

        Args:
            other: 需要比较的另一个对象

        Returns:
            若两个钉子内部包装的是同一个函数，则返回 True
        """
        if not isinstance(other, _HookItem):
            return False

        return self.func.__name__ == other.func.__name__ and id(self.func) == id(other.func)

    def __hash__(self) -> int:
        """重写哈希逻辑以支持 Set 数据结构的高效排重

        由于重写了 __eq__，dataclass 默认会禁用 __hash__，
        因此必须手动实现以提供 O(1) 的去重性能

        Returns:
            哈希值
        """
        return hash((self.func.__name__, id(self.func)))


# 钉子注册表
class HookRegistry:
    """生命周期钉子注册表

    管理启动和关闭阶段的钉子函数，支持优先级排序和去重
    每个实例独立维护自己的钉子列表，便于测试隔离和多实例部署

    Examples:
        registry = HookRegistry()

        @registry.on_startup(priority=100)
        async def init_db():
            await create_engine()
    """

    __slots__ = ('_startup_hooks', '_shutdown_hooks', '_startup_seen', '_shutdown_seen')

    def __init__(self):
        """初始化"""
        self._startup_hooks: list[_HookItem] = []
        self._shutdown_hooks: list[_HookItem] = []
        self._startup_seen: set[_HookItem] = set()
        self._shutdown_seen: set[_HookItem] = set()

    def register_startup(
            self,
            func: HookFunc,
            priority: int,
            abort_on_exception: bool,
            timeout: float | None = None
    ) -> None:
        """将启动钉子注册到列表中

        按优先级从大到小降序排列，priority 值越大的函数越先执行
        注册时自动检测函数签名并缓存结果，避免运行时重复反射

        Args:
            func: 待执行的异步函数
            priority: 执行优先级
            abort_on_exception: 异常时是否抛出 RuntimeError 终止启动
            timeout: 单个钉子执行超时（秒），None 表示不限制
        """
        needs_app = isinstance(func, _AppArgHook)
        item = _HookItem(func, priority, abort_on_exception, needs_app, timeout)
        if item not in self._startup_seen:
            self._startup_seen.add(item)
            self._startup_hooks.append(item)
            self._startup_hooks.sort(key=lambda x: -x.priority)

    def register_shutdown(
            self,
            func: HookFunc,
            priority: int,
            abort_on_exception: bool,
            timeout: float | None = None
    ) -> None:
        """将关闭钉子注册到列表中

        按优先级从小到大升序排列，以便进行反向清理
        注册时自动检测函数类型并缓存结果，避免运行时重复反射

        Args:
            func: 待执行的异步函数
            priority: 执行优先级
            abort_on_exception: 异常时是否抛出 RuntimeError
            timeout: 单个钉子执行超时（秒），None 表示不限制
        """
        needs_app = isinstance(func, _AppArgHook)
        item = _HookItem(func, priority, abort_on_exception, needs_app, timeout)
        if item not in self._shutdown_seen:
            self._shutdown_seen.add(item)
            self._shutdown_hooks.append(item)
            self._shutdown_hooks.sort(key=lambda x: x.priority)

    async def run_startup(self, app: FastAPI) -> None:
        """执行所有启动钉子

        Args:
            app: 当前 FastAPI 应用实例
        """
        hooks_count = len(self._startup_hooks)
        if hooks_count > 0:
            _logger.info(f'正在执行 {hooks_count} 个启动钉子...')
            await self._run_hooks(self._startup_hooks, app)
            _logger.info('启动钉子执行完成')

    async def run_shutdown(self, app: FastAPI) -> None:
        """执行所有关闭钉子

        Args:
            app: 当前 FastAPI 应用实例
        """
        hooks_count = len(self._shutdown_hooks)
        if hooks_count > 0:
            _logger.info(f'正在执行 {hooks_count} 个关闭钉子...')
            await self._run_hooks(self._shutdown_hooks, app)
            _logger.info('关闭钉子执行完成')

    @staticmethod
    async def _run_hooks(hooks: list[_HookItem], app: FastAPI) -> None:
        """按序执行给定的生命周期钉子列表

        根据注册时缓存的签名结果决定是否注入 FastAPI 应用实例
        如果钉子设置了 timeout，使用 asyncio.wait_for 强制超时

        Args:
            hooks: 包含 _HookItem 的列表
            app: 当前 FastAPI 应用实例

        Raises:
            RuntimeError: 当 abort_on_exception=True 且执行发生异常时抛出
        """
        for item in hooks:
            name = item.func.__name__
            try:
                coro = item.func(app) if item.needs_app else item.func()
                if item.timeout is not None:
                    await asyncio.wait_for(coro, timeout=item.timeout)
                else:
                    await coro
            except asyncio.TimeoutError:
                _logger.error(
                    f'[生命周期钉子执行超时] {name}: 超过 {item.timeout}s'
                )
                if item.abort_on_exception:
                    raise RuntimeError(f'[启动/关闭终止：钉子 {name} 执行超时]')
            except Exception as e:
                _logger.error(f'[生命周期钉子执行失败] {name}: {str(e)}')

                if item.abort_on_exception:
                    raise RuntimeError(f'[启动/关闭终止：钉子 {name} 异常]') from e

    def clear(self) -> None:
        """清空所有已注册的钉子（用于测试隔离）"""
        self._startup_hooks.clear()
        self._shutdown_hooks.clear()
        self._startup_seen.clear()
        self._shutdown_seen.clear()

    def list_startup_hooks(self) -> list[str]:
        """列举已注册的启动钉子信息

        返回按执行顺序排列的钉子描述列表，便于调试时查看注册状态

        Returns:
            启动钉子描述列表，格式为「func_name(priority=N, abort=T, timeout=Xs)」
        """
        return [
            f'{item.func.__name__}('
            f'priority={item.priority}, '
            f'abort={item.abort_on_exception}, '
            f'timeout={f"{item.timeout}s" if item.timeout is not None else "None"})'
            for item in self._startup_hooks
        ]

    def list_shutdown_hooks(self) -> list[str]:
        """列举已注册的关闭钉子信息

        返回按执行顺序排列的钉子描述列表，便于调试时查看注册状态

        Returns:
            关闭钉子描述列表，格式为「func_name(priority=N, abort=T, timeout=Xs)」
        """
        return [
            f'{item.func.__name__}('
            f'priority={item.priority}, '
            f'abort={item.abort_on_exception}, '
            f'timeout={f"{item.timeout}s" if item.timeout is not None else "None"})'
            for item in self._shutdown_hooks
        ]

    @overload
    def on_startup(self, func: HookFunc) -> HookFunc:
        """注册服务启动(Startup)生命周期钉子的装饰器（实例级）

        Args:
            func: 挂载此装饰器的异步函数

        Returns:
            挂载的装饰器函数
        """
        ...

    @overload
    def on_startup(
            self,
            *,
            priority: int = 50,
            abort_on_exception: bool = True,
            timeout: int | float | None = None
    ) -> Callable[[HookFunc], HookFunc]:
        """注册服务启动(Startup)生命周期钉子的装饰器（实例级）

        Args:
            priority: 优先级 (默认 50)。值越大，越早被执行
            abort_on_exception: 如果执行报错是否抛出异常阻止启动 (默认 True)
            timeout: 钉子执行超时（秒），None 表示不限制 (默认 None)

        Returns:
            挂载的装饰器函数
        """
        ...

    def on_startup(
            self,
            func: HookFunc | None = None,
            *,
            priority: int = 50,
            abort_on_exception: bool = True,
            timeout: int | float | None = None
    ) -> Callable[[HookFunc], HookFunc] | HookFunc:
        """注册服务启动(Startup)生命周期钉子的装饰器（实例级）

        Args:
            func: 挂载此装饰器的异步函数
            priority: 优先级 (默认 50)。值越大，越早被执行
            abort_on_exception: 如果执行报错是否抛出异常阻止启动 (默认 True)
            timeout: 钉子执行超时（秒），None 表示不限制 (默认 None)
        """

        def decorator(fn: HookFunc) -> HookFunc:
            """内部装饰器函数

            Args:
                fn: 被装饰的钉子函数

            Returns:
                原封不动返回被装饰的函数
            """
            self.register_startup(fn, priority, abort_on_exception, timeout)
            return fn

        return decorator(func) if func else decorator

    @overload
    def on_shutdown(self, func: HookFunc) -> HookFunc:
        """注册服务关闭(Shutdown)生命周期钉子的装饰器（实例级）

        Args:
            func: 挂载此装饰器的异步函数

        Returns:
            挂载的装饰器函数
        """
        ...

    @overload
    def on_shutdown(
            self,
            *,
            priority: int = 50,
            abort_on_exception: bool = False,
            timeout: float | None = None
    ) -> Callable[[HookFunc], HookFunc] | HookFunc:
        """注册服务关闭(Shutdown)生命周期钉子的装饰器（实例级）

        Args:
            priority: 优先级 (默认 50)
            abort_on_exception: 报错时是否抛出异常 (默认 False)
            timeout: 钉子执行超时（秒），None 表示不限制 (默认 None)

        Returns:
            挂载的装饰器函数
        """
        ...

    def on_shutdown(
            self,
            func: HookFunc | None = None,
            *,
            priority: int = 50,
            abort_on_exception: bool = False,
            timeout: float | None = None
    ) -> Callable[[HookFunc], HookFunc] | HookFunc:
        """注册服务关闭(Shutdown)生命周期钉子的装饰器（实例级）

        Args:
            func: 挂载此装饰器的异步函数
            priority: 优先级 (默认 50)
            abort_on_exception: 报错时是否抛出异常 (默认 False)
            timeout: 钉子执行超时（秒），None 表示不限制 (默认 None)
        """

        def decorator(fn: HookFunc) -> HookFunc:
            """内部装饰器函数

            Args:
                fn: 被装饰的钉子函数

            Returns:
                原封不动返回被装饰的函数
            """
            self.register_shutdown(fn, priority, abort_on_exception, timeout)
            return fn

        return decorator(func) if func else decorator


# 默认全局注册表（向后兼容）
default_registry = HookRegistry()


# FastAPI 生命周期
@asynccontextmanager
async def fastapi_lifespan(app: FastAPI, registry: HookRegistry | None = None) -> AsyncGenerator[None, None]:
    """FastAPI 应用的生命周期管理函数

    用于处理应用启动前（startup）和关闭后（shutdown）的逻辑，
    例如：数据库连接池的建立与释放、全局资源的初始化与清理等

    Args:
        app: FastAPI 应用实例
        registry: 钉子注册表，为 None 时使用默认全局注册表

    Returns:
        异步生成器
    """
    reg = registry or default_registry
    await reg.run_startup(app)
    yield
    await reg.run_shutdown(app)


# 模块级装饰器（向后兼容）
@overload
def on_startup(func: HookFunc) -> HookFunc:
    """注册服务启动(Startup)生命周期钉子的装饰器

    Args:
        func: 挂载此装饰器的异步函数

    Returns:
        挂载的装饰器函数
    """
    ...


@overload
def on_startup(
        *,
        priority: int = 50,
        abort_on_exception: bool = True,
        timeout: float | None = None
) -> Callable[[HookFunc], HookFunc] | HookFunc:
    """注册服务启动(Startup)生命周期钉子的装饰器

    允许您将应用启动时的初始化逻辑（如数据库连接、数据预热等）分散到具体的业务模块中
    在 FastAPI 实例启动之前，会统一收集并按 `priority` 降序执行所有挂载了该装饰器的函数

    Args:
        priority: 优先级 (默认 50)。值越大，越早被执行
        abort_on_exception: 如果执行报错是否抛出异常阻止启动 (默认 True)
        timeout: 钉子执行超时（秒），None 表示不限制 (默认 None)

    Returns:
        挂载的装饰器函数
    """
    ...


def on_startup(
        func: HookFunc | None = None,
        *, priority: int = 50,
        abort_on_exception: bool = True,
        timeout: float | None = None
) -> Callable[[HookFunc], HookFunc] | HookFunc:
    """注册服务启动(Startup)生命周期钉子的装饰器

    允许您将应用启动时的初始化逻辑（如数据库连接、数据预热等）分散到具体的业务模块中
    在 FastAPI 实例启动之前，会统一收集并按 `priority` 降序执行所有挂载了该装饰器的函数

    Args:
        func: 挂载此装饰器的异步函数
        priority: 优先级 (默认 50)。值越大，越早被执行
        abort_on_exception: 如果执行报错是否抛出异常阻止启动 (默认 True)
        timeout: 钉子执行超时（秒），None 表示不限制 (默认 None)

    Examples:
        @on_startup(priority=100)
        async def connect_db():
            await init_db()

        @on_startup
        async def load_cache(app: FastAPI):
            app.state.cache = await build_cache()
    """

    def decorator(fn: HookFunc) -> HookFunc:
        """内部装饰器函数

        Args:
            fn: 被装饰的钉子函数

        Returns:
            原封不动返回被装饰的函数
        """
        default_registry.register_startup(fn, priority, abort_on_exception, timeout)
        return fn

    return decorator(func) if func else decorator


@overload
def on_shutdown(func: HookFunc) -> HookFunc:
    """注册服务关闭(Shutdown)生命周期钉子的装饰器

    Args:
        func: 挂载此装饰器的异步函数

    Returns:
        挂载的装饰器函数
    """
    ...


@overload
def on_shutdown(
        *,
        priority: int = 50,
        abort_on_exception: bool = False,
        timeout: int | float | None = None
) -> Callable[[HookFunc], HookFunc] | HookFunc:
    """注册服务关闭(Shutdown)生命周期钉子的装饰器

    Args:
        priority: 优先级 (默认 50)。启动时优先级越大的，关闭时优先级也应设为越大，它会越晚被清理
        abort_on_exception: 报错时是否抛出异常 (默认 False。关闭通常不应因局部报错而中断全局清理)
        timeout: 钉子执行超时（秒），None 表示不限制 (默认 None)

    Returns:
        挂载的装饰器函数
    """
    ...


def on_shutdown(
        func: HookFunc | None = None,
        *,
        priority: int = 50,
        abort_on_exception: bool = False,
        timeout: int | float | None = None
) -> Callable[[HookFunc], HookFunc] | HookFunc:
    """注册服务关闭(Shutdown)生命周期钉子的装饰器

    允许您将应用关闭时的清理逻辑（如释放连接池、刷新日志等）分散到具体的业务模块中
    在 FastAPI 实例关闭之前，会统一收集并按 `priority` 升序执行所有挂载了该装饰器的函数
    （与启动时的顺序刚好相反，优先清理后初始化的资源）

    Args:
        func: 挂载此装饰器的异步函数
        priority: 优先级 (默认 50)。启动时优先级越大的，关闭时优先级也应设为越大，它会越晚被清理
        abort_on_exception: 报错时是否抛出异常 (默认 False。关闭通常不应因局部报错而中断全局清理)
        timeout: 钉子执行超时（秒），None 表示不限制 (默认 None)

    Examples:
        @on_shutdown
        async def close_db():
            await engine.dispose()
    """

    def decorator(fn: HookFunc) -> HookFunc:
        """内部装饰器函数

        Args:
            fn: 被装饰的钉子函数

        Returns:
            原封不动返回被装饰的函数
        """
        default_registry.register_shutdown(fn, priority, abort_on_exception, timeout)
        return fn

    return decorator(func) if func else decorator


def clear_hooks() -> None:
    """清空默认全局注册表中的所有钉子（用于测试隔离）"""
    default_registry.clear()
