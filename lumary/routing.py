"""
@Author     : zarkhan
@CreateDate : 2026/6/17
@Description: 自动响应包装路由
"""
from functools import wraps
from inspect import iscoroutinefunction
from typing import Callable, Any

from fastapi import Response
from fastapi.routing import APIRoute

from .schemas import APIResponse, response_success


def _wrap_endpoint(endpoint: Callable) -> Callable:
    """包装路由函数，将其返回值统一包装为APIResponse

    Args:
        endpoint: 原始的路由处理函数

    Returns:
        包装后的路由处理函数
    """

    @wraps(endpoint)
    async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        """异步路由函数的包装器

        Args:
            *args: 路由函数的位置参数
            **kwargs: 路由函数的关键字参数

        Returns:
            统一格式化的响应数据
        """
        raw_response = await endpoint(*args, **kwargs)
        return _process_raw_response(raw_response)

    @wraps(endpoint)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        """同步路由函数的包装器

        Args:
            *args: 路由函数的位置参数
            **kwargs: 路由函数的关键字参数

        Returns:
            统一格式化的响应数据
        """
        raw_response = endpoint(*args, **kwargs)
        return _process_raw_response(raw_response)

    def _process_raw_response(raw_response: Any) -> Any:
        """处理并格式化原始响应数据

        Args:
            raw_response: 路由函数返回的原始数据

        Returns:
            经过APIResponse包装后的数据
        """
        if isinstance(raw_response, (Response, APIResponse)):
            return raw_response

        # 使用exact type matching替代isinstance，绕过MRO查找，提升高并发下的纳秒级性能
        raw_type = type(raw_response)

        if raw_type is tuple:
            length = len(raw_response)
            if length == 2:
                return response_success(data=raw_response[0], extra=raw_response[1])
            elif length == 3:
                return response_success(data=raw_response[0], extra=raw_response[1], message=raw_response[2])

        if raw_type is dict and 'code' in raw_response and 'message' in raw_response:
            # 如果是字典透传，使用APIResponse解析一下确保格式统一并带上request_id
            return APIResponse(**raw_response)

        return response_success(data=raw_response)

    return async_wrapper if iscoroutinefunction(endpoint) else sync_wrapper


class WrapAPIRoute(APIRoute):
    """自动包装响应的自定义路由类

    能够拦截路由函数的返回值，并自动包装为标准的APIResponse，
    同时动态修正Swagger OpenAPI的response_model推导
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """初始化路由实例，并动态修正OpenAPI响应模型推导

        Args:
            *args: 路由初始化位置参数
            **kwargs: 路由初始化关键字参数
        """
        # 替换endpoint，使底层依赖注入和序列化针对包装后的结果
        if 'endpoint' in kwargs:
            kwargs['endpoint'] = _wrap_endpoint(kwargs['endpoint'])

        super().__init__(*args, **kwargs)

        if self.response_model:
            origin_type = getattr(self.response_model, '__origin__', self.response_model)

            if isinstance(origin_type, type) and issubclass(origin_type, (Response, APIResponse)):
                pass
            else:
                if getattr(self.response_model, '__origin__', None) is tuple:
                    type_args = getattr(self.response_model, '__args__', ())

                    if len(type_args) >= 2:
                        data_type, extra_type = type_args[0], type_args[1]
                        self.response_model = APIResponse[data_type, extra_type]  # type: ignore
                else:
                    self.response_model = APIResponse[self.response_model, Any]  # type: ignore

        # 清空内部校验字段，防止FastAPI运行时抛出ResponseValidationError
        # 注意：不同 FastAPI 版本的内部属性名称可能不同，兼容处理
        if hasattr(self, 'secure_cloned_response_field'):
            self.secure_cloned_response_field = None
        if hasattr(self, 'response_field'):
            self.response_field = None
