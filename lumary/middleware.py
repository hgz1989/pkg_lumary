"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 应用中间件配置
"""
from logging import getLogger

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .common import generate_request_id, set_request_id

logger = getLogger(__name__)


class RequestIdMiddleware:
    """纯 ASGI request_id 中间件

    与 BaseHTTPMiddleware 不同，此中间件直接操作 ASGI 协议，
    在同一上下文中运行，确保 uvicorn.access 等日志能获取到 request_id。

    每次请求写入 ContextVar，不做 reset：
    - uvicorn.access 日志在中间件返回**之后**才发出，reset 会导致 request_id 丢失
    - 下一个请求会自动覆盖旧值，不存在串数据风险
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] not in ('http', 'websocket'):
            await self.app(scope, receive, send)
            return

        # 从请求头提取或自动生成 request_id
        headers_list = scope.get('headers', [])
        request_id = None
        for key, value in headers_list:
            if key == b'x-request-id':
                request_id = value.decode('utf-8')
                break
        if not request_id:
            request_id = generate_request_id()

        # 写入上下文变量（不做 reset，让值持续到 uvicorn.access 输出）
        set_request_id(request_id)

        if scope['type'] == 'http':
            # HTTP 请求：拦截 send，把 X-Request-ID 写入响应头
            async def send_with_request_id(message: Message) -> None:
                if message['type'] == 'http.response.start':
                    headers = list(message.get('headers', []))
                    headers.append((b'x-request-id', request_id.encode('utf-8')))
                    message = {**message, 'headers': headers}
                await send(message)

            await self.app(scope, receive, send_with_request_id)
        else:
            # WebSocket 请求：仅设置上下文，不注入响应头
            await self.app(scope, receive, send)


def setup_middlewares(
        app: FastAPI,
        *,
        enable_cors: bool,
        allow_origins: list[str] | None = None,
        allow_methods: list[str] | None = None,
        allow_headers: list[str] | None = None,
) -> None:
    """注册全局中间件

    将日志链路追踪、CORS 等中间件挂载到 FastAPI 实例

    Args:
        app: 当前运行的 FastAPI 应用实例
        enable_cors: 是否启用 CORS 中间件
        allow_origins: 允许的源列表
        allow_methods: 允许的方法列表
        allow_headers: 允许的头列表
    """
    # 纯 ASGI request_id 中间件（必须放在最外层，最先执行）
    app.add_middleware(RequestIdMiddleware)

    # 动态 CORS 跨域（根据配置开启）
    if enable_cors:
        origins = allow_origins or ['*']
        # 避免 `allow_origins=['*']` 与 `allow_credentials=True` 同时出现引发的兼容和安全风险
        credentials = origins != ['*']

        app.add_middleware(
            CORSMiddleware,  # type: ignore
            allow_origins=origins,
            allow_credentials=credentials,
            allow_methods=allow_methods or ['*'],
            allow_headers=allow_headers or ['*'],
        )
        logger.info(f'[{app.title}] Cross-Origin Resource Sharing enabled')
