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
pip install lumary
```

如需 SQLAlchemy 支持：

```bash
pip install lumary[sqlalchemy]
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

## 开发

```bash
# 克隆仓库
git clone https://github.com/zarkhan/lumary.git
cd lumary

# 创建虚拟环境 & 安装开发依赖
python -m venv .venv
.venv\Scripts\activate       # Windows
source .venv/bin/activate    # macOS / Linux
pip install -e ".[dev]"

# 代码检查
ruff check lumary/

# 运行测试
pytest
```

## 打包发布

```bash
python -m build
twine check dist/*
twine upload dist/*
```

## License

[MIT](LICENSE)
