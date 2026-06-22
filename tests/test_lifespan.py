"""
@Author     : zarkhan
@CreateDate : 2026/6/17
@Description: HookRegistry生命周期钩子单元测试
"""
import asyncio
import pytest

from fastapi import FastAPI
from lumary.lifespan import HookRegistry


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────
@pytest.fixture
def registry():
    """每个测试用独立的HookRegistry实例，避免状态污染"""
    return HookRegistry()


@pytest.fixture
def dummy_app():
    return FastAPI()


# ──────────────────────────────────────────────
# 注册行为
# ──────────────────────────────────────────────
class TestHookRegistration:
    def test_register_startup(self, registry):
        async def my_hook():
            pass
        registry.register_startup(my_hook, priority=50, abort_on_exception=True)
        assert len(registry._startup_hooks) == 1

    def test_register_shutdown(self, registry):
        async def my_hook():
            pass
        registry.register_shutdown(my_hook, priority=50, abort_on_exception=True)
        assert len(registry._shutdown_hooks) == 1

    def test_duplicate_startup_not_added(self, registry):
        """相同函数不应重复注册"""
        async def my_hook():
            pass
        registry.register_startup(my_hook, priority=50, abort_on_exception=True)
        registry.register_startup(my_hook, priority=50, abort_on_exception=True)
        assert len(registry._startup_hooks) == 1

    def test_startup_priority_order(self, registry):
        """启动钉子按优先级从大到小排序"""
        async def hook_low():
            pass
        async def hook_high():
            pass
        registry.register_startup(hook_low, priority=10, abort_on_exception=False)
        registry.register_startup(hook_high, priority=100, abort_on_exception=False)
        names = [h.func.__name__ for h in registry._startup_hooks]
        assert names == ['hook_high', 'hook_low']

    def test_shutdown_priority_order(self, registry):
        """关闭钉子按优先级从小到大排序"""
        async def hook_low():
            pass
        async def hook_high():
            pass
        registry.register_shutdown(hook_low, priority=10, abort_on_exception=False)
        registry.register_shutdown(hook_high, priority=100, abort_on_exception=False)
        names = [h.func.__name__ for h in registry._shutdown_hooks]
        assert names == ['hook_low', 'hook_high']

    def test_clear(self, registry):
        async def h():
            pass
        registry.register_startup(h, priority=1, abort_on_exception=False)
        registry.register_shutdown(h, priority=1, abort_on_exception=False)
        registry.clear()
        assert len(registry._startup_hooks) == 0
        assert len(registry._shutdown_hooks) == 0


# ──────────────────────────────────────────────
# 装饰器API
# ──────────────────────────────────────────────
class TestDecoratorAPI:
    def test_on_startup_decorator_no_args(self, registry):
        @registry.on_startup
        async def my_hook():
            pass
        assert len(registry._startup_hooks) == 1

    def test_on_startup_decorator_with_args(self, registry):
        @registry.on_startup(priority=99)
        async def my_hook():
            pass
        assert registry._startup_hooks[0].priority == 99

    def test_on_shutdown_decorator_no_args(self, registry):
        @registry.on_shutdown
        async def my_hook():
            pass
        assert len(registry._shutdown_hooks) == 1

    def test_on_shutdown_decorator_with_args(self, registry):
        @registry.on_shutdown(priority=1, abort_on_exception=False)
        async def my_hook():
            pass
        item = registry._shutdown_hooks[0]
        assert item.priority == 1
        assert item.abort_on_exception is False


# ──────────────────────────────────────────────
# 执行行为
# ──────────────────────────────────────────────
class TestHookExecution:
    async def test_run_startup_calls_hook(self, registry, dummy_app):
        results = []

        async def hook(app):
            results.append('startup')

        registry.register_startup(hook, priority=50, abort_on_exception=True)
        await registry.run_startup(dummy_app)
        assert results == ['startup']

    async def test_run_shutdown_calls_hook(self, registry, dummy_app):
        results = []

        async def hook(app):
            results.append('shutdown')

        registry.register_shutdown(hook, priority=50, abort_on_exception=True)
        await registry.run_shutdown(dummy_app)
        assert results == ['shutdown']

    async def test_hook_with_app_arg(self, registry, dummy_app):
        """接收app参数的钩子能收到FastAPI实例"""
        received = []

        async def hook_with_app(app: FastAPI):
            received.append(app)

        registry.register_startup(hook_with_app, priority=50, abort_on_exception=True)
        await registry.run_startup(dummy_app)
        assert received == [dummy_app]

    async def test_abort_on_exception_raises(self, registry, dummy_app):
        async def bad_hook(app):
            raise ValueError('oops')

        registry.register_startup(bad_hook, priority=50, abort_on_exception=True)
        with pytest.raises(RuntimeError, match='启动/关闭终止'):
            await registry.run_startup(dummy_app)

    async def test_no_abort_continues(self, registry, dummy_app):
        """abort_on_exception=False时异常不阻止后续钩子"""
        results = []

        async def bad_hook(app):
            raise ValueError('non-fatal error')

        async def good_hook(app):
            results.append('done')

        registry.register_startup(bad_hook, priority=100, abort_on_exception=False)
        registry.register_startup(good_hook, priority=1, abort_on_exception=False)
        await registry.run_startup(dummy_app)
        assert results == ['done']

    async def test_timeout_raises_when_abort(self, registry, dummy_app):
        async def slow_hook(app):
            await asyncio.sleep(10)

        registry.register_startup(slow_hook, priority=50, abort_on_exception=True, timeout=0.05)
        with pytest.raises(RuntimeError):
            await registry.run_startup(dummy_app)

    async def test_timeout_continues_when_no_abort(self, registry, dummy_app):
        """超时但abort_on_exception=False时，应继续执行后续钩子"""
        results = []

        async def slow_hook(app):
            await asyncio.sleep(10)

        async def after_slow(app):
            results.append('ok')

        registry.register_startup(slow_hook, priority=100, abort_on_exception=False, timeout=0.05)
        registry.register_startup(after_slow, priority=1, abort_on_exception=False)
        await registry.run_startup(dummy_app)
        assert results == ['ok']

    async def test_execution_order_by_priority(self, registry, dummy_app):
        """验证多个启动钩子按优先级顺序执行"""
        order = []

        async def low(app):
            order.append('low')

        async def high(app):
            order.append('high')

        async def mid(app):
            order.append('mid')

        registry.register_startup(low, priority=10, abort_on_exception=False)
        registry.register_startup(high, priority=100, abort_on_exception=False)
        registry.register_startup(mid, priority=50, abort_on_exception=False)
        await registry.run_startup(dummy_app)
        assert order == ['high', 'mid', 'low']


# ──────────────────────────────────────────────
# list_startup_hooks / list_shutdown_hooks
# ──────────────────────────────────────────────
class TestListHooks:
    def test_list_startup_hooks_format(self, registry):
        @registry.on_startup(priority=42, abort_on_exception=False)
        async def my_hook():
            pass

        info = registry.list_startup_hooks()
        assert len(info) == 1
        assert 'my_hook' in info[0]
        assert 'priority=42' in info[0]

    def test_list_empty_hooks(self, registry):
        assert registry.list_startup_hooks() == []
        assert registry.list_shutdown_hooks() == []
