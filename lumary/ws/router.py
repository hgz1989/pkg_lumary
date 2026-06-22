"""
@Author     : zarkhan
@CreateDate : 2026/6/14
@Description: WebSocket专用路由，禁止注册常规HTTP接口
"""
from fastapi import APIRouter


class WSRouter(APIRouter):
    """WebSocket专用路由

    继承自APIRouter，默认前缀为 '/ws'
    重写add_api_route禁止注册HTTP接口，确保该路由仅用于WebSocket端点
    """

    def __init__(self, *args, **kwargs):
        """初始化WebSocket专用路由

        Args:
            *args: 传递给APIRouter的位置参数
            **kwargs: 传递给APIRouter的关键字参数，prefix默认为 '/ws'
        """
        kwargs.setdefault('prefix', '/ws')
        super().__init__(*args, **kwargs)

    def add_api_route(self, *args, **kwargs):
        """禁止在当前路由实例上注册HTTP接口

        Args:
            *args: 无意义，仅为展示拦截
            **kwargs: 无意义，仅为展示拦截

        Raises:
            NotImplementedError: 无论何时调用均抛出
        """
        raise NotImplementedError('当前路由实例仅支持WebSocket，不允许注册HTTP接口')
