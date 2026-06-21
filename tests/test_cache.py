"""
@Author     : zarkhan
@CreateDate : 2026/6/17
@Description: 缓存模块无 Redis 降级测试
"""
import pytest
from fastapi import Request

from lumary.common.cache import cache, cache_response


@pytest.mark.asyncio
async def test_cache_manager_fallback():
    """测试未初始化 cache 时的方法调用不会报错"""
    # 强制标记为未启用
    cache.enabled = False
    
    # 全部调用一遍，如果报错则测试不通过
    assert await cache.get("key") is None
    await cache.set("key", "val")
    await cache.delete("key")
    await cache.clear_namespace("test_ns")


@pytest.mark.asyncio
async def test_cache_response_decorator_fallback():
    """测试未启用缓存时，装饰器依然能正常返回函数结果"""
    cache.enabled = False

    @cache_response("test_ns")
    async def dummy_endpoint(request: Request, name: str):
        return {"hello": name}

    # Mock request
    class MockURL:
        path = "/api/test"
        query = "page=1"
        
    class MockRequest:
        method = "GET"
        url = MockURL()

    req = MockRequest()
    # Type ignore to bypass Request mock validation
    res = await dummy_endpoint(req, "lumary") # type: ignore
    
    assert res == {"hello": "lumary"}
