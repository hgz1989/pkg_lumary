"""
@Author     : zarkhan
@CreateDate : 2026/6/21
@Description: 可选的MQTT客户端与路由管理器(基于paho-mqtt)
"""
import asyncio
from inspect import iscoroutinefunction
from logging import getLogger
from typing import Any, Callable

from lumary.common.utils.strings import json_dumps

try:
    import paho.mqtt.client as mqtt

    MQTT_INSTALLED = True
except ImportError:
    MQTT_INSTALLED = False
    mqtt = Any  # type: ignore

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


class MQTTManager:
    """MQTT管理器 (基于paho-mqtt)

    提供优雅的主题订阅装饰器机制，支持一个主题绑定多个处理程序
    利用 paho-mqtt 自带的网络循环线程，结合 asyncio.run_coroutine_threadsafe 桥接 FastAPI 异步循环
    如果未安装paho-mqtt库，则默认所有操作静默失效，保证业务安全降级
    """
    __slots__ = ('client', 'handlers', 'enabled', '_fastapi_loop')

    def __init__(self) -> None:
        """初始化"""
        self.client: mqtt.Client | None = None
        self.handlers: dict[str, list[Callable]] = {}
        self.enabled: bool = False
        self._fastapi_loop: asyncio.AbstractEventLoop | None = None

    def on_message(self, topic: str) -> Callable:
        """MQTT消息处理装饰器

        允许为同一个主题绑定多个处理函数。当收到消息时，所有匹配的函数将并发执行

        Args:
            topic: 订阅的主题模式（支持 + 和 # 通配符）

        Returns:
            装饰器函数
        """

        def decorator(func: Callable) -> Callable:
            """装饰器函数

            Args:
                func: 要装饰的函数

            Returns:
                装饰后的函数
            """
            if topic not in self.handlers:
                self.handlers[topic] = []
            self.handlers[topic].append(func)
            return func

        return decorator

    async def init(self, host: str, port: int = 1883, client_id: str | None = None,
                   username: str | None = None, password: str | None = None, **kwargs: Any) -> None:
        """初始化并连接MQTT服务器

        自动拉起 paho-mqtt 的 loop_start 后台线程

        Args:
            host: 服务器地址
            port: 端口
            client_id: 客户端ID
            username: 用户名
            password: 密码
            **kwargs: 传递给 mqtt.Client 的其他参数
        """
        if not MQTT_INSTALLED:
            raise RuntimeError('未安装paho-mqtt依赖，无法启动MQTT！请使用pip install lumary[mqtt] 安装')

        # 捕获 FastAPI 主线程的 event_loop，用于后续从 paho 线程中分发异步任务
        self._fastapi_loop = asyncio.get_running_loop()

        # paho-mqtt v2 回调版本要求
        client_kwargs: dict[str, Any] = {'client_id': client_id} if client_id else {}
        if hasattr(mqtt, 'CallbackAPIVersion'):
            client_kwargs['callback_api_version'] = getattr(mqtt.CallbackAPIVersion, 'VERSION2', 2)

        client = mqtt.Client(**client_kwargs, **kwargs)
        self.client = client

        if username and password:
            client.username_pw_set(username, password)

        # 绑定内部回调
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_paho_message

        try:
            client.connect(host, port)
            # 启动 paho 内部的网络收发线程
            client.loop_start()
            self.enabled = True
        except Exception as e:
            _logger.error(f'MQTT连接失败: {e}')
            raise

    def _on_connect(self, client: Any, userdata: Any, flags: Any, rc: Any, *args: Any) -> None:
        """Paho 连接成功回调
        
        Args:
            client: paho mqtt客户端实例
            userdata: 用户自定义数据
            flags: 响应标志
            rc: 连接结果码
            *args: 其他兼容参数
        """
        # 消除未使用变量的警告
        _ = userdata
        _ = flags
        _ = args
        
        # paho-mqtt v2 返回的是 ReasonCode 对象，可以直接判断 is_failure
        is_fail = getattr(rc, 'is_failure', rc != 0)
        if not is_fail:
            _logger.info('MQTT客户端连接成功')
            # 连接成功后，自动订阅所有已注册的主题
            for topic in self.handlers:
                client.subscribe(topic)
                _logger.info(f'MQTT已自动订阅主题: {topic}')
        else:
            _logger.error(f'MQTT连接被拒绝，返回码: {rc}')

    @staticmethod
    def _on_disconnect(client: Any, userdata: Any, rc: Any, *args: Any) -> None:
        """Paho 断开连接回调
        
        Args:
            client: paho mqtt客户端实例
            userdata: 用户自定义数据
            rc: 断开结果码
            *args: 其他兼容参数
        """
        _ = client
        _ = userdata
        _ = args
        _logger.warning(f'MQTT客户端已断开连接，返回码: {rc}')

    def _on_paho_message(self, client: Any, userdata: Any, msg: Any) -> None:
        """Paho 收到消息回调（运行在 Paho 的后台线程中）
        
        Args:
            client: paho mqtt客户端实例
            userdata: 用户自定义数据
            msg: MQTT消息对象
        """
        _ = client
        _ = userdata
        
        if not self._fastapi_loop:
            return

        topic = msg.topic
        try:
            payload = msg.payload.decode('utf-8')
        except UnicodeDecodeError:
            payload = msg.payload  # 非文本载荷保持 bytes

        # 路由匹配：寻找所有匹配该 topic 的处理器
        matched_handlers = []
        for pattern, funcs in self.handlers.items():
            if topic_matches(pattern, topic):
                matched_handlers.extend(funcs)

        if not matched_handlers:
            return

        # 由于当前在 paho 线程，必须通过 run_coroutine_threadsafe 投递回 FastAPI 的 async loop 执行
        for func in matched_handlers:
            try:
                # 判断是否是异步函数 (使用 inspect.iscoroutinefunction 替代 asyncio.iscoroutinefunction 避免未来版本弃用)
                if iscoroutinefunction(func):
                    asyncio.run_coroutine_threadsafe(func(topic, payload), self._fastapi_loop)
                else:
                    # 同步函数直接在当前线程执行（或者考虑投入线程池以防阻塞 paho 循环）
                    self._fastapi_loop.call_soon_threadsafe(func, topic, payload)
            except Exception as e:
                _logger.error(f'MQTT消息分发失败: {e}')

    async def publish(self, topic: str, payload: Any, qos: int = 0, retain: bool = False) -> None:
        """发布消息

        Args:
            topic: 主题
            payload: 消息内容（支持自动JSON序列化）
            qos: 服务质量
            retain: 是否保留消息
        """
        if not self.enabled or not self.client:
            return

        try:
            if isinstance(payload, (dict, list)):
                payload = json_dumps(payload)
            elif not isinstance(payload, (str, bytes)):
                payload = str(payload)

            # paho的publish是异步（非阻塞）的，直接调用即可
            self.client.publish(topic, payload, qos=qos, retain=retain)
        except Exception as e:
            _logger.error(f'MQTT发布消息失败: {e}')

    async def close(self) -> None:
        """安全关闭客户端"""
        if self.client:
            self.enabled = False
            self.client.loop_stop()
            self.client.disconnect()
            _logger.info('MQTT客户端已安全关闭')

# 全局单例
mqtt_client = MQTTManager()
