"""
@Author     : zarkhan
@CreateDate : 2026/6/17
@Description: WSConnectionManager单元测试（使用MagicMock模拟WebSocket）
"""
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lumary.ws.connect_manager import WSConnectionManager


# ──────────────────────────────────────────────
# 辅助：创建模拟WebSocket
# ──────────────────────────────────────────────
def _make_ws() -> MagicMock:
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    ws.send_text = AsyncMock()
    ws.send_json = AsyncMock()
    ws.send_bytes = AsyncMock()
    return ws


@pytest.fixture
def manager() -> WSConnectionManager:
    return WSConnectionManager()


# ──────────────────────────────────────────────
# 连接 & 断开
# ──────────────────────────────────────────────
class TestConnectDisconnect:
    async def test_connect_accepts_websocket(self, manager):
        ws = _make_ws()
        cid = await manager.connect(ws)
        ws.accept.assert_called_once()
        assert manager.is_connected(cid)

    async def test_connect_returns_cid(self, manager):
        ws = _make_ws()
        cid = await manager.connect(ws)
        assert isinstance(cid, str) and len(cid) > 0

    async def test_connect_custom_connection_id(self, manager):
        ws = _make_ws()
        cid = await manager.connect(ws, connection_id='custom-id')
        assert cid == 'custom-id'

    async def test_connect_with_group(self, manager):
        ws = _make_ws()
        cid = await manager.connect(ws, group='room1')
        assert 'room1' in manager.groups
        assert manager.group_count('room1') == 1

    async def test_connect_with_metadata(self, manager):
        ws = _make_ws()
        cid = await manager.connect(ws, metadata={'user': 'alice'})
        assert manager.get_metadata(cid, 'user') == 'alice'

    async def test_disconnect_removes_connection(self, manager):
        ws = _make_ws()
        cid = await manager.connect(ws)
        await manager.disconnect(cid)
        assert not manager.is_connected(cid)

    async def test_disconnect_closes_ws(self, manager):
        ws = _make_ws()
        cid = await manager.connect(ws)
        await manager.disconnect(cid)
        ws.close.assert_called_once()

    async def test_disconnect_nonexistent_safe(self, manager):
        """断开不存在的连接不应抛出异常"""
        await manager.disconnect('nonexistent')

    async def test_disconnect_removes_from_group(self, manager):
        ws = _make_ws()
        cid = await manager.connect(ws, group='grp')
        await manager.disconnect(cid)
        assert 'grp' not in manager.groups

    async def test_disconnect_clears_metadata(self, manager):
        ws = _make_ws()
        cid = await manager.connect(ws, metadata={'k': 'v'})
        await manager.disconnect(cid)
        assert manager.get_all_metadata(cid) == {}

    async def test_active_count_updates(self, manager):
        ws1, ws2 = _make_ws(), _make_ws()
        await manager.connect(ws1)
        cid2 = await manager.connect(ws2)
        assert manager.active_count == 2
        await manager.disconnect(cid2)
        assert manager.active_count == 1


# ──────────────────────────────────────────────
# 分组管理
# ──────────────────────────────────────────────
class TestGroupManagement:
    async def test_join_group(self, manager):
        ws = _make_ws()
        cid = await manager.connect(ws)
        manager.join_group(cid, 'chat')
        assert 'chat' in manager.groups

    async def test_join_nonexistent_connection_raises(self, manager):
        with pytest.raises(KeyError):
            manager.join_group('ghost', 'chat')

    async def test_leave_group(self, manager):
        ws = _make_ws()
        cid = await manager.connect(ws, group='grp')
        manager.leave_group(cid, 'grp')
        assert 'grp' not in manager.groups

    async def test_leave_nonexistent_group_safe(self, manager):
        ws = _make_ws()
        cid = await manager.connect(ws)
        manager.leave_group(cid, 'nonexistent_group')  # 不应抛出

    async def test_group_count(self, manager):
        ws1, ws2 = _make_ws(), _make_ws()
        await manager.connect(ws1, group='room')
        await manager.connect(ws2, group='room')
        assert manager.group_count('room') == 2

    async def test_group_count_nonexistent_is_zero(self, manager):
        assert manager.group_count('no_such_group') == 0


# ──────────────────────────────────────────────
# 单播
# ──────────────────────────────────────────────
class TestSendMessage:
    async def test_send_text(self, manager):
        ws = _make_ws()
        cid = await manager.connect(ws)
        await manager.send_text(cid, 'hello')
        ws.send_text.assert_called_once_with('hello')

    async def test_send_json(self, manager):
        ws = _make_ws()
        cid = await manager.connect(ws)
        await manager.send_json(cid, {'key': 'val'})
        ws.send_json.assert_called_once_with({'key': 'val'})

    async def test_send_text_nonexistent_safe(self, manager):
        """向不存在的连接发送不应抛出异常"""
        await manager.send_text('ghost', 'msg')

    async def test_send_json_nonexistent_safe(self, manager):
        await manager.send_json('ghost', {})


# ──────────────────────────────────────────────
# 广播
# ──────────────────────────────────────────────
class TestBroadcast:
    async def test_broadcast_text_all(self, manager):
        ws1, ws2 = _make_ws(), _make_ws()
        await manager.connect(ws1)
        await manager.connect(ws2)
        await manager.broadcast_text('hi')
        ws1.send_text.assert_called_once_with('hi')
        ws2.send_text.assert_called_once_with('hi')

    async def test_broadcast_text_group(self, manager):
        ws1, ws2 = _make_ws(), _make_ws()
        await manager.connect(ws1, group='g1')
        await manager.connect(ws2, group='g2')
        await manager.broadcast_text('g1_msg', group='g1')
        ws1.send_text.assert_called_once_with('g1_msg')
        ws2.send_text.assert_not_called()

    async def test_broadcast_text_exclude(self, manager):
        ws1, ws2 = _make_ws(), _make_ws()
        cid1 = await manager.connect(ws1)
        await manager.connect(ws2)
        await manager.broadcast_text('msg', exclude={cid1})
        ws1.send_text.assert_not_called()
        ws2.send_text.assert_called_once()

    async def test_broadcast_json_all(self, manager):
        ws1, ws2 = _make_ws(), _make_ws()
        await manager.connect(ws1)
        await manager.connect(ws2)
        data = {'event': 'update'}
        await manager.broadcast_json(data)
        ws1.send_json.assert_called_once_with(data)
        ws2.send_json.assert_called_once_with(data)

    async def test_broadcast_empty_no_error(self, manager):
        """没有连接时广播不应报错"""
        await manager.broadcast_text('nobody')
        await manager.broadcast_json({})


# ──────────────────────────────────────────────
# 元数据
# ──────────────────────────────────────────────
class TestMetadata:
    async def test_set_get_metadata(self, manager):
        ws = _make_ws()
        cid = await manager.connect(ws)
        manager.set_metadata(cid, 'role', 'admin')
        assert manager.get_metadata(cid, 'role') == 'admin'

    async def test_set_metadata_nonexistent_raises(self, manager):
        with pytest.raises(KeyError):
            manager.set_metadata('ghost', 'k', 'v')

    async def test_get_metadata_default(self, manager):
        ws = _make_ws()
        cid = await manager.connect(ws)
        assert manager.get_metadata(cid, 'missing', default='fallback') == 'fallback'

    async def test_get_all_metadata(self, manager):
        ws = _make_ws()
        cid = await manager.connect(ws, metadata={'a': 1, 'b': 2})
        assert manager.get_all_metadata(cid) == {'a': 1, 'b': 2}

    async def test_metadata_isolation(self, manager):
        """各连接的元数据相互独立"""
        ws1, ws2 = _make_ws(), _make_ws()
        cid1 = await manager.connect(ws1, metadata={'x': 'alice'})
        cid2 = await manager.connect(ws2, metadata={'x': 'bob'})
        assert manager.get_metadata(cid1, 'x') == 'alice'
        assert manager.get_metadata(cid2, 'x') == 'bob'


# ──────────────────────────────────────────────
# 心跳
# ──────────────────────────────────────────────
class TestHeartbeat:
    async def test_ping_returns_true(self, manager):
        ws = _make_ws()
        cid = await manager.connect(ws)
        result = await manager.ping(cid)
        assert result is True
        ws.send_bytes.assert_called_once_with(b'')

    async def test_ping_nonexistent_returns_false(self, manager):
        result = await manager.ping('ghost')
        assert result is False

    async def test_update_heartbeat(self, manager):
        ws = _make_ws()
        cid = await manager.connect(ws)
        old_ts = manager._last_seen[cid]
        time.sleep(0.01)
        manager.update_heartbeat(cid)
        assert manager._last_seen[cid] >= old_ts

    async def test_get_stale_connections(self, manager):
        ws = _make_ws()
        cid = await manager.connect(ws)
        # 强制设置为一个很久前的时间
        manager._last_seen[cid] = time.monotonic() - 999
        stale = manager.get_stale_connections(timeout_seconds=10)
        assert cid in stale

    async def test_no_stale_connections(self, manager):
        ws = _make_ws()
        await manager.connect(ws)
        stale = manager.get_stale_connections(timeout_seconds=9999)
        assert stale == []


# ──────────────────────────────────────────────
# 魔术方法 & 属性
# ──────────────────────────────────────────────
class TestDunderMethods:
    async def test_len(self, manager):
        assert len(manager) == 0
        ws = _make_ws()
        await manager.connect(ws)
        assert len(manager) == 1

    async def test_contains(self, manager):
        ws = _make_ws()
        cid = await manager.connect(ws)
        assert cid in manager
        assert 'nope' not in manager

    async def test_repr(self, manager):
        ws = _make_ws()
        await manager.connect(ws, group='room')
        text = repr(manager)
        assert 'WSConnectionManager' in text
        assert 'active=1' in text

    def test_groups_property(self, manager):
        assert isinstance(manager.groups, list)

# ──────────────────────────────────────────────
# Redis Pub/Sub分布式广播测试
# ──────────────────────────────────────────────
class TestRedisBroadcast:
    @pytest.mark.asyncio
    @patch('lumary.ws.connect_manager.REDIS_INSTALLED', False)
    async def test_init_redis_raises_when_not_installed(self, manager):
        with pytest.raises(RuntimeError, match='未安装redis依赖'):
            await manager.init_redis('redis://localhost')

    @pytest.mark.asyncio
    @patch('lumary.ws.connect_manager.REDIS_INSTALLED', True)
    @patch('lumary.ws.connect_manager.aioredis')
    async def test_init_close_redis(self, mock_aioredis, manager):
        mock_redis = AsyncMock()
        mock_pubsub = AsyncMock()
        mock_redis.pubsub.return_value = mock_pubsub
        mock_aioredis.from_url.return_value = mock_redis
        
        await manager.init_redis('redis://localhost', 'test_channel')
        
        mock_aioredis.from_url.assert_called_once_with('redis://localhost', decode_responses=True)
        mock_pubsub.subscribe.assert_called_once_with('test_channel')
        assert manager._listen_task is not None
        
        await manager.close_redis()
        mock_pubsub.unsubscribe.assert_called_once_with('test_channel')
        mock_pubsub.close.assert_called_once()
        mock_redis.close.assert_called_once()
        assert manager._listen_task.cancelled()

    @pytest.mark.asyncio
    @patch('lumary.ws.connect_manager.REDIS_INSTALLED', True)
    @patch('lumary.ws.connect_manager.aioredis')
    async def test_redis_broadcast_text(self, mock_aioredis, manager):
        mock_redis = AsyncMock()
        mock_aioredis.from_url.return_value = mock_redis
        await manager.init_redis('redis://localhost')
        
        await manager.broadcast_text('hello redis', group='group1', exclude={'c1'})
        
        mock_redis.publish.assert_called_once()
        args, kwargs = mock_redis.publish.call_args
        assert args[0] == 'lumary_ws_broadcast'
        import json
        payload = json.loads(args[1])
        assert payload['sender_id'] == manager._instance_id
        assert payload['type'] == 'text'
        assert payload['content'] == 'hello redis'
        assert payload['group'] == 'group1'
        assert payload['exclude'] == ['c1']
        
        await manager.close_redis()
