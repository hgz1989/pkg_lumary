"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 
"""
from contextlib import asynccontextmanager
from dataclasses import dataclass
from inspect import signature
from logging import getLogger
from typing import (
    runtime_checkable,
    Protocol,
    List,
    AsyncGenerator,
    overload,
    Callable
)

from fastapi import FastAPI

logger = getLogger(__name__)


# ===============================
# 类型协议
# ===============================
@runtime_checkable
class _NoArgHook(Protocol):
    async def __call__(self) -> None: ...


@runtime_checkable
class _AppArgHook(Protocol):
    async def __call__(self, app: FastAPI) -> None: ...


HookFunc = _NoArgHook | _AppArgHook


# ===============================
# 钩子条目（增加 abort_on_exception）
# ===============================
@dataclass(frozen=True)
class _HookItem:
    func: HookFunc
    priority: int
    abort_on_exception: bool  # 新增：出错是否终止项目

    def __eq__(self, other: object) -> bool:
        """重写等于判断逻辑，用于去重

        防止同一个初始化函数被重复注册到列表中。
        比较依据为函数的内存地址及其名称。

        Args:
            other: 需要比较的另一个对象

        Returns:
            若两个钩子内部包装的是同一个函数，则返回 True
        """
        if not isinstance(other, _HookItem):
            return False

        return (
                self.func.__name__ == other.func.__name__
                and id(self.func) == id(other.func)
        )


# ===============================
# 全局注册表
# ===============================
_startup_hooks: List[_HookItem] = []
_shutdown_hooks: List[_HookItem] = []


# ===============================
# 注册函数
# ===============================
def _register_startup(
        func: HookFunc,
        priority: int,
        abort_on_exception: bool
) -> None:
    """将启动钩子注册到全局列表中

    按优先级从大到小降序排列，priority 值越大的函数越先执行。

    Args:
        func: 待执行的异步函数
        priority: 执行优先级
        abort_on_exception: 异常时是否抛出 RuntimeError 终止启动
    """
    item = _HookItem(func, priority, abort_on_exception)
    if item not in _startup_hooks:
        _startup_hooks.append(item)
        _startup_hooks.sort(key=lambda x: -x.priority)


def _register_shutdown(
        func: HookFunc,
        priority: int,
        abort_on_exception: bool
) -> None:
    """将关闭钩子注册到全局列表中

    按优先级从小到大升序排列，以便进行反向清理。

    Args:
        func: 待执行的异步函数
        priority: 执行优先级
        abort_on_exception: 异常时是否抛出 RuntimeError
    """
    item = _HookItem(func, priority, abort_on_exception)
    if item not in _shutdown_hooks:
        _shutdown_hooks.append(item)
        _shutdown_hooks.sort(key=lambda x: x.priority)


# ===============================
# 执行钩子
# ===============================
async def _run_hooks(hooks: List[_HookItem], app: FastAPI) -> None:
    """按序执行给定的生命周期钩子列表

    自动识别钩子函数的签名，若包含一个参数则注入 FastAPI 应用实例；
    否则无参调用。

    Args:
        hooks: 包含 _HookItem 的列表
        app: 当前 FastAPI 应用实例

    Raises:
        RuntimeError: 当 abort_on_exception=True 且执行发生异常时抛出
    """
    for item in hooks:
        try:
            sig = signature(item.func)
            if len(sig.parameters) == 1:
                await item.func(app)
            else:
                await item.func()
        except Exception as e:
            name = item.func.__name__
            logger.error(f'❌ [生命周期钩子执行失败] {name}: {str(e)}')

            if item.abort_on_exception:
                raise RuntimeError(f'❌ [启动/关闭终止：钩子 {name} 异常]') from e


# ===============================
# FastAPI 生命周期
# ===============================
@asynccontextmanager
async def fastapi_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI 应用的生命周期管理函数

    用于处理应用启动前（startup）和关闭后（shutdown）的逻辑，
    例如：数据库连接池的建立与释放、全局资源的初始化与清理等。

    如果 FullAPI 实例提供了 user_lifespan，会将其嵌套在框架钩子内部执行，
    确保框架级的 startup/shutdown 钩子始终优先运行。

    执行顺序：
        startup: 框架钩子 → user_lifespan startup → yield
        shutdown: user_lifespan shutdown → 框架钩子

    Args:
        app: FastAPI 应用实例

    Returns:
        异步迭代器
    """
    _startup_hooks_count = len(_startup_hooks)
    if _startup_hooks_count > 0:
        logger.info(f'Executing {_startup_hooks_count} startup hooks...')
        await _run_hooks(_startup_hooks, app)
        logger.info('Startup hooks executed successfully.')

    yield

    _shutdown_hooks_count = len(_shutdown_hooks)
    if _shutdown_hooks_count > 0:
        logger.info(f'Executing {_shutdown_hooks_count} shutdown hooks...')
        await _run_hooks(_shutdown_hooks, app)
        logger.info('Shutdown hooks executed successfully.')


# ===============================
# 装饰器（支持 priority + abort_on_exception）
# ===============================
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
def on_startup(
        *,
        priority: int = 50,
        abort_on_exception: bool = True
) -> Callable[[HookFunc], HookFunc]:
    """注册服务启动(Startup)生命周期钩子的装饰器

    允许您将应用启动时的初始化逻辑（如数据库连接、数据预热等）分散到具体的业务模块中。
    在 FastAPI 实例启动之前，会统一收集并按 `priority` 降序执行所有挂载了该装饰器的函数。

    Args:
        priority: 优先级 (默认 50)。值越大，越早被执行。
        abort_on_exception: 如果执行报错是否抛出异常阻止启动 (默认 True)。

    Returns:
        挂载的装饰器函数
    """
    ...


def on_startup(
        func: HookFunc | None = None,
        *,
        priority: int = 50,
        abort_on_exception: bool = True
):
    """注册服务启动(Startup)生命周期钩子的装饰器

    允许您将应用启动时的初始化逻辑（如数据库连接、数据预热等）分散到具体的业务模块中。
    在 FastAPI 实例启动之前，会统一收集并按 `priority` 降序执行所有挂载了该装饰器的函数。

    Args:
        func: 挂载此装饰器的异步函数
        priority: 优先级 (默认 50)。值越大，越早被执行。
        abort_on_exception: 如果执行报错是否抛出异常阻止启动 (默认 True)。

    Examples:
        @on_startup(priority=100)
        async def connect_db():
            await init_db()

        @on_startup
        async def load_cache(app: FastAPI):
            app.state.cache = ...
    """

    def decorator(fn: HookFunc) -> HookFunc:
        """将启动钩子注册到全局列表中

        按优先级从大到小降序排列，priority 值越大的函数越先执行。

        Args:
            fn: 挂载此装饰器的异步函数
        """
        _register_startup(fn, priority, abort_on_exception)
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
def on_shutdown(
        *,
        priority: int = 50,
        abort_on_exception: bool = False
) -> Callable[[HookFunc], HookFunc]:
    """注册服务关闭(Shutdown)生命周期钩子的装饰器

    Args:
        priority: 优先级 (默认 50)。启动时优先级越大的，关闭时优先级也应设为越大，它会越晚被清理。
        abort_on_exception: 报错时是否抛出异常 (默认 False。关闭通常不应因局部报错而中断全局清理)。

    Returns:
        挂载的装饰器函数
    """
    ...


def on_shutdown(
        func: HookFunc | None = None,
        *,
        priority: int = 50,
        abort_on_exception: bool = False
):
    """注册服务关闭(Shutdown)生命周期钩子的装饰器

    允许您将应用关闭时的清理逻辑（如释放连接池、刷新日志等）分散到具体的业务模块中。
    在 FastAPI 实例关闭之前，会统一收集并按 `priority` 升序执行所有挂载了该装饰器的函数。
    （与启动时的顺序刚好相反，优先清理后初始化的资源）

    Args:
        func: 挂载此装饰器的异步函数
        priority: 优先级 (默认 50)。启动时优先级越大的，关闭时优先级也应设为越大，它会越晚被清理。
        abort_on_exception: 报错时是否抛出异常 (默认 False。关闭通常不应因局部报错而中断全局清理)。

    Examples:
        @on_shutdown
        async def close_db():
            await engine.dispose()
    """

    def decorator(fn: HookFunc) -> HookFunc:
        """将关闭钩子注册到全局列表中

        按优先级从小到大升序排列，priority 值越小的函数越先执行。

        Args:
            fn: 挂载此装饰器的异步函数

        Returns:
            挂载的装饰器函数
        """
        _register_shutdown(fn, priority, abort_on_exception)
        return fn

    return decorator(func) if func else decorator
