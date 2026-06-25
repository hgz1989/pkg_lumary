"""
@Author     : zarkhan
@CreateDate : 2026/6/22
@Description: 调试与演示专用入口
"""
import asyncio
from datetime import datetime
from typing import Type, AsyncGenerator, Any

from fastapi import HTTPException, WebSocket, WebSocketDisconnect, Depends
from pydantic import BaseModel, Field
from sqlalchemy import String, Integer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from lumary import Lumary, on_startup, on_shutdown, Response
from lumary.common import cache, cache_response, mqtt_client
from lumary.db.sqlalchemy import ModelBase, CRUDBase, create_db_engine, SessionFactory
from lumary.schemas import (
    SchemaBase,
    APIResponse,
    PageData,
    response_success
)
from lumary.ws.connect_manager import WSConnectionManager

# ──────────────────────────────────────────────
# 初始化应用
# ──────────────────────────────────────────────
app = Lumary(debug=True, title="Lumary 接口调试服务")

# ──────────────────────────────────────────────
# 数据库模块初始化 (SQLite 内存数据库)
# ──────────────────────────────────────────────
db_engine = create_db_engine("sqlite+aiosqlite:///:memory:")
session_factory = SessionFactory(db_engine)


class DemoUserModel(ModelBase):
    """测试用数据库表模型"""
    __tablename__ = "demo_users"

    __table_args__ = {'extend_existing': True}
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), index=True)
    age: Mapped[int] = mapped_column(Integer)


class DemoUserCreate(SchemaBase):
    username: str
    age: int


class DemoUserUpdate(SchemaBase):
    username: str | None = None
    age: int | None = None


class DemoUserCRUD(CRUDBase[DemoUserModel, DemoUserCreate, DemoUserUpdate]):
    """测试用CRUD操作类"""
    model = DemoUserModel


# ──────────────────────────────────────────────
# WebSocket 模块初始化
# ──────────────────────────────────────────────
ws_manager = WSConnectionManager()


async def cpu_burner():
    """模拟持续的 CPU 占用，用于展示 /system/metrics 的 cpu_percent"""
    while True:
        # 简单计算耗时操作，但不完全阻塞事件循环
        for _ in range(500):
            _ = sum([i * i for i in range(100)])
        await asyncio.sleep(0.05)


# ──────────────────────────────────────────────
# 生命周期事件
# ──────────────────────────────────────────────
_bg_tasks = []


@on_startup
async def setup_all():
    """统一的启动事件处理"""
    # 启动后台 CPU 占用任务
    task = asyncio.create_task(cpu_burner())
    _bg_tasks.append(task)
    # 1. 初始化数据库表结构
    async with db_engine.begin() as conn:
        await conn.run_sync(ModelBase.metadata.create_all)
        print("SQLite 内存数据库表创建成功")

    # 2. 尝试初始化 Redis 缓存
    try:
        # 使用纯内存缓存，确保无 Redis 依赖也能极速响应
        await cache.init(None)
    except Exception as e:
        print(f"Redis 缓存未启动或未安装，已自动降级为内存模式: {e}")

    # 3. 尝试初始化 MQTT 客户端
    try:
        await mqtt_client.init("broker.emqx.io", port=1883, client_id=f"lumary_debug_{datetime.now().timestamp()}")
    except Exception as e:
        print(f"MQTT 客户端未启动或未安装，已自动降级: {e}")


@on_shutdown
async def teardown_all():
    """统一的关闭事件处理"""
    for task in _bg_tasks:
        task.cancel()
    await mqtt_client.close()
    await cache.close()


# 注册 MQTT 消息回调
@mqtt_client.on_message("lumary/debug/#")
async def on_debug_message(topic: str, payload: str):
    """当收到匹配主题的消息时自动触发"""
    print(f"\n[MQTT 收到消息] Topic: {topic} | Payload: {payload}\n")


# ──────────────────────────────────────────────
# 路由接口定义 - 基础响应测试
# ──────────────────────────────────────────────
class UserOut(SchemaBase):
    id: int
    username: str
    created_at: datetime


class PaginationExtra(SchemaBase):
    has_next: bool
    cursor: str


@app.get("/users/standard", summary="1. 标准响应测试", response_model=APIResponse[UserOut, Any])
async def get_standard_response(resp: Response):
    """测试不带扩展信息的标准业务响应"""
    user = UserOut(id=1, username="zarkhan", created_at=datetime.now())
    resp.headers["X-Request-Id"] = "123456789"
    return response_success(message="用户获取成功", data=user)


@app.get("/users/extra", summary="2. 带扩展响应测试",
         response_model=APIResponse[PageData[UserOut], PaginationExtra])
async def get_extra_response():
    """测试带有额外扩展信息的业务响应"""
    users_list = [
        UserOut(id=1, username="user1", created_at=datetime.now()),
        UserOut(id=2, username="user2", created_at=datetime.now())
    ]
    page_data = PageData.build(items=users_list, page=1, size=10, total=2)
    extra_info = PaginationExtra(has_next=False, cursor="eyJpZCI6Mn0=")
    return response_success(message="用户列表获取成功", data=page_data, extra=extra_info)


# ──────────────────────────────────────────────
# 路由接口定义 - 全局异常测试
# ──────────────────────────────────────────────
class UserCreate(SchemaBase):
    username: str = Field( min_length=3, max_length=20, description="用户名")
    age: int = Field(..., ge=0, le=120, description="年龄")


@app.post("/errors/validation", summary="3. 参数校验异常测试", response_model=APIResponse)
async def trigger_validation_error(payload: UserCreate):
    """测试 Pydantic 参数校验异常（传入非法参数触发）"""
    return response_success(message="参数校验通过", data=payload)


@app.get("/errors/http", summary="4. HTTP 协议异常测试")
async def trigger_http_error(trigger: bool = True):
    """测试手动抛出 HTTP 异常"""
    if trigger:
        # 演示抛出带有字典结构的异常，会被框架自动提取为 extra
        raise HTTPException(
            status_code=403,
            detail={
                "message": "没有权限执行此操作",
                "need_role": "admin",
                "retry": False
            }
        )
    return response_success(message="正常访问")


@app.get("/errors/internal", summary="5. 系统内部异常测试")
async def trigger_internal_error():
    """测试未被捕获的系统内部异常"""
    return 1 / 0


# ──────────────────────────────────────────────
# 路由接口定义 - 缓存测试
# ──────────────────────────────────────────────
@app.get("/cache/decorator", summary="6. 装饰器缓存测试", response_model=APIResponse[UserOut, Type[None]])
@cache_response(namespace="debug_users", expire=60)
async def get_cached_user(user_id: int):
    """测试 @cache_response 装饰器 (第二次请求将瞬间返回)"""
    await asyncio.sleep(2)
    user = UserOut(id=user_id, username=f"cached_user_{user_id}", created_at=datetime.now())
    return response_success(message="执行了真实逻辑", data=user)


@app.post("/cache/clear", summary="7. 清理缓存")
async def clear_cache(namespace: str = "debug_users"):
    """清理指定 namespace 下的所有缓存"""
    await cache.clear_namespace(namespace)
    return response_success(message=f"命名空间 {namespace} 缓存已清理")


# ──────────────────────────────────────────────
# 路由接口定义 - MQTT 测试
# ──────────────────────────────────────────────
class MQTTPayload(BaseModel):
    topic: str = Field(default="lumary/debug/test")
    message: str = Field(default="Hello Lumary MQTT!")


@app.post("/mqtt/publish", summary="8. MQTT 消息发布测试")
async def publish_mqtt_message(payload: MQTTPayload):
    """向指定的 Topic 发布消息，控制台将打印接收日志"""
    if not mqtt_client.enabled:
        return response_success(message="MQTT 客户端未连接")
    await mqtt_client.publish(payload.topic, payload.message)
    return response_success(message=f"消息已发送至 {payload.topic}")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with session_factory.get_session() as db:
        yield db


# ──────────────────────────────────────────────
# 路由接口定义 - 数据库 CRUD 测试
# ──────────────────────────────────────────────
@app.post("/db/users", summary="9. 数据库 - 创建用户")
async def db_create_user(username: str, age: int, db: AsyncSession = Depends(get_db)):
    """在 SQLite 内存数据库中创建一条用户记录"""
    demo_crud = DemoUserCRUD(db)
    user = await demo_crud.create(obj_in={"username": username, "age": age})
    await db.commit()
    return response_success(message="创建成功", data={"id": user.id, "username": user.username, "age": user.age})


@app.get("/db/users", summary="10. 数据库 - 获取用户列表")
async def db_get_users(db: AsyncSession = Depends(get_db)):
    """获取 SQLite 内存数据库中的所有用户记录"""
    demo_crud = DemoUserCRUD(db)
    users = await demo_crud.get_multi()
    return response_success(message="获取成功",
                            data=[{"id": u.id, "username": u.username, "age": u.age} for u in users])


# ──────────────────────────────────────────────
# 路由接口定义 - WebSocket 测试
# ──────────────────────────────────────────────
@app.websocket("/ws/chat")
async def websocket_endpoint(ws: WebSocket):
    """
    11. WebSocket 测试端点
    连接后发送任意 JSON，如 `{"msg": "hello"}`，管理器会广播给同组所有连接
    """
    async with ws_manager.lifespan(ws, group="debug_chat") as cid:
        try:
            while True:
                data = await ws.receive_json()
                await ws_manager.broadcast_json(
                    {"sender": cid, "message": data},
                    group="debug_chat"
                )
        except WebSocketDisconnect:
            pass


@app.post("/ws/broadcast", summary="12. WebSocket - 服务端广播")
async def ws_broadcast_message(msg: str = "系统通知"):
    """测试通过 HTTP 接口主动向 WebSocket 组广播消息"""
    await ws_manager.broadcast_json({"system_msg": msg}, group="debug_chat")
    return response_success(message="广播发送成功")


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host='0.0.0.0', port=8000, log_config=None)
