"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 应用中间件配置
"""
from starlette.types import ASGIApp, Scope, Receive, Send, Message

from .common import generate_request_id, set_request_id


class RequestIdMiddleware:
    """纯ASGI request_id中间件

    与BaseHTTPMiddleware不同，此中间件直接操作ASGI协议，
    在同一上下文中运行，确保uvicorn.access等日志能获取到request_id

    通过优化ASGI消息拦截，极大降低了对流式响应（StreamingResponse）的性能损耗
    """

    def __init__(self, app: ASGIApp):
        """初始化request_id中间件

        Args:
            app: ASGI应用
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """处理ASGI请求

        Args:
            scope: ASGI作用域
            receive: 接收请求数据
            send: 发送响应数据
        """
        if scope['type'] not in ('http', 'websocket'):
            await self.app(scope, receive, send)
            return

        # 提取或生成Request ID
        headers = dict(scope.get('headers', []))
        request_id_bytes = headers.get(b'x-request-id')

        if request_id_bytes and isinstance(request_id_bytes, bytes):
            request_id = request_id_bytes.decode('utf-8')
        else:
            request_id = generate_request_id()

        # 写入上下文变量（不做reset，让值持续到uvicorn.access输出）
        set_request_id(request_id)

        if scope['type'] == 'http':
            # 优化：只在response.start阶段拦截并修改headers，后续数据块直接透传，提升性能
            response_started = False

            async def send_wrapper(message: Message) -> None:
                nonlocal response_started
                if not response_started and message['type'] == 'http.response.start':
                    response_started = True
                    resp_headers  = list(message.get('headers', []))
                    resp_headers .append((b'x-request-id', request_id.encode('utf-8')))
                    message['headers'] = resp_headers
                await send(message)

            await self.app(scope, receive, send_wrapper)
        else:
            # WebSocket请求：仅设置上下文，不注入响应头
            await self.app(scope, receive, send)
