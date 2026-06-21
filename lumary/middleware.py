"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 应用中间件配置
"""

from starlette.types import ASGIApp, Scope, Receive, Send, Message

from .common import generate_request_id, set_request_id


class RequestIdMiddleware:
    """纯 ASGI request_id 中间件

    与 BaseHTTPMiddleware 不同，此中间件直接操作 ASGI 协议，
    在同一上下文中运行，确保 uvicorn.access 等日志能获取到 request_id

    每次请求写入 ContextVar，不做 reset：
    - uvicorn.access 日志在中间件返回**之后**才发出，reset 会导致 request_id 丢失
    - 下一个请求会自动覆盖旧值，不存在串数据风险
    """

    def __init__(self, app: ASGIApp):
        """初始化 request_id 中间件

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

        # 使用 C 层级的 dict 转换实现 O(1) 提取，取代 Python 层级的 for 循环遍历
        headers = dict(scope.get('headers', []))
        request_id_bytes = headers.get(b'x-request-id')
        
        request_id = request_id_bytes.decode('utf-8') if request_id_bytes else generate_request_id()

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
