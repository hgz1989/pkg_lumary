"""
@Author     : zarkhan
@CreateDate : 2026/6/14
@Description: WebSocket 专用路由，禁止注册常规 HTTP 接口
"""
from fastapi import APIRouter


class WSRouter(APIRouter):
    """WebSocket 专用路由

    继承自 APIRouter，默认前缀为 '/ws'
    重写 add_api_route 禁止注册 HTTP 接口，确保该路由仅用于 WebSocket 端点
    """

    def __init__(self, *args, **kwargs):
        """初始化 WebSocket 专用路由

        Args:
            *args: 传递给 APIRouter 的位置参数
            **kwargs: 传递给 APIRouter 的关键字参数，prefix 默认为 '/ws'
        """
        kwargs.setdefault('prefix', '/ws')
        super().__init__(*args, **kwargs)

    def add_api_route(self, *args, **kwargs):
        """禁止在当前路由实例上注册 HTTP 接口

        Args:
            *args: 无意义，仅为展示拦截
            **kwargs: 无意义，仅为展示拦截

        Raises:
            NotImplementedError: 无论何时调用均抛出
        """
        raise NotImplementedError('当前路由实例仅支持 WebSocket，不允许注册 HTTP 接口')
