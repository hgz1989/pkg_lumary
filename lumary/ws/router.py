"""
@Author     : zarkhan
@Date       : 2026/6/14
@Description:
"""
from fastapi import APIRouter


class WebSocketRouter(APIRouter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.prefix = "/ws"

    # 拦截常规 HTTP 方法注册
    def add_api_route(self, *args, **kwargs):
        raise NotImplementedError("当前路由实例仅支持 WebSocket，不允许注册 HTTP 接口")

    # 可选：逐个拦截常用 HTTP 装饰器（增加友好提示）
    def get(self, *args, **kwargs):
        raise NotImplementedError("WSRouter 仅支持 WebSocket，禁止使用 GET")

    def post(self, *args, **kwargs):
        raise NotImplementedError("WSRouter 仅支持 WebSocket，禁止使用 POST")

    def put(self, *args, **kwargs):
        raise NotImplementedError("WSRouter 仅支持 WebSocket，禁止使用 PUT")

    def delete(self, *args, **kwargs):
        raise NotImplementedError("WSRouter 仅支持 WebSocket，禁止使用 DELETE")

    def patch(self, *args, **kwargs):
        raise NotImplementedError("WSRouter 仅支持 WebSocket，禁止使用 PATCH")
