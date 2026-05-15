"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 
"""
from typing import Any


class BusinessException(Exception):
    """业务异常基类

    用于在业务逻辑层主动抛出已知的业务错误，如：参数不合法、资源不存在等
    抛出此异常后，将被全局拦截器捕获并返回 HTTP 200 及统一的 JSON 错误结构
    """

    def __init__(self, code: int, message: str, data: Any = None):
        """初始化业务异常

        Args:
            code: 业务错误码
            message: 错误提示信息
            data: 附加的错误数据或调试信息，默认为 None
        """
        self.code = code
        self.message = message
        self.data = data