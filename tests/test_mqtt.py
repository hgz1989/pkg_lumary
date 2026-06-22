"""
@Author     : zarkhan
@CreateDate : 2026/6/21
@Description: MQTT模块测试（包含平滑降级）
"""
import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

import lumary.common.mqtt as mqtt_module
from lumary.common.mqtt import MqttManager, topic_matches


@pytest.fixture
def mock_missing_aiomqtt():
    """模拟未安装aiomqtt库的环境"""
    import sys
    mqtt_module = sys.modules['lumary.common.mqtt']
    orig_mqtt_installed = mqtt_module.MQTT_INSTALLED
    mqtt_module.MQTT_INSTALLED = False
    yield
    mqtt_module.MQTT_INSTALLED = orig_mqtt_installed


def test_topic_matches():
    """测试主题匹配规则"""
    assert topic_matches('sensor/+/temp', 'sensor/room1/temp') is True
    assert topic_matches('sensor/+/temp', 'sensor/room1/humidity') is False
    assert topic_matches('sensor/#', 'sensor/room1/temp/1') is True
    assert topic_matches('sensor/room1/temp', 'sensor/room1/temp') is True
    assert topic_matches('sensor/+/temp', 'sensor/room1/temp/extra') is False


@pytest.mark.asyncio
async def test_mqtt_manager_missing_dependency_fallback(mock_missing_aiomqtt):
    """测试未安装aiomqtt时，MQTT管理器平滑降级（静默空跑）"""
    manager = MqttManager()
    
    # 未安装时init应该抛出RuntimeError
    with pytest.raises(RuntimeError, match='未安装aiomqtt依赖'):
        await manager.init('localhost')
        
    assert manager.enabled is False
    
    # 装饰器应能正常挂载（不报错）
    @manager.on_message('test/topic')
    async def dummy_handler(topic, payload):
        pass
        
    assert 'test/topic' in manager.handlers
    assert len(manager.handlers['test/topic']) == 1
    
    # 发布消息不应该抛出异常
    await manager.publish('test/topic', {'data': 123})
    
    # close不应该抛出异常
    await manager.close()
