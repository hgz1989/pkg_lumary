"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 应用中间件配置
"""
from contextvars import ContextVar, Token
from uuid import uuid4

from starlette.types import ASGIApp, Scope, Receive, Send, Message

# 定义用于存储request_id的上下文变量，默认值为None
request_id_ctx_var: ContextVar[str | None] = ContextVar('request_id', default=None)

def get_request_id() -> str | None:
    """获取当前请求的Request ID"""
    return request_id_ctx_var.get()

def set_request_id(request_id: str) -> Token:
    """设置当前请求的Request ID"""
    return request_id_ctx_var.set(request_id)

def generate_request_id() -> str:
    """生成一个随机的Request ID"""
    return uuid4().hex


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
        # 优化：ASGI headers 是一个包含 tuple 的 list，不需要转成 dict 也能找，转 dict 每次请求都会产生性能损耗
        request_id = None

        for name, value in scope.get('headers', []):
            if name == b'x-request-id':
                request_id = value.decode('latin-1')
                break

        if not request_id:
            request_id = generate_request_id()

        # 写入上下文变量（不做reset，让值持续到uvicorn.access输出）
        set_request_id(request_id)

        if scope['type'] == 'http':
            # 将 request_id 提前编码为 bytes，避免在内部闭包中反复执行 encode
            request_id_bytes_val = request_id.encode('latin-1')

            async def send_wrapper(message: Message) -> None:
                """包装响应消息

                Args:
                    message: ASGI响应消息
                """
                if message['type'] == 'http.response.start':
                    # 使用 list comprehension 或 copy 避免修改原始的可变引用
                    # 避免多次调用 append 导致的重复头部或性能损耗
                    headers = message.get('headers', [])

                    # 快速检查是否已经存在 x-request-id（应对某些特殊内部重定向或早早设置的情况）
                    if not any(k == b'x-request-id' for k, _ in headers):
                        headers.append((b'x-request-id', request_id_bytes_val))

                    message['headers'] = headers
                await send(message)

            await self.app(scope, receive, send_wrapper)
        else:
            # WebSocket请求：仅设置上下文，不注入响应头
            await self.app(scope, receive, send)
