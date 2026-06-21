"""
@Author     : zarkhan
@CreateDate : 2026/6/21
@Description: MQTT 客户端与路由管理器测试
"""
import asyncio
import pytest

from lumary.common.mqtt import topic_matches, mqtt_client


def test_topic_matches():
    """测试 MQTT 通配符主题匹配逻辑"""
    # 精确匹配
    assert topic_matches('sensor/temp', 'sensor/temp')
    assert not topic_matches('sensor/temp', 'sensor/humidity')

    # 单层级通配符 +
    assert topic_matches('sensor/+/temp', 'sensor/room1/temp')
    assert topic_matches('sensor/+/temp', 'sensor/room2/temp')
    assert not topic_matches('sensor/+/temp', 'sensor/room1/humidity')
    assert not topic_matches('sensor/+/temp', 'sensor/room1/zone1/temp')

    # 多层级通配符 #
    assert topic_matches('sensor/#', 'sensor/room1/temp')
    assert topic_matches('sensor/#', 'sensor/room1')
    assert topic_matches('sensor/#', 'sensor')
    assert not topic_matches('sensor/#', 'system/room1')

    # 混合通配符
    assert topic_matches('+/+/temp', 'building1/room1/temp')
    assert topic_matches('+/#', 'building1/room1/temp')


@pytest.mark.asyncio
async def test_mqtt_manager_fallback():
    """测试未配置或未安装 aiomqtt 时的方法调用不会报错"""
    # 强制标记为未启用
    mqtt_client.enabled = False

    # 绑定多个处理函数到同一个主题
    @mqtt_client.on_message('sensor/+')
    async def handle_sensor_1(topic, payload):
        pass

    @mqtt_client.on_message('sensor/+')
    async def handle_sensor_2(topic, payload):
        pass

    assert len(mqtt_client.handlers['sensor/+']) == 2

    # 全部调用一遍，如果报错则测试不通过
    await mqtt_client.publish('sensor/temp', {'data': 123})
    await mqtt_client.close()

    # 清理注册的 handlers 避免影响其他测试
    mqtt_client.handlers.clear()
