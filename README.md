# Lumary

基于 FastAPI 封装的生产级 Web 应用框架，开箱即用。

## 特性

- **应用封装** — `Lumary` 类继承 FastAPI，内置异常处理、CORS 中间件、自定义 OpenAPI 文档、健康检查
- **生命周期钩子** — `@on_startup` / `@on_shutdown` 装饰器，支持优先级排序与异常终止控制
- **统一响应格式** — `APIResponse`、`PageData`、`PageQuery` 等标准化 Schema
- **业务异常** — `BusinessException` 支持自定义错误码与消息，全局自动捕获
- **WebSocket 管理** — `WSConnectionManager` 支持分组、单播、广播、上下文管理器
- **枚举基类** — `BaseEnum` 提供 `val` / `label` 属性访问
- **SQLAlchemy 混入** — `SoftDeleteMixin` 软删除支持（可选依赖）
- **子应用管控** — 支持动态挂载子应用，禁止子应用嵌套

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

```python
from lumary import Lumary, on_startup, on_shutdown

app = Lumary(title='My Project', debug=True, enable_health_check=True)


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
from lumary import Lumary, WSConnectionManager

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
from lumary import response_success, response_fail, APIResponse

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
    ...
```

## 模块一览

| 模块 | 说明 |
|------|------|
| `lumary.application` | 应用类 `Lumary` |
| `lumary.lifespan` | 生命周期钩子 `on_startup` / `on_shutdown` |
| `lumary.schemas` | 统一响应模型 `APIResponse` / `PageData` / `PageQuery` |
| `lumary.exceptions` | 业务异常 `BusinessException` |
| `lumary.handlers` | 全局异常处理器 |
| `lumary.middleware` | 中间件注册 |
| `lumary.openapi` | 自定义 OpenAPI 文档 |
| `lumary.websocket` | WebSocket 连接管理器 `WSConnectionManager` |
| `lumary.common.enums` | 枚举基类 `BaseEnum` |
| `lumary.common.mixins` | SQLAlchemy 混入类 |
| `lumary.db` | 数据库工具 |

## License

[MIT](LICENSE)
