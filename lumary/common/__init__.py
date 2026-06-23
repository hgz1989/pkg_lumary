"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: Lumary模块
"""
from importlib.util import find_spec

from .context import (
    request_id_ctx_var,
    generate_request_id,
    set_request_id,
    get_request_id
)
from .logger import set_log_level, set_log_format, setup_logger

__all__ = [
    # 上下文变量
    'request_id_ctx_var',
    'generate_request_id',
    'set_request_id',
    'get_request_id',
    # 日志控制
    'set_log_level',
    'set_log_format',
    'setup_logger',
    # Cache
    'CacheManager',
    'cache',
    'cache_response'
]

if find_spec('aiocache') is not None:
    from .cache import CacheManager, cache, cache_response

    __all__.append('CacheManager')
    __all__.append('cache')
    __all__.append('cache_response')

if find_spec('paho') is not None:
    from .mqtt import topic_matches, MQTTManager, mqtt_client

    __all__.append('topic_matches')
    __all__.append('MQTTManager')
    __all__.append('mqtt_client')
