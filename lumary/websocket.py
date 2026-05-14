"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: WebSocket 连接管理器
"""
from asyncio import gather
from contextlib import asynccontextmanager
from logging import getLogger
from typing import Any, AsyncGenerator
from uuid import uuid4

from fastapi import WebSocket

logger = getLogger(__name__)


# ===============================
# WebSocket 连接管理器
# ===============================
class WSConnectionManager:
    """WebSocket 连接管理器

    管理所有活跃的 WebSocket 连接，支持按分组进行连接隔离和消息推送。
    提供连接注册、注销、单播、广播、分组管理等能力。

    设计约束：
        本管理器面向单事件循环（即典型 FastAPI/uvicorn 部署模型），
        不需要 asyncio.Lock，因为协程之间不存在抢占式中断，
        dict/set 的读写在 CPython 中本身是原子的。

    Examples:
        manager = WSConnectionManager()

        # 方式一：手动管理连接生命周期
        @app.websocket("/ws")
        async def ws_endpoint(websocket: WebSocket):
            cid = await manager.connect(websocket, group="chat")
            try:
                while True:
                    data = await websocket.receive_json()
                    await manager.broadcast_json(data, group="chat", exclude={cid})
            finally:
                await manager.disconnect(cid)

        # 方式二：上下文管理器自动管理
        @app.websocket("/ws")
        async def ws_endpoint(websocket: WebSocket):
            async with manager.lifespan(websocket, group="chat") as cid:
                while True:
                    data = await websocket.receive_json()
                    await manager.broadcast_json(data, group="chat", exclude={cid})
    """

    __slots__ = ('_connections', '_groups')

    def __init__(self):
        """初始化"""
        self._connections: dict[str, WebSocket] = {}
        self._groups: dict[str, set[str]] = {}

    # ===============================
    # 连接生命周期
    # ===============================
    async def connect(
            self,
            websocket: WebSocket,
            *,
            connection_id: str | None = None,
            group: str | None = None
    ) -> str:
        """接受并存储新的 WebSocket 连接

        Args:
            websocket: FastAPI WebSocket 实例
            connection_id: 自定义连接ID（如 user_id），不传则自动生成 UUID
            group: 分组名称，加入后可按组广播

        Returns:
            连接ID
        """
        await websocket.accept()

        cid = connection_id or str(uuid4())
        self._connections[cid] = websocket

        if group:
            self._groups.setdefault(group, set()).add(cid)

        logger.info(f'WebSocket connected: {cid}' + (f' [group: {group}]' if group else ''))
        return cid

    async def disconnect(self, connection_id: str) -> None:
        """断开并移除指定连接

        自动从所有分组中移除该连接，并关闭 WebSocket。
        若连接已不存在或已关闭，则安全跳过。

        Args:
            connection_id: 连接ID
        """
        ws = self._connections.pop(connection_id, None)
        if ws is None:
            return

        # 👇 从所有分组中移除
        for group_conns in self._groups.values():
            group_conns.discard(connection_id)

        # 👇 清理空分组
        empty_groups = [g for g, conns in self._groups.items() if not conns]
        for g in empty_groups:
            del self._groups[g]

        # 👇 安全关闭连接
        try:
            await ws.close()
        except Exception:
            pass

        logger.info(f'WebSocket disconnected: {connection_id}')

    @asynccontextmanager
    async def lifespan(
            self,
            websocket: WebSocket,
            *,
            connection_id: str | None = None,
            group: str | None = None
    ) -> AsyncGenerator[str, None]:
        """上下文管理器方式管理连接生命周期

        自动处理连接的注册与注销，确保即使发生异常也能正确清理资源。

        Args:
            websocket: FastAPI WebSocket 实例
            connection_id: 自定义连接ID，不传则自动生成 UUID
            group: 分组名称

        Yields:
            连接ID

        Examples:
            async with manager.lifespan(websocket, group="room1") as cid:
                while True:
                    data = await websocket.receive_json()
                    await manager.broadcast_json(data, group="room1", exclude={cid})
        """
        cid = await self.connect(websocket, connection_id=connection_id, group=group)
        try:
            yield cid
        finally:
            await self.disconnect(cid)

    # ===============================
    # 分组管理
    # ===============================
    def join_group(self, connection_id: str, group: str) -> None:
        """将已有连接加入指定分组

        Args:
            connection_id: 连接ID
            group: 分组名称

        Raises:
            KeyError: 当连接不存在时抛出
        """
        if connection_id not in self._connections:
            raise KeyError(f'Connection {connection_id} does not exist')
        self._groups.setdefault(group, set()).add(connection_id)
        logger.debug(f'WebSocket {connection_id} joined group: {group}')

    def leave_group(self, connection_id: str, group: str) -> None:
        """将连接从指定分组中移除

        不会断开连接，仅退出分组。若分组清空则自动清理。

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

        logger.debug(f'WebSocket {connection_id} left group: {group}')

    # ===============================
    # 单播
    # ===============================
    async def send_text(self, connection_id: str, message: str) -> None:
        """向指定连接发送文本消息

        Args:
            connection_id: 连接ID
            message: 文本消息
        """
        ws = self._connections.get(connection_id)
        if ws is None:
            logger.warning(f'Cannot send text: connection {connection_id} not found')
            return
        try:
            await ws.send_text(message)
        except Exception as e:
            logger.error(f'Failed to send text to {connection_id}: {e}')

    async def send_json(self, connection_id: str, data: Any) -> None:
        """向指定连接发送 JSON 数据

        Args:
            connection_id: 连接ID
            data: 可序列化为 JSON 的数据
        """
        ws = self._connections.get(connection_id)
        if ws is None:
            logger.warning(f'Cannot send json: connection {connection_id} not found')
            return
        try:
            await ws.send_json(data)
        except Exception as e:
            logger.error(f'Failed to send json to {connection_id}: {e}')

    # ===============================
    # 广播
    # ===============================
    async def broadcast_text(
            self,
            message: str,
            *,
            group: str | None = None,
            exclude: set[str] | None = None
    ) -> None:
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

    async def broadcast_json(
            self,
            data: Any,
            *,
            group: str | None = None,
            exclude: set[str] | None = None
    ) -> None:
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

    # ===============================
    # 内部方法
    # ===============================
    def _resolve_targets(
            self,
            group: str | None,
            exclude: set[str] | None
    ) -> set[str]:
        """解析广播目标连接集合

        Args:
            group: 分组名称，None 表示全部
            exclude: 需要排除的连接ID集合

        Returns:
            目标连接ID集合
        """
        if group:
            targets = set(self._groups.get(group, set()))
        else:
            targets = set(self._connections.keys())

        if exclude:
            targets -= exclude

        return targets

    # ===============================
    # 属性 & 魔术方法
    # ===============================
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
        return len(self._connections)

    def __contains__(self, connection_id: str) -> bool:
        return connection_id in self._connections

    def __repr__(self) -> str:
        return (
            f'{self.__class__.__name__}('
            f'active={len(self._connections)}, '
            f'groups={list(self._groups.keys())}'
            f')'
        )
