"""
@Author     : zarkhan
@CreateDate : 2026/6/13
@Description: 字符串与序列化工具
"""
import json
import random
import string
from typing import Any

# 尝试导入orjson以获得极致性能
try:
    import orjson

    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False
    orjson = None


def camel_to_snake(s: str) -> str:
    """驼峰转下划线

    Args:
        s: 驼峰字符串 (例如: 'CamelCase' 或 'camelCase')

    Returns:
        下划线字符串 (例如: 'camel_case')
    """
    return ''.join(['_' + c.lower() if c.isupper() else c for c in s]).lstrip('_')


def snake_to_camel(s: str) -> str:
    """下划线转驼峰

    Args:
        s: 下划线字符串 (例如: 'snake_case')

    Returns:
        驼峰字符串 (例如: 'SnakeCase')
    """
    components = s.split('_')
    return ''.join(x.title() for x in components)


def random_string(length: int = 16) -> str:
    """生成指定长度的随机字符串（包含大小写字母和数字）

    Args:
        length: 字符串长度

    Returns:
        随机字符串
    """
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))


def json_dumps(obj: Any) -> str:
    """高性能JSON序列化

    如果环境安装了orjson，则使用orjson加速序列化；否则回退到标准库json

    Args:
        obj: 要序列化的对象

    Returns:
        JSON字符串
    """
    if HAS_ORJSON:
        return orjson.dumps(obj).decode('utf-8')
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))


def json_loads(s: str | bytes) -> Any:
    """高性能JSON反序列化

    如果环境安装了orjson，则使用orjson加速反序列化；否则回退到标准库json

    Args:
        s: JSON字符串或字节

    Returns:
        反序列化后的Python对象
    """
    if HAS_ORJSON:
        return orjson.loads(s)
    return json.loads(s)
