"""
@Author     : zarkhan
@CreateDate : 2026/6/21
@Description: 可选的异步MQTT客户端与路由管理器
"""
import asyncio
from logging import getLogger
from typing import Any, Callable

from lumary.common.utils.strings import json_dumps

try:
    import aiomqtt
    from aiomqtt import Client

    MQTT_INSTALLED = True
except ImportError:
    MQTT_INSTALLED = False
    aiomqtt = Any  # type: ignore

    class Client:  # type: ignore
        """MQTT Client降级桩类，解决Pylance对Any | None的类型收窄警告"""
        async def publish(self, topic: str, payload: Any, **kwargs: Any) -> None: ...
        async def subscribe(self, topic: str, **kwargs: Any) -> None: ...
        messages: Any

_logger = getLogger(__name__)


def topic_matches(pattern: str, topic: str) -> bool:
    """判断实际topic是否匹配带通配符的pattern

    支持MQTT标准通配符：
    - `+` 匹配单层级
    - `#` 匹配多层级

    Args:
        pattern: 订阅的模式字符串（如sensor/+/temp）
        topic: 实际接收到的主题（如sensor/room1/temp）

    Returns:
        是否匹配成功
    """
    p_levels = pattern.split('/')
    t_levels = topic.split('/')

    for i, p in enumerate(p_levels):

        if p == '#':
            return True

        if i >= len(t_levels):
            return False

        if p != '+' and p != t_levels[i]:
            return False

    return len(p_levels) == len(t_levels)


class MqttManager:
    """异步MQTT管理器

    提供优雅的主题订阅装饰器机制，支持一个主题绑定多个处理程序
    如果未安装aiomqtt库，则默认所有操作静默失效，保证业务安全降级
    """
    __slots__ = ('client', 'handlers', 'enabled', '_listen_task')

    def __init__(self):
        """初始化"""
        self.client: Client | None = None
        self.handlers: dict[str, list[Callable]] = {}
        self.enabled: bool = False
        self._listen_task: asyncio.Task | None = None

    def on_message(self, topic: str) -> Callable:
        """MQTT消息处理装饰器

        允许为同一个主题绑定多个处理函数。当收到消息时，所有匹配的函数将并发执行

        Args:
            topic: 订阅的主题模式（支持 + 和 # 通配符）

        Returns:
            装饰器函数
        """

        def decorator(func: Callable) -> Callable:
            """内层装饰器，接收原始处理函数"""
            if topic not in self.handlers:
                self.handlers[topic] = []

            self.handlers[topic].append(func)
            return func

        return decorator

    async def init(self, hostname: str, port: int = 1883, **kwargs: Any) -> None:
        """初始化MQTT客户端并启动后台监听任务

        Args:
            hostname: MQTT Broker主机地址
            port: MQTT Broker端口
            **kwargs: 透传给aiomqtt.Client的其他参数 (如username, password)
            
        Raises:
            RuntimeError: 如果未安装aiomqtt依赖时抛出
        """
        if not MQTT_INSTALLED:
            raise RuntimeError('未安装aiomqtt依赖，无法启动MQTT！请使用pip install lumary[mqtt] 安装')

        self.enabled = True
        self._listen_task = asyncio.create_task(self._listen(hostname, port, kwargs))
        _logger.info('MQTT后台监听任务已启动')

    async def close(self) -> None:
        """关闭MQTT连接与监听任务"""
        self.enabled = False

        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()

        _logger.info('MQTT监听任务已安全关闭')

    async def publish(self, topic: str, payload: Any, **kwargs: Any) -> None:
        """发布MQTT消息

        Args:
            topic: 目标主题
            payload: 消息负载（如果是dict将自动转为JSON字符串）
            **kwargs: 透传给publish的其他参数 (如qos, retain)
        """
        mqtt_c = self.client

        if not self.enabled or mqtt_c is None:
            return

        if isinstance(payload, dict):
            payload = json_dumps(payload)

        try:
            await mqtt_c.publish(topic, payload, **kwargs)
        except Exception as e:
            _logger.error(f'MQTT发布消息失败 [{topic}]: {e}')

    async def _safe_execute(self, func: Callable, topic: str, payload: bytes) -> None:
        """安全执行处理程序，防止单点报错导致整个事件循环崩溃

        Args:
            func: 处理程序
            topic: 实际主题
            payload: 消息负载
        """
        try:
            await func(topic, payload)
        except Exception as e:
            _logger.error(f'MQTT处理程序执行异常 [{topic}]: {e}', exc_info=True)

    async def _listen(self, hostname: str, port: int, kwargs: dict[str, Any]) -> None:
        """内部无限循环的后台监听协程

        负责维持连接、订阅主题并分发消息到对应的处理程序

        Args:
            hostname: 主机
            port: 端口
            kwargs: 其他连接参数
        """
        while self.enabled:
            try:
                async with aiomqtt.Client(hostname, port=port, **kwargs) as client:
                    self.client = client
                    _logger.info(f'MQTT成功连接至 {hostname}:{port}')

                    # 批量订阅已注册的所有主题
                    for topic in self.handlers.keys():
                        await client.subscribe(topic)
                        _logger.debug(f'MQTT已订阅主题: {topic}')

                    # 循环接收并分发消息
                    async for message in client.messages:
                        incoming_topic = str(message.topic)
                        payload = message.payload if isinstance(message.payload, bytes) else str(
                            message.payload).encode('utf-8')

                        # 遍历路由表寻找所有匹配的处理函数
                        for pattern, funcs in self.handlers.items():
                            if topic_matches(pattern, incoming_topic):
                                for func in funcs:
                                    # 创建独立任务并发执行，避免阻塞主接收循环
                                    asyncio.create_task(self._safe_execute(func, incoming_topic, payload))

            except aiomqtt.MqttError as e:
                _logger.warning(f'MQTT断开连接，3秒后尝试重连: {e}')
                await asyncio.sleep(3)
            except asyncio.CancelledError:
                break
            except Exception as e:
                _logger.error(f'MQTT监听发生未捕获异常: {e}')
                await asyncio.sleep(3)


# 全局单例
mqtt_client = MqttManager()
