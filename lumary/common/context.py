"""
@Author     : zarkhan
@CreateDate : 2026/6/16
@Description: 全局上下文变量管理
"""
from contextvars import ContextVar, Token
from uuid import uuid4

# 定义用于存储request_id的上下文变量，默认值为None
request_id_ctx_var: ContextVar[str | None] = ContextVar('request_id', default=None)


def generate_request_id() -> str:
    """生成一个随机的Request ID

    Returns:
        随机生成的Request ID
    """
    return str(uuid4())


def set_request_id(request_id: str) -> Token:
    """设置当前请求的Request ID

    Args:
        request_id: 当前请求的Request ID

    Returns:
        上下文变量的Token
    """
    return request_id_ctx_var.set(request_id)


def get_request_id() -> str | None:
    """获取当前请求的Request ID

    Returns:
        当前请求的Request ID，如果不存在则返回None
    """
    return request_id_ctx_var.get()
