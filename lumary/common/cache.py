"""
@Author     : zarkhan
@CreateDate : 2026/6/17
@Description: 可选的aiocache缓存管理器与缓存装饰器
"""
import hashlib
import re
from functools import wraps
from logging import getLogger
from typing import Any, Callable

from fastapi import Request
from pydantic import BaseModel

try:
    from aiocache import Cache

    AIOCACHE_INSTALLED = True
except ImportError:
    AIOCACHE_INSTALLED = False


    class Cache:  # type: ignore
        """aiocache降级桩类，解决Pylance对Any | None的类型收窄警告"""
        MEMORY = 1
        REDIS = 2
        MEMCACHED = 3

        def __init__(self, **kwargs: Any) -> None: ...

        async def close(self) -> None: ...

        async def get(self, key: str, default: Any = None) -> Any: ...

        async def set(self, key: str, value: Any, ttl: Any = None) -> Any: ...

        async def delete(self, key: str) -> Any: ...

        async def clear(self, namespace: str | None = None) -> Any: ...

        async def raw(self, command: str, *args: Any, **kwargs: Any) -> Any: ...

_logger = getLogger(__name__)


class CacheManager:
    """基于aiocache的缓存管理器

    支持内存、Redis等多种后端
    如果未安装aiocache库或未初始化，则默认所有操作静默失效（不抛异常），
    保证业务在无缓存状态下也能正常运行
    """
    __slots__ = ('cache', 'enabled', 'cache_class')

    def __init__(self):
        """初始化"""
        self.cache: Cache | None = None
        self.enabled: bool = False
        self.cache_class: int = Cache.MEMORY

    async def init(self, url: str | None = None) -> None:
        """初始化缓存

        Args:
            url: 可选的连接URL。
                 Redis示例: redis://localhost:6379/0
                 Memcached示例: memcached://localhost:11211
                 若不提供，则默认使用内存缓存。
            
        Raises:
            RuntimeError: 如果未安装aiocache依赖时抛出
        """
        if not AIOCACHE_INSTALLED:
            raise RuntimeError(
                '未安装aiocache依赖，无法启动缓存！请使用pip install lumary[cache] 或 pip install aiocache 安装')

        if url and url.startswith('redis://'):
            self.cache_class = Cache.REDIS
            # 解析Redis URL
            match = re.match(r'redis://([^:]+):?(\d+)?/?(\d+)?', url)
            if match:
                endpoint = match.group(1)
                port = int(match.group(2)) if match.group(2) else 6379
                db = int(match.group(3)) if match.group(3) else 0
                self.cache = Cache(self.cache_class, endpoint=endpoint, port=port, db=db, namespace='main')
            else:
                self.cache = Cache(self.cache_class, endpoint='127.0.0.1', port=6379, db=0, namespace='main')
            _logger.info('Redis缓存连接成功 (aiocache)')
        elif url and url.startswith('memcached://'):
            self.cache_class = Cache.MEMCACHED
            # 解析Memcached URL
            match = re.match(r'memcached://([^:]+):?(\d+)?', url)
            if match:
                endpoint = match.group(1)
                port = int(match.group(2)) if match.group(2) else 11211
                self.cache = Cache(self.cache_class, endpoint=endpoint, port=port, namespace='main')
            else:
                self.cache = Cache(self.cache_class, endpoint='127.0.0.1', port=11211, namespace='main')
            _logger.info('Memcached缓存连接成功 (aiocache)')
        else:
            # 默认内存缓存
            self.cache = Cache(self.cache_class, namespace='main')
            _logger.info('纯内存缓存初始化成功 (aiocache)')

        self.enabled = True

    async def close(self) -> None:
        """关闭缓存连接"""
        cache_client = self.cache
        if cache_client is not None:
            await cache_client.close()
            self.enabled = False
            _logger.info('缓存已断开')

    async def get(self, key: str) -> Any:
        """获取缓存

        Args:
            key: 缓存键

        Returns:
            解析后的缓存数据，不存在或未开启时返回None
        """
        cache_client = self.cache

        if not self.enabled or cache_client is None:
            return None

        try:
            return await cache_client.get(key)
        except Exception as e:
            _logger.error(f'缓存 get错误: {e}')
            return None

    async def set(self, key: str, value: Any, expire: int = 3600) -> None:
        """设置缓存

        Args:
            key: 缓存键
            value: 缓存数据（需可被json序列化）
            expire: 过期时间（秒）
        """
        cache_client = self.cache

        if not self.enabled or cache_client is None:
            return

        try:
            await cache_client.set(key, value, ttl=expire)
        except Exception as e:
            _logger.error(f'缓存 set错误: {e}')

    async def delete(self, key: str) -> None:
        """删除单个缓存

        Args:
            key: 缓存键
        """
        cache_client = self.cache

        if not self.enabled or cache_client is None:
            return

        try:
            await cache_client.delete(key)
        except Exception as e:
            _logger.error(f'缓存 delete错误: {e}')

    async def clear_namespace(self, namespace: str) -> None:
        """清理特定命名空间下的所有缓存（如某个表的所有查询缓存）

        Args:
            namespace: 命名空间前缀
        """
        cache_client = self.cache

        if not self.enabled or cache_client is None:
            return

        try:
            # 内存模式不支持通过SCAN或keys批量删除前缀，这里通过底层遍历或者清理所有实现兜底
            # 如果是Redis，可以通过raw命令执行SCAN和DEL
            if self.cache_class == Cache.REDIS:
                cursor = 0
                match_pattern = f'main:{namespace}:*'
                while True:
                    result = await cache_client.raw('scan', cursor, match=match_pattern, count=100)
                    cursor = int(result[0])
                    keys = result[1]

                    if keys:
                        # raw DEL 需要去掉外层的 aiocache 自动加的命名空间前缀？其实不需要，因为 raw 直接操作底层 Redis
                        await cache_client.raw('del', *keys)

                    if cursor == 0:
                        break
            elif hasattr(cache_client, '_cache'):
                # MemoryCache没有原生的前缀删除，遍历内部字典删除
                keys_to_delete = [k for k in getattr(cache_client, '_cache').keys() if k.startswith(namespace + ':')]
                for k in keys_to_delete:
                    await cache_client.delete(k)
        except Exception as e:
            _logger.error(f'缓存 clear_namespace错误: {e}')


# 全局单例
cache = CacheManager()


def cache_response(namespace: str, expire: int = 3600) -> Callable:
    """API响应缓存装饰器

    自动根据请求路径和参数生成缓存Key，并将函数的返回结果缓存
    当CRUDBase发生数据变动时，可通过namespace批量使其失效

    Args:
        namespace: 缓存命名空间（建议与模型tablename保持一致）
        expire: 过期时间（秒）

    Returns:
        装饰器
    """

    def decorator(func: Callable) -> Callable:
        """内层装饰器，接收原始接口处理函数"""

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            """异步接口缓存执行包装器

            执行流程：
            1. 判断全局缓存开关，未启用直接放行原函数
            2. 自动从args/kwargs提取Request对象
            3. 根据请求方法+路径+查询参数生成哈希缓存key；无Request则使用函数名兜底
            4. 读取缓存，命中直接返回缓存数据
            5. 未命中执行原始接口，将返回值序列化为可缓存格式写入缓存
            6. 返回原始接口完整响应对象

            Args:
                *args: 接口位置参数，自动遍历匹配Request实例
                **kwargs: 接口关键字参数，优先读取request入参

            Returns:
                Any: 原接口返回的完整响应对象（Pydantic模型/字典/列表等）
            """
            if not cache.enabled:
                return await func(*args, **kwargs)

            # 尝试从参数中提取Request对象以构建精确的缓存Key
            request: Request | None = kwargs.get('request')

            if not request:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
                    # 作为降级兜底，判断鸭子类型
                    if hasattr(arg, 'url') and hasattr(arg, 'method'):
                        request = arg  # type: ignore
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
                _logger.debug(f'缓存命中: {cache_key}')
                return cached_data

            # 未命中则执行原函数
            response = await func(*args, **kwargs)

            # 解析数据用于缓存（支持Pydantic BaseModel）
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
