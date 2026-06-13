# Lumary

基于 FastAPI 封装的生产级 Web 应用框架，开箱即用。

## 特性

- **应用封装** — `Lumary` 类继承 FastAPI，内置异常处理、CORS 中间件、自定义 OpenAPI 文档、健康检查
- **生命周期钩子** — `@on_startup` / `@on_shutdown` 装饰器，支持优先级排序与异常终止控制
- **统一响应格式** — `APIResponse`、`PageData`、`PageQuery` 等标准化 Schema，自动排除 None 字段
- **业务异常** — `BusinessException` 支持自定义错误码与消息，全局自动捕获并映射 HTTP 状态码
- **WebSocket 管理** — `WSConnectionManager` 支持分组、单播、广播、上下文管理器自动清理
- **SQLAlchemy 集成** — `ModelBase` 模型基类、`CRUDBase` 泛型 CRUD、`SoftDeleteMixin` 软删除（可选依赖）
- **子应用管控** — `mount_sub_apps` 一键挂载，禁止子应用嵌套
- **日志管理** — `setup_logger` 一键配置文件轮转日志，`set_log_level` / `set_log_format` 动态调整
- **工具函数** — 驼峰/下划线互转、随机字符串、高性能 JSON 序列化（orjson 加速）、日期时间运算
- **OpenAPI 优化** — 自动移除 `ValidationError` 和 HTTP 422 响应，生成更干净的 API 文档

## 安装

```bash
# 最小安装（仅核心，无数据库依赖）
pip install lumary

# 仅 SQLAlchemy[asyncio] 支持
pip install lumary[sqlalchemy]

# 标准安装（含 SQLAlchemy[asyncio] + pydantic-settings）
pip install lumary[standard]
```

## 快速开始

### 基础用法

```python
from lumary import Lumary, on_startup, on_shutdown

app = Lumary(title='My Project', debug=True)


@on_startup(priority=100)
async def connect_db():
    print('Database connected')


@on_shutdown
async def close_db():
    print('Database closed')
```

### WebSocket

```python
from fastapi import WebSocket
from lumary import Lumary
from lumary.ws import WSConnectionManager

app = Lumary(title='Chat')
manager = WSConnectionManager()


@app.websocket('/ws/{room}')
async def ws_endpoint(websocket: WebSocket, room: str):
    async with manager.lifespan(websocket, group=room) as cid:
        while True:
            data = await websocket.receive_json()
            await manager.broadcast_json(data, group=room, exclude={cid})
```

### 统一响应

```python
from lumary import Lumary, response_success, response_fail, APIResponse

app = Lumary()


@app.get('/users/{uid}')
async def get_user(uid: int) -> APIResponse:
    user = await fetch_user(uid)
    if not user:
        return response_fail(code=404, message='用户不存在')
    return response_success(data=user)
```

### 业务异常

```python
from lumary import BusinessException

async def transfer(from_id: int, to_id: int, amount: float):
    if amount <= 0:
        raise BusinessException(code=400, message='金额必须大于零')
```

### 子应用挂载

```python
from lumary import Lumary

app = Lumary(title='Gateway')

# 一键挂载 apps/ 目录下所有子应用
app.mount_sub_apps('./apps')
```

目录结构示例：

```text
apps/
├── user/
│   ├── __init__.py      # 暴露 user_app 实例
│   └── ...
└── order/
    ├── __init__.py      # 暴露 order_app 实例
    └── ...
```

子应用自动挂载到 `/{folder_name}` 路径（下划线转连字符），如 `user` → `/user`、`order_service` → `/order-service`。

### 数据库操作

> 需安装 `lumary[sqlalchemy]` 或 `lumary[standard]`

**模型定义**

```python
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from lumary.db.sqlalchemy import ModelBase
from lumary.common.mixins import SoftDeleteMixin

class User(ModelBase, SoftDeleteMixin):
    __tablename__ = 'user'

    name: Mapped[str] = mapped_column(
        String(50),
        comment='用户名'
    )
```

**引擎与工厂**

```python
from lumary.db.sqlalchemy import create_db_engine, SessionFactory

engine = create_db_engine('postgresql+asyncpg://user:pass@localhost/db')
factory = SessionFactory(engine)
```

**CRUD 操作**

```python
from lumary.db.sqlalchemy import CRUDBase

class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    model = User

async def create_user(db, data):
    crud = CRUDUser(db)
    user = await crud.create(obj_in=data)
    await db.commit()
    return user
```

### 日志配置

```python
from lumary.common import setup_logger, set_log_level, set_log_format

# 一键配置文件日志（按天轮转，保留 30 天）
setup_logger(log_dir='./logs', filename='app.log')

# 动态调整日志级别
set_log_level('info')

# 动态调整日志格式
set_log_format('%(asctime)s | %(levelname)s | %(message)s')
```

### 工具函数

```python
from lumary.common import (
    camel_to_snake,
    snake_to_camel,
    random_string,
    json_dumps,
    json_loads,
    add_datetime,
)

camel_to_snake('HelloWorld')   # 'hello_world'
snake_to_camel('hello_world')  # 'HelloWorld'
random_string(16)              # 'aB3xK9mQ7pL2nR5t'
json_dumps({'key': 'val'})     # 优先使用 orjson 加速
add_datetime(dt, months=3)     # 正确处理闰年和月份天数
```

## API 参考

### 应用核心 — `lumary`

#### `Lumary`

基于 FastAPI 封装的生产级 Web 应用类，集成异常处理、中间件、自定义文档、子应用管控、生命周期管理。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `debug` | `bool` | `False` | 是否启用调试模式。非调试模式自动关闭文档并设置 INFO 日志级别 |
| `title` | `str` | `'Lumary'` | 应用标题 |
| `summary` | `str` | `''` | 应用简介 |
| `description` | `str` | `''` | 应用描述 |
| `version` | `str` | 框架版本 | 应用版本 |
| `is_sub_app` | `bool` | `False` | 是否为子应用，子应用禁止嵌套挂载、自动清空 root_path 和 lifespan |
| `enable_cors` | `bool` | `True` | 是否启用 CORS 中间件 |
| `allow_origins` | `list[str] \| None` | `None` | 允许的源列表，默认 `['*']` |
| `allow_methods` | `list[str] \| None` | `None` | 允许的 HTTP 方法列表，默认 `['*']` |
| `allow_headers` | `list[str] \| None` | `None` | 允许的请求头列表，默认 `['*']` |
| `hook_registry` | `HookRegistry \| None` | `None` | 生命周期钩子注册表，为 None 时使用默认全局注册表 |

**实例方法：**

- **`mount(path, app, name=None)`** — 挂载单个子应用到指定路径，子应用上禁止调用此方法
- **`mount_sub_apps(apps_path='./apps')`** — 扫描目录并一键挂载所有子应用。自动跳过以下划线/点开头的目录以及 `__pycache__`、`tests`、`test`、`utils` 目录

**内置接口：**

- `GET /system/health` — 服务健康检查，返回 `SystemHealthOut`（name、version、debug）

---

### 生命周期 — `lumary.lifespan`

#### `on_startup(func=None, *, priority=50, abort_on_exception=True)`

注册服务启动生命周期钩子的装饰器。将初始化逻辑（数据库连接、数据预热等）分散到业务模块中，按 `priority` 降序执行。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `func` | `HookFunc \| None` | `None` | 挂载此装饰器的异步函数，支持无参或 `(app: FastAPI)` 单参 |
| `priority` | `int` | `50` | 优先级，值越大越早执行 |
| `abort_on_exception` | `bool` | `True` | 执行报错时是否抛出 `RuntimeError` 阻止启动 |

#### `on_shutdown(func=None, *, priority=50, abort_on_exception=False)`

注册服务关闭生命周期钩子的装饰器。将清理逻辑（释放连接池、刷新日志等）分散到业务模块中，按 `priority` 升序执行（与启动顺序相反）。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `func` | `HookFunc \| None` | `None` | 挂载此装饰器的异步函数，支持无参或 `(app: FastAPI)` 单参 |
| `priority` | `int` | `50` | 优先级，启动时越大的关闭时也应越大，它会越晚被清理 |
| `abort_on_exception` | `bool` | `False` | 报错时是否抛出异常，默认不中断全局清理 |

#### `clear_hooks()`

清空默认全局注册表中的所有钩子，用于测试隔离。

#### `HookRegistry`

生命周期钩子注册表类，管理启动和关闭阶段的钩子函数，支持优先级排序和去重。每个实例独立维护钩子列表，便于测试隔离和多实例部署。

**实例方法：**

- **`register_startup(func, priority, abort_on_exception)`** — 注册启动钩子，按优先级降序排列
- **`register_shutdown(func, priority, abort_on_exception)`** — 注册关闭钩子，按优先级升序排列
- **`on_startup(func=None, *, priority=50, abort_on_exception=True)`** — 实例级启动装饰器
- **`on_shutdown(func=None, *, priority=50, abort_on_exception=False)`** — 实例级关闭装饰器
- **`run_startup(app)`** — 异步执行所有启动钩子
- **`run_shutdown(app)`** — 异步执行所有关闭钩子
- **`clear()`** — 清空所有已注册的钩子

---

### 统一响应 — `lumary.schemas`

#### `SchemaBase`

全局 Pydantic Schema 基类，统一配置 `from_attributes=True`（ORM 兼容）、`populate_by_name=True`（别名支持）、`extra='ignore'`（忽略多余字段），并自动在序列化时排除 `None` 值。

#### `APIResponse[T]`

标准响应结构模型。

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `code` | `int` | `0` | 状态码，0 为成功，其他为错误 |
| `message` | `str` | `'Success'` | 提示信息 |
| `data` | `T \| None` | `None` | 响应数据 |

#### `PageData[T]`

通用分页响应数据模型。

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `page` | `int` | `1` | 当前页码 |
| `size` | `int` | `10` | 每页数量 |
| `total` | `int` | `0` | 总记录数 |
| `pages` | `int` | `0` | 总页数 |
| `items` | `Sequence[T] \| list[T]` | `[]` | 当前页数据列表 |

#### `PageQuery`

通用分页请求参数模型，适用于后台管理系统。

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `page` | `int` | `1` | 当前页码（≥1） |
| `size` | `int` | `10` | 每页数量（1~1000） |

#### `SystemHealthOut`

系统健康检查输出模型。

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `status` | `str` | `'OK'` | 系统状态 |
| `name` | `str` | `'Lumary'` | 系统名称 |
| `version` | `str` | 框架版本 | 系统版本 |
| `debug` | `bool` | `False` | 是否处于调试模式 |

#### `response_success(data=None, message='Success', code=200) -> APIResponse[T]`

快速构建成功响应。

#### `response_fail(code=40000, message='Fail', data=None) -> APIResponse[T]`

快速构建失败响应。

---

### 业务异常 — `lumary.exceptions`

#### `BusinessException(code, message, data=None)`

业务异常基类。在业务逻辑层主动抛出已知错误（参数不合法、资源不存在等），由全局拦截器捕获并返回统一 JSON 错误结构。错误码自动映射 HTTP 状态码：`4xxxx` → `4xx`、`5xxxx` → `5xx`。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `code` | `int` | 必填 | 业务错误码 |
| `message` | `str` | 必填 | 错误提示信息 |
| `data` | `Any` | `None` | 附加错误数据 |

**内置子类：**

| 异常类 | 默认错误码 | 默认消息 | 对应 HTTP |
|--------|-----------|----------|-----------|
| `UnauthorizedError` | 40100 | 未授权访问 | 401 |
| `ForbiddenError` | 40300 | 拒绝访问 | 403 |
| `NotFoundError` | 40400 | 资源不存在 | 404 |
| `ConflictError` | 40900 | 资源冲突 | 409 |

---

### WebSocket — `lumary.ws`

#### `WSConnectionManager`

WebSocket 连接管理器，管理所有活跃连接，支持分组隔离和消息推送。面向单事件循环设计，无需 asyncio.Lock。

**连接生命周期：**

- **`connect(websocket, *, connection_id=None, group=None) -> str`** — 接受并存储新连接，返回连接 ID（不传则自动生成 UUID）
- **`disconnect(connection_id)`** — 断开并移除指定连接，自动从所有分组中移除并安全关闭 WebSocket
- **`lifespan(websocket, *, connection_id=None, group=None) -> AsyncGenerator[str]`** — 上下文管理器方式管理连接生命周期，自动注册与注销，即使异常也能正确清理

**分组管理：**

- **`join_group(connection_id, group)`** — 将已有连接加入指定分组
- **`leave_group(connection_id, group)`** — 将连接从指定分组移除，不关闭连接，分组清空时自动清理

**单播：**

- **`send_text(connection_id, message)`** — 向指定连接发送文本消息
- **`send_json(connection_id, data)`** — 向指定连接发送 JSON 数据

**广播：**

- **`broadcast_text(message, *, group=None, exclude=None)`** — 广播文本消息，可按分组广播并排除指定连接
- **`broadcast_json(data, *, group=None, exclude=None)`** — 广播 JSON 数据，可按分组广播并排除指定连接

**查询属性：**

- **`active_count`** (property) — 当前活跃连接数
- **`groups`** (property) — 获取所有分组名称列表
- **`group_count(group)`** — 获取指定分组的连接数
- **`is_connected(connection_id)`** — 检查指定连接是否活跃
- **`len(manager)`** — 返回活跃连接数
- **`connection_id in manager`** — 检查连接是否存在

---

### 数据库 — `lumary.db.sqlalchemy`

#### `Base`

SQLAlchemy 2.0 声明式基类，继承 `DeclarativeBase`。所有 ORM 模型的最终基类。

#### `ModelBase`

ORM 模型基础类（继承 `Base`），提供通用字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `str(26)` | 基于 ULID 的主键，全局唯一、可按时间排序 |
| `created_at` | `datetime` | 创建时间，数据库自动填充 |
| `updated_at` | `datetime` | 更新时间，数据库自动更新 |

#### `SoftDeleteMixin` — `lumary.common.mixins`

软删除混入类，为模型提供逻辑删除能力：

| 字段 | 类型 | 说明 |
|------|------|------|
| `is_deleted` | `bool` | 是否已删除，默认 `False` |
| `deleted_at` | `datetime \| None` | 删除时间 |

#### `CRUDBase[ModelType, CreateSchemaType, UpdateSchemaType]`

CRUD 泛型基类，提供标准异步 CRUD 操作。子类必须显式定义 `model` 属性。构造函数接收 `db: AsyncSession`。

**查询方法：**

- **`get(obj_id, options=None)`** — 根据主键获取单条记录，不存在或已软删除时抛出 `NoResultFound`
- **`get_one(*, options=None, **kwargs)`** — 根据多个字段条件获取单条记录（AND 关系），自动过滤软删除
- **`get_multi(*criteria, skip=0, limit=100, order_by=None, options=None, **kwargs)`** — 获取多条记录，支持分页、条件过滤和排序，自动过滤软删除
- **`get_count(*criteria, options=None, **kwargs)`** — 统计符合条件的记录总数

**写入方法：**

- **`create(*, obj_in)`** — 创建新记录，自动过滤无效字段并 flush
- **`batch_create(*, objs_in, ignore_errors=False, return_objs=True)`** — 批量创建记录，支持忽略单条错误（唯一键冲突）
- **`update(*, db_obj, obj_in)`** — 更新已有记录，自动过滤无效字段
- **`soft_delete(*, obj_id)`** — 软删除记录（需模型继承 `SoftDeleteMixin`）
- **`restore(*, obj_id)`** — 恢复软删除的记录
- **`remove(*, db_obj=None, obj_id=None)`** — 物理删除记录

**高级方法：**

- **`execute_stmt(*, stmt, options=None)`** — 执行外部传入的 SQLAlchemy 语句（Select/Insert/Update/Delete），调用方自行处理返回结果
- **`execute_sql(*, sql, params=None)`** — 执行原始 SQL 语句，支持参数绑定

#### `create_db_engine(url, *, echo=False, pool_pre_ping=True, connect_args=None, **engine_kwargs) -> AsyncEngine`

自动创建异步数据库引擎。仅支持异步驱动（asyncpg、asyncmy、aiomysql、aiosqlite、aioodbc）。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `url` | `str` | 必填 | 数据库连接 URL，仅支持异步驱动 |
| `echo` | `bool` | `False` | 是否打印 SQL 日志 |
| `pool_pre_ping` | `bool` | `True` | 借出连接前是否测试连接有效性 |
| `connect_args` | `Mapping \| None` | `None` | 传递给驱动的额外连接参数 |

#### `SessionFactory(engine)`

数据库会话管理器，无全局变量，传入引擎更安全。

- **`get_session() -> AsyncGenerator[AsyncSession]`** — 获取会话上下文管理器，自动事务、自动回滚、自动关闭
- **`get_service(service_cls) -> Callable`** — 生成 FastAPI `Depends` 可用的服务依赖工厂方法

---

### 日志 — `lumary.common`

#### `set_log_level(level)`

动态修改全局日志级别（包括 FastAPI/Uvicorn 所有日志）。支持传入 `'debug'` / `'info'` / `'warn'` / `'error'` 或 `logging.DEBUG` 等常量。

#### `set_log_format(log_format)`

动态修改全局日志格式字符串，所有输出（控制台 + 文件）立即生效。

#### `setup_logger(log_dir=None, filename='app.log', when='midnight', backup_count=30, encoding='utf-8', enable_console=True)`

一键配置应用日志，支持控制台开关与文件日志。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `log_dir` | `str \| Path \| None` | `None` | 日志保存目录，不提供则不开启文件日志 |
| `filename` | `str` | `'app.log'` | 日志文件名 |
| `when` | `str` | `'midnight'` | 轮转周期（`'midnight'` 每天半夜，`'H'` 每小时） |
| `backup_count` | `int` | `30` | 保留的日志文件数量 |
| `encoding` | `str` | `'utf-8'` | 文件编码 |
| `enable_console` | `bool` | `True` | 是否在控制台输出日志 |

---

### 工具函数 — `lumary.common`

#### `camel_to_snake(s: str) -> str`

驼峰转下划线。`'HelloWorld'` → `'hello_world'`。

#### `snake_to_camel(s: str) -> str`

下划线转驼峰。`'hello_world'` → `'HelloWorld'`。

#### `random_string(length: int = 16) -> str`

生成指定长度的随机字符串（包含大小写字母和数字）。

#### `json_dumps(obj: Any) -> str`

高性能 JSON 序列化。若环境安装了 `orjson` 则优先使用 orjson 加速，否则回退到标准库 `json`。

#### `json_loads(s: str | bytes) -> Any`

高性能 JSON 反序列化。若环境安装了 `orjson` 则优先使用 orjson 加速，否则回退到标准库 `json`。

#### `add_datetime(dt, years=0, months=0, days=0, hours=0, minutes=0, seconds=0) -> datetime`

给 datetime 对象添加指定的年月日时分秒，正确处理闰年和月份天数差异。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `dt` | `datetime` | 必填 | 原始 datetime（支持 naive/aware） |
| `years` | `int` | `0` | 增加的年数（负数减少） |
| `months` | `int` | `0` | 增加的月数（负数减少） |
| `days` | `int` | `0` | 增加的天数（负数减少） |
| `hours` | `int` | `0` | 增加的小时数 |
| `minutes` | `int` | `0` | 增加的分钟数 |
| `seconds` | `int` | `0` | 增加的秒数 |

---

### 便捷重导出 — `lumary`

为了方便使用，`lumary` 顶层直接重导出了以下 FastAPI 和 Pydantic 常用对象：

| 类别 | 导出 |
|------|------|
| FastAPI 核心 | `FastAPI`, `APIRouter`, `Depends`, `Query`, `Path`, `Body`, `Header`, `Cookie`, `Form`, `File`, `UploadFile`, `Request`, `Response`, `HTTPException`, `BackgroundTasks`, `status`, `WebSocket`, `WebSocketDisconnect` |
| FastAPI 响应 | `JSONResponse`, `HTMLResponse`, `StreamingResponse`, `RedirectResponse`, `FileResponse`, `jsonable_encoder` |
| Pydantic | `BaseModel`, `Field`, `ConfigDict`, `field_validator`, `model_validator`, `ValidationError` |

## License

[MIT](LICENSE)
