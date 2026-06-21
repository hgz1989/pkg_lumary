"""
@Author     : zarkhan
@CreateDate : 2026/6/17
@Description: 可选的 Redis 缓存管理器与缓存装饰器
"""
import hashlib
from functools import wraps
from logging import getLogger
from typing import Any, Callable

from fastapi import Request
from pydantic import BaseModel
import redis.asyncio as aioredis
from redis.asyncio import Redis

from lumary.common.utils.strings import json_loads, json_dumps

_logger = getLogger(__name__)


class CacheManager:
    """Redis 缓存管理器

    如果未安装 redis 库或未初始化，则默认所有操作静默失效（不抛异常），
    保证业务在无缓存状态下也能正常运行。
    """
    __slots__ = ('redis', 'enabled')

    def __init__(self):
        """初始化"""
        self.redis: Redis | None = None
        self.enabled: bool = False

    async def init(self, url: str) -> None:
        """初始化 Redis 连接池

        Args:
            url: Redis 连接 URL (如 redis://localhost:6379/0)
        """
        self.redis = aioredis.from_url(url, decode_responses=True)
        self.enabled = True
        _logger.info('Redis 缓存连接成功')

    async def close(self) -> None:
        """关闭 Redis 连接"""
        if self.redis:
            await self.redis.close()
            self.enabled = False
            _logger.info('Redis 缓存已断开')

    async def get(self, key: str) -> Any:
        """获取缓存

        Args:
            key: 缓存键

        Returns:
            解析后的缓存数据，不存在或未开启时返回 None
        """
        redis_client = self.redis
        if not self.enabled or not redis_client:
            return None
        try:
            val = await redis_client.get(key)
            return json_loads(val) if val else None
        except Exception as e:
            _logger.error(f'Redis get 错误: {e}')
            return None

    async def set(self, key: str, value: Any, expire: int = 3600) -> None:
        """设置缓存

        Args:
            key: 缓存键
            value: 缓存数据（需可被 json 序列化）
            expire: 过期时间（秒）
        """
        redis_client = self.redis
        if not self.enabled or not redis_client:
            return
        try:
            await redis_client.set(key, json_dumps(value), ex=expire)
        except Exception as e:
            _logger.error(f'Redis set 错误: {e}')

    async def delete(self, key: str) -> None:
        """删除单个缓存

        Args:
            key: 缓存键
        """
        redis_client = self.redis
        if not self.enabled or not redis_client:
            return
        try:
            await redis_client.delete(key)
        except Exception as e:
            _logger.error(f'Redis delete 错误: {e}')

    async def clear_namespace(self, namespace: str) -> None:
        """清理特定命名空间下的所有缓存（如某个表的所有查询缓存）

        使用 SCAN 迭代匹配清理，避免阻塞 Redis 主线程

        Args:
            namespace: 命名空间前缀
        """
        redis_client = self.redis
        if not self.enabled or not redis_client:
            return
        try:
            cursor = 0
            match_pattern = f'{namespace}:*'
            while True:
                cursor, keys = await redis_client.scan(cursor=cursor, match=match_pattern, count=100)
                if keys:
                    await redis_client.delete(*keys)
                if cursor == 0:
                    break
        except Exception as e:
            _logger.error(f'Redis scan/delete 错误: {e}')


# 全局单例
cache = CacheManager()


def cache_response(namespace: str, expire: int = 3600) -> Callable:
    """API 响应缓存装饰器

    自动根据请求路径和参数生成缓存 Key，并将函数的返回结果缓存。
    当 CRUDBase 发生数据变动时，可通过 namespace 批量使其失效。

    Args:
        namespace: 缓存命名空间（建议与模型 tablename 保持一致）
        expire: 过期时间（秒）

    Returns:
        装饰器
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not cache.enabled:
                return await func(*args, **kwargs)

            # 尝试从参数中提取 Request 对象以构建精确的缓存 Key
            request: Request | None = kwargs.get('request')
            if not request:
                for arg in args:
                    if hasattr(arg, 'url') and hasattr(arg, 'method'):
                        request = arg
                        break

            if request:
                raw_key = f'{request.method}:{request.url.path}?{request.url.query}'
                key_hash = hashlib.md5(raw_key.encode('utf-8')).hexdigest()
                cache_key = f'{namespace}:{key_hash}'
            else:
                cache_key = f'{namespace}:{func.__name__}'

            # 尝试命中缓存
            cached_data = await cache.get(cache_key)
            if cached_data is not None:
                return cached_data

            # 未命中则执行原函数
            response = await func(*args, **kwargs)

            # 解析数据用于缓存（支持 Pydantic BaseModel）
            to_cache = response
            if hasattr(response, 'model_dump'):
                to_cache = response.model_dump(mode='json')
            elif isinstance(response, BaseModel):
                to_cache = response.model_dump(mode='json')

            # 仅当可序列化时才进行缓存写入
            if isinstance(to_cache, (dict, list, str, int, float, bool)):
                await cache.set(cache_key, to_cache, expire)

            return response

        return wrapper

    return decorator
