# Lumary (企业级 FastAPI 基础框架)

Lumary 是一个基于 **FastAPI** 和 **Pydantic V2** 构建的高标准、生产级 Python Web 基础框架。它不仅提供了一套极其严苛的代码规范，还为开发者屏蔽了大量底层复杂的封装细节，实现了真正的“开箱即用”与“极致开发者体验（DX）”。

## ✨ 核心特性 (Key Features)

### 📦 1. 极致无侵入的自动响应包装 (Auto Response Wrapper)
彻底告别繁琐的 `return {"code": 0, "data": ...}`。
通过底层的 `LumaryRoute` 拦截器，开发者只需在路由函数中直接返回业务模型，框架会在序列化前自动将其包装为企业级的 `APIResponse`，并且 **完美支持 Swagger OpenAPI Schema 推导**！
- 支持普通数据直接返回。
- 支持 `return data, extra` 元组自动解包并生成带有扩展字段的结构。
- 智能防重复包装，支持字典与 `Response` 对象的透明放行。

### 🔗 2. 全链路 Request ID 追踪 (Traceability)
基于 Python `contextvars` 实现协程安全的请求上下文管理。
框架在入口中间件自动生成（或提取）`X-Request-ID`，并将其无感注入到：
- 每一条业务日志中（结合 `logging.Filter`）。
- 每一个 API 接口的统一响应体中 (`APIResponse.request_id`)。

### 🛡️ 3. Pydantic V2 深度适配与全局序列化
完美迁移至 Pydantic V2 标准。
- 摒弃了被弃用的 `json_encoders`，采用 `@model_serializer(mode='wrap')` 实现了全局时间字段（`datetime`）的递归格式化（`YYYY-MM-DD HH:MM:SS`）。
- 严格遵循 `Field` 定义与默认值约束。

### 🗄️ 4. 生产级异步 ORM 与 CRUD 泛型
基于 `SQLAlchemy 2.0` 的纯异步架构：
- **安全第一**：修复了连接池与 Session 泄漏隐患（采用 AsyncGenerator 生命周期）。
- **泛型 CRUD**：内置高度封装的 `CRUDBase`，支持自动分页 (`PageData`)、多条件查询、动态排序。
- **高级 Mixin**：内置 `SoftDeleteMixin`（软删除）与 `AuditMixin`（审计字段），自动在查询时过滤已软删除数据。

### 🚨 5. 异常收敛与统一错误链路
重构全局异常处理器（Exception Handlers），将 Pydantic 校验错误（`RequestValidationError`）和系统底层异常转化为标准的 `HTTPException`，再交由底层统一格式化，确保所有报错格式 100% 统一。

### 📏 6. 强迫症级的代码规范
全面遵循极其严苛的 `CODING_STANDARDS.md`：
- `import` 语句严格按照代码中被**首次调用**的顺序排列。
- 极简的 Google 风格 Docstring（仅包含纯文本描述，剥离冗余的类型标注）。

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
使用原生的 `APIRouter`，并注入 `LumaryRoute` 即可专注于业务逻辑：

```python
from fastapi import FastAPI, APIRouter
from lumary import WrapAPIRoute
from pydantic import BaseModel


class UserOut(BaseModel):
    name: str
    age: int


# 实例化 APIRouter 并绑定 LumaryRoute 拦截器，它会自动包装响应
router = APIRouter(prefix="/users", tags=["用户模块"], route_class=WrapAPIRoute)


@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: int):
    # 直接返回数据模型，底层会自动包装！
    return UserOut(name="张三", age=25)
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
├── common/             # 公共组件 (日志、工具、上下文)
├── db/                 # 数据库封装 (SQLAlchemy, Mixins, CRUD基类)
├── ws/                 # WebSocket 管理器
├── application.py      # Lumary 核心 App 封装
├── exceptions.py       # 统一业务与 HTTP 异常基类
├── handlers.py         # 全局异常拦截与格式化转换
├── lifespan.py         # 异步生命周期管理与事件钩子
├── middleware.py       # 核心中间件 (Request ID 注入等)
├── router.py           # 自动响应包装器 (LumaryRoute)
└── schemas.py          # 全局通用数据模型与响应体配置
```
