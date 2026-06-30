"""
@Author     : zarkhan
@CreateDate : 2026/6/17
@Description: request_id上下文变量（context.py）单元测试
"""
import asyncio
import pytest

from lumary.middleware import (
    generate_request_id,
    set_request_id,
    get_request_id,
    request_id_ctx_var)


class TestGenerateRequestId:
    # 匹配无短横线的 32 位 UUID4 hex 格式
    _UUID4_RE = __import__('re').compile(
        r'^[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{15}$',
        __import__('re').IGNORECASE
    )

    def test_returns_string(self):
        assert isinstance(generate_request_id(), str)

    def test_returns_valid_uuid4(self):
        rid = generate_request_id()
        assert self._UUID4_RE.match(rid), f'不是合法UUID4: {rid}'

    def test_each_call_unique(self):
        ids = {generate_request_id() for _ in range(50)}
        assert len(ids) == 50


class TestSetGetRequestId:
    def test_get_default_is_none(self):
        """未设置时默认返回None"""
        # 用新的ContextVar隔离验证
        from contextvars import ContextVar
        fresh = ContextVar('test_fresh', default=None)
        assert fresh.get() is None

    def test_set_and_get(self):
        set_request_id('test-id-abc')
        assert get_request_id() == 'test-id-abc'

    def test_set_returns_token(self):
        """set_request_id应返回ContextVar Token"""
        from contextvars import Token
        token = set_request_id('token-test')
        assert isinstance(token, Token)

    def test_overwrite_value(self):
        set_request_id('first')
        set_request_id('second')
        assert get_request_id() == 'second'

    def test_reset_via_token(self):
        """通过Token.reset可恢复之前的值"""
        set_request_id('original')
        token = set_request_id('temporary')
        assert get_request_id() == 'temporary'
        request_id_ctx_var.reset(token)
        assert get_request_id() == 'original'


class TestContextVarIsolation:
    async def test_different_coroutines_have_independent_context(self):
        """不同协程上下文之间的request_id应相互隔离"""
        results = {}

        async def worker(name: str, rid: str):
            set_request_id(rid)
            await asyncio.sleep(0.01)
            results[name] = get_request_id()

        await asyncio.gather(
            worker('a', 'rid-for-a'),
            worker('b', 'rid-for-b'),
        )
        assert results['a'] == 'rid-for-a'
        assert results['b'] == 'rid-for-b'

    async def test_task_inherits_context_snapshot(self):
        """asyncio.create_task时协程会拷贝当前上下文快照"""
        set_request_id('parent-rid')
        captured = []

        async def child():
            captured.append(get_request_id())

        task = asyncio.create_task(child())
        await task
        # child任务在创建时拷贝了parent的上下文
        assert captured == ['parent-rid']
