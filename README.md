# Lumary (企业级 FastAPI 基础框架)

Lumary 是一个基于 **FastAPI** 和 **Pydantic V2** 构建的高标准、生产级 Python Web 基础框架。它不仅提供了一套极其严苛的代码规范，还为开发者屏蔽了大量底层复杂的封装细节，实现了真正的“开箱即用”与“极致开发者体验（DX）”。

## ✨ 核心特性 (Key Features)

### 📦 1. 标准化 API 响应规范
框架推荐采用统一的 `APIResponse` 结构来向客户端返回业务数据。通过全局 `SchemaBase` 的强契约约束，所有的 API 响应都天然支持：
- 自动提取并注入 `X-Request-ID`。
- 业务状态码 (`code`) 与提示信息 (`message`)。
- 高度扩展性 (`extra` 字段)。

### 🔗 2. 全链路 Request ID 追踪 (Traceability)
基于 Python `contextvars` 实现协程安全的请求上下文管理。
框架在入口中间件自动生成（或提取）`X-Request-ID`，并将其无感注入到：
- 每一条业务日志中（结合 `logging.Filter`）。
- 每一个 API 接口的统一响应体中 (`APIResponse.request_id`)。

### 🛡️ 3. Pydantic V2 深度适配与全局 PascalCase 响应
完美迁移至 Pydantic V2 标准。
- 内置 `alias_generator=to_pascal`，**全框架 API 响应默认采用大写驼峰 (PascalCase)**，高度契合企业级前端契约标准（例如 `RequestId`, `Data`, `Message`）。
- 采用 `@model_serializer(mode='wrap')` 实现了全局时间字段（`datetime`）的递归格式化（`YYYY-MM-DD HH:MM:SS`）。
- 严格遵循 `Field` 定义与默认值约束。

### 🗄️ 4. 生产级异步 ORM 与 CRUD 泛型
基于 `SQLAlchemy 2.0` 的纯异步架构：
- **安全第一**：修复了连接池与 Session 泄漏隐患（采用 AsyncGenerator 生命周期）。
- **极速批量操作**：原生 SQL 级 `update_multi` / `remove_multi` 避开实例化开销。
- **延迟初始化支持**：采用 `init(engine)` 模式延迟绑定会话，确保模块加载阶段装饰器可安全使用。
- **泛型 CRUD**：内置高度封装的 `CRUDBase`，支持自动分页 (`PageData`)、多条件查询、动态排序。
- **高级 Mixin**：内置 `SoftDeleteMixin`（软删除）与 `AuditMixin`（审计字段），自动在查询时过滤已软删除数据。

### 🚨 5. 异常收敛与统一错误链路
重构全局异常处理器（Exception Handlers），将 Pydantic 校验错误（`RequestValidationError`）和系统底层异常转化为标准的 `HTTPException`，再交由底层统一格式化，确保所有报错格式 100% 统一，并附带针对 `/metrics` 等监控接口的自动日志降级能力。

### 🌐 6. Paho-MQTT 与 WebSocket 稳健集成
- **WebSocket**：提供 `WSConnectionManager`，内置异常隔离机制，阻断单客户端断连引发的广播雪崩。
- **MQTT**：全面重构为原生 `paho-mqtt`，利用底层 C 扩展级守护线程结合 FastAPI 异步事件循环 (`run_coroutine_threadsafe`)，实现百万级安全跨线程消息投递。

---

## 🚀 快速开始 (Quick Start)

### 1. 安装 (Installation)
确保你的环境是 Python 3.10+，根据你的业务需求选择合适的安装方式：

```bash
# 最小安装（仅核心功能，无数据库依赖）
pip install lumary

# 仅 SQLAlchemy[asyncio] 支持（包含 python-ulid）
pip install lumary[sqlalchemy]

# 标准安装（包含核心功能 + SQLAlchemy支持 + 配置管理 pydantic-settings + 多文件上传 python-multipart）
pip install lumary[standard]
```

*如果你是下载源码进行本地开发，可以使用 `pip install -e .[standard]`。*

### 2. 编写业务路由
使用原生的 `APIRouter`，并直接返回标准化的 `APIResponse`：

```python
from fastapi import APIRouter
from pydantic import BaseModel
from lumary.schemas import APIResponse, response_success


class UserOut(BaseModel):
    name: str
    age: int


router = APIRouter(prefix="/users", tags=["用户模块"])


@router.get("/{user_id}", response_model=APIResponse[UserOut, None])
async def get_user(user_id: int):
    # 使用框架提供的 response_success 快捷方法返回标准响应
    user_data = UserOut(name="张三", age=25)
    return response_success(data=user_data)
```

### 3. 挂载并启动应用
```python
from lumary import Lumary

# 使用封装好的 Lumary App
app = Lumary(
    title="我的企业级应用",
    version="1.0.0",
    debug=True
)

app.include_router(router)

# 实际的 API 响应结果：
# {
#   "request_id": "01J2X...",
#   "code": 0,
#   "message": "成功",
#   "data": {
#     "name": "张三",
#     "age": 25
#   }
# }
```

---

## 📂 核心目录结构

```text
lumary/
├── common/             # 公共组件
│   ├── base/           # 基础模式 (单例等)
│   ├── utils/          # 实用工具 (时间处理、字符串、高性能序列化)
│   ├── cache.py        # 缓存管理器 (支持内存/Redis/文件)
│   └── mqtt.py         # MQTT 客户端管理器
├── db/                 # 数据库封装
│   └── sa/             # SQLAlchemy 2.0 异步封装
│       ├── base.py     # Base 元类
│       ├── crud.py     # 泛型 CRUD 基类
│       ├── engine.py   # 异步引擎及主从路由
│       ├── mixins.py   # 常用 Mixins (软删除、审计等)
│       ├── model.py    # ORM 基础模型
│       └── session.py  # 会话工厂及路由服务注入
├── ws/                 # WebSocket 模块
│   ├── connect_manager.py  # 高性能连接与广播管理器
│   └── router.py       # WS 路由
├── application.py      # Lumary 核心 App 封装及子应用挂载
├── exceptions.py       # 统一业务与 HTTP 异常基类
├── handlers.py         # 全局异常拦截与格式化转换
├── lifespan.py         # 异步生命周期管理与事件钩子注册表
├── logger.py           # 增强型多进程日志轮转与格式化
├── middleware.py       # 核心中间件 (Request ID 提取/注入)
├── openapi.py          # OpenAPI/Swagger 自定义渲染 (注入 4XX/500 错误)
└── schemas.py          # 全局通用数据模型 (APIResponse, PageData 等)
```
