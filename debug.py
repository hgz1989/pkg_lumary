"""
@Author     : zarkhan
@CreateDate : 2026/6/22
@Description: 调试与演示专用入口
"""
from datetime import datetime
from fastapi import HTTPException
from pydantic import BaseModel, Field

from lumary import Lumary, on_startup, on_shutdown
from lumary.common.cache import cache, cache_response
from lumary.common.mqtt import mqtt_client
from lumary.schemas import (
    APIResponse,
    APIResponseWithExtra,
    PageData,
    response_success,
    response_with_extra_success
)

app = Lumary(debug=True, title="Lumary 接口调试服务")

@on_startup
async def setup_cache():
    """尝试在启动时初始化 Redis 缓存，方便测试缓存装饰器"""
    try:
        # 如果你本地没有运行 Redis，这行会静默失败或降级，不影响主流程
        await cache.init("redis://localhost:6379/0")
    except Exception as e:
        print(f"Redis 缓存未启动或未安装，已自动降级为空跑模式: {e}")


@on_startup
async def setup_mqtt():
    """尝试在启动时初始化 MQTT 客户端，用于测试收发消息"""
    try:
        # 使用公共免费的测试 Broker (broker.emqx.io)
        # 注意: 如果网络连不通会静默降级
        await mqtt_client.init("broker.emqx.io", port=1883, client_id=f"lumary_debug_{datetime.now().timestamp()}")
    except Exception as e:
        print(f"MQTT 客户端未启动或未安装，已自动降级: {e}")

@on_shutdown
async def teardown_mqtt():
    """在服务关闭时安全断开 MQTT"""
    await mqtt_client.close()


# 注册一个全局的 MQTT 消息回调，用于接收测试主题的消息
@mqtt_client.on_message("lumary/debug/#")
async def on_debug_message(topic: str, payload: str):
    """当收到匹配 `lumary/debug/#` 主题的消息时，此函数会被自动触发"""
    print(f"\n[MQTT 收到消息] Topic: {topic} | Payload: {payload}\n")


# ──────────────────────────────────────────────
# 模拟数据模型定义
# ──────────────────────────────────────────────

class UserOut(BaseModel):
    """用户信息输出模型"""
    id: int
    username: str
    created_at: datetime


class PaginationExtra(BaseModel):
    """自定义分页游标扩展信息"""
    has_next: bool
    cursor: str


# ──────────────────────────────────────────────
# 路由接口定义
# ──────────────────────────────────────────────

@app.get("/users/standard", summary="标准响应测试", response_model=APIResponse[UserOut])
async def get_standard_response():
    """
    测试不带扩展信息的标准业务响应
    直接返回 APIResponse[T]
    """
    user = UserOut(
        id=1, 
        username="zarkhan", 
        created_at=datetime.now()
    )
    
    return response_success(
        message="用户获取成功", 
        data=user
    )


@app.get("/users/extra", summary="带扩展响应测试", response_model=APIResponseWithExtra[PageData[UserOut], PaginationExtra])
async def get_extra_response():
    """
    测试带有额外扩展信息的业务响应
    返回 APIResponseWithExtra[T, E]，常用于游标分页或附加统计数据的场景
    """
    users_list = [
        UserOut(id=1, username="user1", created_at=datetime.now()),
        UserOut(id=2, username="user2", created_at=datetime.now())
    ]
    
    # 构建分页外层数据
    page_data = PageData.build(
        items=users_list,
        page=1,
        size=10,
        total=2
    )
    
    # 构建自定义扩展信息
    extra_info = PaginationExtra(
        has_next=False,
        cursor="eyJpZCI6Mn0="
    )
    
    return response_with_extra_success(
        message="用户列表及扩展信息获取成功",
        data=page_data,
        extra=extra_info
    )


# ──────────────────────────────────────────────
# 全局异常处理测试接口
# ──────────────────────────────────────────────

class UserCreate(BaseModel):
    """用户创建输入模型"""
    username: str = Field(..., min_length=3, max_length=20, description="用户名（长度3-20）")
    age: int = Field(..., ge=0, le=120, description="年龄（0-120）")


@app.post("/errors/validation", summary="1. 参数校验异常测试 (RequestValidationError)")
async def trigger_validation_error(payload: UserCreate):
    """
    测试 Pydantic 参数校验异常。
    请在 Swagger UI 中尝试传入非法的参数（例如 age=-1、username过短 或 缺少必填字段）。
    """
    return response_success(message="参数校验通过", data=payload)


@app.get("/errors/http", summary="2. HTTP 协议异常测试 (HTTPException)")
async def trigger_http_error(trigger: bool = True):
    """
    测试手动抛出 HTTP 异常。
    当 trigger=true 时，主动抛出 403 HTTPException，框架会自动拦截并转为标准 JSON 响应。
    """
    if trigger:
        raise HTTPException(
            status_code=403, 
            detail="您没有权限执行此操作，请联系管理员申请权限",
            headers={"X-Error-Reason": "Permission Denied"}
        )
    return response_success(message="正常访问")


@app.get("/errors/internal", summary="3. 系统内部异常测试 (Exception兜底)")
async def trigger_internal_error():
    """
    测试未被捕获的系统内部异常。
    这里故意触发一个除零错误 (ZeroDivisionError)，将触发 500 兜底处理，同时终端会打印 Critical 堆栈。
    """
    # 故意制造一个 Python 运行时内部异常
    return 1 / 0


# ──────────────────────────────────────────────
# 缓存系统测试接口
# ──────────────────────────────────────────────

@app.get("/cache/decorator", summary="1. 装饰器缓存测试", response_model=APIResponse[UserOut])
@cache_response(namespace="debug_users", expire=60)
async def get_cached_user(user_id: int):
    """
    测试 @cache_response 装饰器。
    
    第一次请求会等待 2 秒并返回数据。
    如果你本地启动了 Redis，第二次使用相同的 user_id 请求时，将会瞬间返回缓存数据！
    如果未安装 Redis，则每次都会等待 2 秒。
    """
    import asyncio
    await asyncio.sleep(2)
    user = UserOut(
        id=user_id,
        username=f"cached_user_{user_id}",
        created_at=datetime.now()
    )
    return response_success(message="用户获取成功（执行了真实逻辑）", data=user)


@app.post("/cache/clear", summary="2. 清理命名空间缓存")
async def clear_cache(namespace: str = "debug_users"):
    """
    测试手动清理某个命名空间下的所有缓存。
    
    执行此接口后，指定 namespace 下的所有接口缓存将失效。
    再次请求 /cache/decorator 时会重新执行并耗时 2 秒。
    """
    await cache.clear_namespace(namespace)
    return response_success(message=f"命名空间 {namespace} 缓存清理成功")


# ──────────────────────────────────────────────
# MQTT 系统测试接口
# ──────────────────────────────────────────────

class MQTTPayload(BaseModel):
    topic: str = Field(default="lumary/debug/test", description="发布的目标主题")
    message: str = Field(default="Hello Lumary MQTT!", description="发布的消息内容")

@app.post("/mqtt/publish", summary="3. MQTT 消息发布测试")
async def publish_mqtt_message(payload: MQTTPayload):
    """
    测试 MQTT 消息发布。
    
    调用此接口将向指定的 Topic 发布一条消息。
    因为我们在代码上方使用 `@mqtt_client.on_message("lumary/debug/#")` 订阅了相关主题，
    所以如果你发布的主题以 `lumary/debug/` 开头，你会在控制台立刻看到接收打印！
    """
    if not mqtt_client.enabled:
        return response_success(message="MQTT 客户端未连接，已降级忽略发送")
        
    await mqtt_client.publish(payload.topic, payload.message)
    return response_success(message=f"消息已发送至 {payload.topic}")


if __name__ == '__main__':
    import uvicorn
    # 启动调试服务
    uvicorn.run(app, host='0.0.0.0', port=8000, log_config=None)
