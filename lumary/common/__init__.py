"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 通用工具包，提供缓存、上下文、异常处理、日志记录等核心能力。
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
    'request_id_ctx_var',
    'generate_request_id',
    'set_request_id',
    'get_request_id',
    'set_log_level',
    'set_log_format',
    'setup_logger',
    'CacheManager',
    'cache',
    'cache_response',
    'CrossProcessFileCache'
]

if find_spec('aiocache') is not None:
    from .cache import CacheManager, cache, cache_response, CrossProcessFileCache

if find_spec('paho') is not None:
    from .mqtt import topic_matches, MQTTManager, mqtt_client

    __all__.append('topic_matches')
    __all__.append('MQTTManager')
    __all__.append('mqtt_client')
