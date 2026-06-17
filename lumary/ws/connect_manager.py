"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: WebSocket 连接管理器
"""
import time
from asyncio import gather
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from logging import getLogger
from typing import Any
from uuid import uuid4

from fastapi import WebSocket

_logger = getLogger(__name__)


# WebSocket 连接管理器
class WSConnectionManager:
    """WebSocket 连接管理器

    管理所有活跃的 WebSocket 连接，支持按分组进行连接隔离和消息推送
    提供连接注册、注销、单播、广播、分组管理等能力

    设计约束：
        本管理器面向单事件循环（即典型 FastAPI/uvicorn 部署模型），
        不需要 asyncio.Lock，因为协程之间不存在抢占式中断，
        dict/set 的读写在 CPython 中本身是原子的

    Examples:
        manager = WSConnectionManager()

        # 方式一：手动管理连接生命周期
        @app.websocket("/ws")
        async def ws_endpoint(ws: WebSocket):
            cid = await manager.connect(ws, group='chat')
            try:
                while True:
                    data = await ws.receive_json()
                    await manager.broadcast_json(data, group='chat', exclude={cid})
            finally:
                await manager.disconnect(cid)

        # 方式二：使用上下文管理器（推荐，更安全）
        @app.websocket('/ws2')
        async def ws_endpoint2(ws: WebSocket):
            async with manager.lifespan(ws, group='chat') as cid:
                while True:
                    data = await ws.receive_json()
                    await manager.broadcast_json(data, group='chat', exclude={cid})
    """

    __slots__ = ('_connections', '_groups', '_metadata', '_last_seen')

    def __init__(self):
        """初始化"""
        self._connections: dict[str, WebSocket] = {}
        self._groups: dict[str, set[str]] = {}
        self._metadata: dict[str, dict[str, Any]] = {}   # 连接元数据
        self._last_seen: dict[str, float] = {}            # 最近心跳时间戳

    async def connect(self, websocket: WebSocket, *, connection_id: str | None = None, group: str | None = None, metadata: dict[str, Any] | None = None) -> str:
        """接受并存储新的 WebSocket 连接

        Args:
            websocket: FastAPI WebSocket 实例
            connection_id: 自定义连接ID（如 user_id），不传则自动生成 UUID
            group: 分组名称，加入后可按组广播
            metadata: 连接附带元数据，如用户名、角色、自定义标签等

        Returns:
            连接ID
        """
        await websocket.accept()

        cid = connection_id or str(uuid4())
        self._connections[cid] = websocket
        self._metadata[cid] = dict(metadata) if metadata else {}
        self._last_seen[cid] = time.monotonic()

        if group:
            self._groups.setdefault(group, set()).add(cid)

        _logger.info(f'WebSocket 已连接：{cid}' + (f' [分组：{group}]' if group else ''))
        return cid

    async def disconnect(self, connection_id: str) -> None:
        """断开并移除指定连接

        自动从所有分组中移除该连接，并关闭 WebSocket
        若连接已不存在或已关闭，则安全跳过

        Args:
            connection_id: 连接ID
        """
        ws = self._connections.pop(connection_id, None)
        self._metadata.pop(connection_id, None)
        self._last_seen.pop(connection_id, None)
        if ws is None:
            return

        # 从所有分组中移除
        for group_conns in self._groups.values():
            group_conns.discard(connection_id)

        # 清理空分组
        empty_groups = [g for g, conns in self._groups.items() if not conns]
        for g in empty_groups:
            del self._groups[g]

        # 安全关闭连接
        try:
            await ws.close()
        except Exception as e:
            _logger.warning(f'关闭 WebSocket 失败：{connection_id}，异常信息：{str(e)}')

        _logger.info(f'WebSocket 已断开：{connection_id}')

    @asynccontextmanager
    async def lifespan(
        self, websocket: WebSocket, *, connection_id: str | None = None, group: str | None = None, metadata: dict[str, Any] | None = None
    ) -> AsyncGenerator[str, None]:
        """上下文管理器方式管理连接生命周期

        自动处理连接的注册与注销，确保即使发生异常也能正确清理资源

        Args:
            websocket: FastAPI WebSocket 实例
            connection_id: 自定义连接ID，不传则自动生成 UUID
            group: 分组名称
            metadata: 连接附带元数据

        Yields:
            连接ID

        Examples:
            async with manager.lifespan(ws, group="room1") as cid:
                while True:
                    data = await ws.receive_json()
                    await manager.broadcast_json(data, group="room1", exclude={cid})
        """
        cid = await self.connect(websocket, connection_id=connection_id, group=group, metadata=metadata)
        try:
            yield cid
        finally:
            await self.disconnect(cid)

    # 分组管理
    def join_group(self, connection_id: str, group: str) -> None:
        """将已有连接加入指定分组

        Args:
            connection_id: 连接ID
            group: 分组名称

        Raises:
            KeyError: 当连接不存在时抛出
        """
        if connection_id not in self._connections:
            raise KeyError(f'连接 {connection_id} 不存在')
        self._groups.setdefault(group, set()).add(connection_id)
        _logger.debug(f'WebSocket {connection_id} 已加入分组：{group}')

    def leave_group(self, connection_id: str, group: str) -> None:
        """将连接从指定分组中移除

        不会断开连接，仅退出分组。若分组清空则自动清理

        Args:
            connection_id: 连接ID
            group: 分组名称
        """
        conns = self._groups.get(group)
        if conns is None:
            return

        conns.discard(connection_id)
        if not conns:
            del self._groups[group]

        _logger.debug(f'WebSocket {connection_id} 已离开分组：{group}')

    # 单播
    async def send_text(self, connection_id: str, message: str) -> None:
        """向指定连接发送文本消息

        Args:
            connection_id: 连接ID
            message: 文本消息
        """
        ws = self._connections.get(connection_id)
        if ws is None:
            _logger.warning(f'无法发送文本：连接 {connection_id} 不存在')
            return
        try:
            await ws.send_text(message)
        except Exception as e:
            _logger.error(f'向 {connection_id} 发送文本失败：{e}')

    async def send_json(self, connection_id: str, data: Any) -> None:
        """向指定连接发送 JSON 数据

        Args:
            connection_id: 连接ID
            data: 可序列化为 JSON 的数据
        """
        ws = self._connections.get(connection_id)
        if ws is None:
            _logger.warning(f'无法发送 JSON：连接 {connection_id} 不存在')
            return
        try:
            await ws.send_json(data)
        except Exception as e:
            _logger.error(f'向 {connection_id} 发送 JSON 失败：{e}')

    # 广播
    async def broadcast_text(self, message: str, *, group: str | None = None, exclude: set[str] | None = None) -> None:
        """广播文本消息

        Args:
            message: 文本消息
            group: 指定分组则只向该组广播，否则向所有连接广播
            exclude: 需要排除的连接ID集合
        """
        targets = self._resolve_targets(group, exclude)
        if not targets:
            return

        await gather(*[self.send_text(cid, message) for cid in targets])

    async def broadcast_json(self, data: Any, *, group: str | None = None, exclude: set[str] | None = None) -> None:
        """广播 JSON 数据

        Args:
            data: 可序列化为 JSON 的数据
            group: 指定分组则只向该组广播，否则向所有连接广播
            exclude: 需要排除的连接ID集合
        """
        targets = self._resolve_targets(group, exclude)
        if not targets:
            return

        await gather(*[self.send_json(cid, data) for cid in targets])

    # 元数据
    def get_metadata(self, connection_id: str, key: str, default: Any = None) -> Any:
        """获取连接元数据中的指定字段

        Args:
            connection_id: 连接ID
            key: 元数据字段名
            default: 不存在时的默认值

        Returns:
            元数据字段值，连接不存在或字段不存在时返回 default
        """
        return self._metadata.get(connection_id, {}).get(key, default)

    def set_metadata(self, connection_id: str, key: str, value: Any) -> None:
        """设置或更新连接元数据字段

        Args:
            connection_id: 连接ID
            key: 元数据字段名
            value: 元数据字段值

        Raises:
            KeyError: 连接不存在时抛出
        """
        if connection_id not in self._connections:
            raise KeyError(f'连接 {connection_id} 不存在')
        self._metadata[connection_id][key] = value

    def get_all_metadata(self, connection_id: str) -> dict[str, Any]:
        """获取连接的全部元数据

        Args:
            connection_id: 连接ID

        Returns:
            元数据字典副本，连接不存在时返回空字典
        """
        return dict(self._metadata.get(connection_id, {}))

    # 心跳检测
    async def ping(self, connection_id: str) -> bool:
        """向指定连接发送心跳包，并更新最近心跳时间

        发送应用层心跳包（空字节）检测连接活跃状态

        Args:
            connection_id: 连接ID

        Returns:
            True 表示发送成功，False 表示连接不存在或发送失败
        """
        ws = self._connections.get(connection_id)
        if ws is None:
            return False
        try:
            await ws.send_bytes(b'')
            self._last_seen[connection_id] = time.monotonic()
            return True
        except Exception as e:
            _logger.warning(f'WebSocket 心跳失败：{connection_id}，{e}')
            return False

    def update_heartbeat(self, connection_id: str) -> None:
        """手动将指定连接的最近心跳时间更新为当前时刻

        业务层收到消息时主动调用，避免被判定为失活连接

        Args:
            connection_id: 连接ID
        """
        if connection_id in self._last_seen:
            self._last_seen[connection_id] = time.monotonic()

    def get_stale_connections(self, timeout_seconds: float) -> list[str]:
        """获取超过指定时间未收到心跳的失活连接列表

        Args:
            timeout_seconds: 心跳超时阈值（秒）

        Returns:
            失活连接ID列表
        """
        now = time.monotonic()
        return [
            cid for cid, last in self._last_seen.items()
            if now - last > timeout_seconds
        ]

    # 内部方法
    def _resolve_targets(self, group: str | None, exclude: set[str] | None) -> set[str]:
        """解析广播目标连接集合

        Args:
            group: 分组名称，None 表示全部
            exclude: 需要排除的连接ID集合

        Returns:
            目标连接ID集合
        """
        targets = set(self._groups.get(group, set())) if group else set(self._connections.keys())

        if exclude:
            targets -= exclude

        return targets

    # 属性 & 魔术方法
    @property
    def active_count(self) -> int:
        """当前活跃连接数"""
        return len(self._connections)

    @property
    def groups(self) -> list[str]:
        """获取所有分组名称"""
        return list(self._groups.keys())

    def group_count(self, group: str) -> int:
        """获取指定分组的连接数

        Args:
            group: 分组名称

        Returns:
            连接数
        """
        return len(self._groups.get(group, set()))

    def is_connected(self, connection_id: str) -> bool:
        """检查连接是否活跃

        Args:
            connection_id: 连接ID

        Returns:
            是否活跃
        """
        return connection_id in self._connections

    def __len__(self) -> int:
        """返回当前活跃连接总数"""
        return len(self._connections)

    def __contains__(self, connection_id: str) -> bool:
        """检查指定连接是否已注册

        Args:
            connection_id: 连接ID

        Returns:
            若连接已注册则返回 True
        """
        return connection_id in self._connections

    def __repr__(self) -> str:
        """返回连接管理器的可读字符串表示"""
        return f'{self.__class__.__name__}(active={len(self._connections)}, groups={list(self._groups.keys())})'
