"""
@Author     : zarkhan
@CreateDate : 2026/6/21
@Description: Cache模块测试（包含平滑降级）
"""
import importlib
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

# 导入真实模块
import lumary.common.cache as cache_module
from lumary.common.cache import CacheManager, cache_response


@pytest.fixture
def mock_missing_redis():
    """模拟未安装redis库的环境"""
    import sys
    cache_module = sys.modules['lumary.common.cache']
    orig_redis_installed = cache_module.REDIS_INSTALLED
    
    # 强制修改状态为未安装
    cache_module.REDIS_INSTALLED = False
    
    yield
    
    # 恢复状态
    cache_module.REDIS_INSTALLED = orig_redis_installed


@pytest.mark.asyncio
async def test_cache_manager_missing_dependency_fallback(mock_missing_redis):
    """测试未安装redis时，缓存管理器平滑降级（静默空跑）"""
    manager = CacheManager()
    
    # 未安装时init应该抛出RuntimeError
    with pytest.raises(RuntimeError, match='未安装redis依赖'):
        await manager.init('redis://localhost:6379/0')
        
    # 其他方法应该静默失效，不抛出异常
    assert manager.enabled is False
    assert await manager.get('test_key') is None
    
    # set和delete和clear_namespace不应该抛异常
    await manager.set('test_key', 'test_value')
    await manager.delete('test_key')
    await manager.clear_namespace('test_ns')


@pytest.mark.asyncio
async def test_cache_response_decorator_missing_dependency(mock_missing_redis):
    """测试未安装redis时，装饰器不阻断原函数执行"""
    
    # 为了测试装饰器，我们需要一个假的缓存管理器状态
    # 装饰器使用的是全局单例 `cache`，在fixture中它的REDIS_INSTALLED虽然被改了
    # 但是enabled默认也是False
    
    @cache_response('test_namespace', expire=60)
    async def dummy_func(x: int):
        return {'result': x * 2}
        
    # 即使在未开启缓存（或未安装）的情况下，也必须正常返回原函数结果
    res = await dummy_func(10)
    assert res == {'result': 20}
