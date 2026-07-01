"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 通用工具包，提供缓存、上下文、异常处理、日志记录等核心能力。
"""
from importlib.util import find_spec

__all__ = []

if find_spec('aiocache') is not None:
    from .cache import CacheManager, cache, cache_response, FileCache

    __all__.extend(['CacheManager', 'cache', 'cache_response', 'FileCache'])

if find_spec('paho') is not None:
    from .mqtt import topic_matches, MQTTManager, mqtt_client

    __all__.extend(['topic_matches', 'MQTTManager', 'mqtt_client'])
