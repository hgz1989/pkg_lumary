# 更新日志 (Changelog)

本文档用于记录 `lumary` 框架的所有显著变更、新特性以及性能优化。

## [0.2.4] - 2026-06-25

### 🚀 新特性 (Features)
- **Response Wrapper (路由响应包装)**: `routing.py` 增强，支持路由函数返回长度为 3 的元组 `(data, extra, message)`。框架将自动解析并将其组装为带有自定义提示信息、扩展数据及业务数据的标准 API 响应。
- **Global Schema Configuration**: 在 `schemas.py` 的全局 `SchemaBase` 中开启了 `alias_generator=to_pascal`。所有继承自该基类的 Pydantic 模型（包括框架自动包装的 `APIResponse`），其序列化输出的 JSON 键名将全局统一采用 **大写驼峰 (PascalCase)** 格式（如 `RequestId`, `Message`, `Data`），高度契合部分企业的前端契约标准。

### 🐛 问题修复 (Bug Fixes)
- **Global Handlers**: 修复了 `handlers.py` 中由于未正确声明及提取 `HTTPException.headers` 导致的局部变量 `extra` 未绑定错误 (`UnboundLocalError`)。现已将 `exc.headers` 标准转化为 `extra` 返回，并在监控降级日志中安全输出。
- **Tests Coverage**: 全面修复了单元测试套件（`tests/test_application.py`, `tests/test_router.py`），将其内部所有的断言逻辑从原先的小写蛇形（snake_case）适配为最新的全局 PascalCase 响应规范，恢复 100% 的测试通过率。

## [0.2.3] - 2026-06-23

### 🚀 新特性 (Features)
- **Database (CRUD)**: 新增极速原生 SQL 级批量更新方法 `update_multi`，彻底绕过 ORM 实例化开销。新增原生 SQL 级批量删除方法 `remove_multi`，自动适配软删除与物理删除。纯写入场景下 `batch_create` 方法重构，启用底层 `insert(model).values()` 提升性能。
- **Core / Application**: 新增 `/metrics` 端点的独立资源监控模块 `lumary.common.utils.metrics`，实现纯标准库、多平台的系统资源（内存、CPU、磁盘）及 Uvicorn 多进程 Worker 的精准指标采集。
- **WebSockets**: 增强 `WSConnectionManager`，在执行广播操作时添加 `return_exceptions=True` 机制，防止单一失效客户端导致的大规模广播雪崩效应。

### ⚡ 性能优化 (Performance)
- **Database (CRUD)**: `get_page` 分页逻辑中新增 `count == 0` 短路判断，当无数据时跳过额外 I/O 查询。`get_multi` 兜底分页机制中，当未显式指定 `order_by` 时，自动采用主键降序排列，消除深分页数据重复或错位。修复 `_validate_kwargs_keys` 实例方法上不当使用 `@lru_cache` 导致的内存与数据库连接泄漏隐患。修复 `get_one` 触发 `scalar_one_or_none()` 潜在的全表扫描风险，加入强制的 `.limit(2)` 限制。
- **Routing & Middleware**: `application.py` 中 `/info` 端点的全量路由遍历计算重构为缓存属性 `_sub_apps_count` 及 `_routes_count`，时间复杂度从 O(N) 降至 O(1)。`RequestIdMiddleware` 中间件重写 ASGI 拦截逻辑，移除不必要的全局字典转化，极大压榨高并发下的流式响应性能。

### 🐛 问题修复 (Bug Fixes)
- **Core / Application**: 修复 `allow_credentials=True` 且未指定具体 Origin 列表时的 CORS 配置漏洞，防止浏览器跨域安全拦截。修复子应用 `_application_lifespan` 挂载雪崩问题：单个子应用异常不再导致整个主框架崩溃。修复子应用挂载时对无序文件系统的依赖，增加强制字典排序，保证路由初始化的确定性。新增子应用重复挂载的拦截机制，彻底阻断路由重叠污染。修复 `route.py` 中的向后兼容性，安全清理 `secure_cloned_response_field` 防止某些 FastAPI/Starlette 版本的 `ResponseValidationError` 报错。
- **Database (CRUD)**: 修复外层传递 `options=[joinedload(...)]` 时 `get_multi` 和 `get_one` 方法未调用 `.unique()` 导致的一对多关联查询报错。
- **Context & UUIDs**: 修复 `generate_request_id` 输出，改用 `uuid4().hex` 产生不带短横线的 32 位纯字符，完美兼容 W3C Trace Context，并同步修复了所有单元测试中断言。

### ♻️ 重构与代码规范 (Refactoring & Code Quality)
- **MQTT (Paho-MQTT 迁移)**: 彻底放弃不稳定的 `aiomqtt`，将底层迁移至官方支持的 `paho-mqtt`。利用原生的 C 扩展后台守护线程 (`loop_start`) 取代自建的事件循环，完美兼容 FastAPI 主线程调度 (`run_coroutine_threadsafe`)。解决 `paho-mqtt` 中大量弃用及未使用变量引发的静态检查警告，同时兼容 API v2 规范。将 `asyncio.iscoroutinefunction` 替换为 `inspect.iscoroutinefunction`，以兼容 Python 3.14+。
- **Logging**: `logger.py` 默认日志格式增强：时间戳精度提升至毫秒 (`%(msecs)03d`) 且采用小数点分隔以利于 ELK 结构化解析，并追加进程与线程追踪 (`%(process)d:%(thread)d`) 支持多 Worker 模式排障。
- **Cache**: 修复 `cache.py` 装饰器中 `Request` 类型探测可能引发的 Pylance 鸭子类型推断错误，补全类型声明。
- **Code Style**: 路由模块重命名：将 `lumary/ws/router.py` 规范化为 `lumary/ws/routing.py`，与 FastAPI 源码命名对齐。提取 `crud.py` 局部导入至文件顶端，消除隐式类型提示警告。精简 `schemas.py` 继承链，优化 `APIResponseWithExtra` 复用逻辑。

## [0.2.2] - 2026-06-22

### 🚀 新特性 (Features)
- **数据库读写分离架构**: `engine.py` 新增 `create_routing_engines`，支持主从数据库集群配置。配合 `session.py` 中的 `RoutingSession` 拦截器和 `ContextVar`，实现了对业务层代码透明的高并发主从库自动路由与流量切分。
- **WebSocket 分布式广播**: `WSConnectionManager` 引入基于 Redis Pub/Sub 的跨实例（多 Pod/Worker）消息订阅分发能力。在多实例部署下有效解决广播消息孤岛问题。
- **服务层类依赖注入**: 新增 `@session_factory.service()` 类装饰器，通过动态重写服务类的 `__signature__`，使得在 FastAPI 路由中可以直接使用 `service: XXXService = Depends()`，极大减少依赖样板代码。

### ⚡ 性能优化 (Performance)
- **批量数据操作下沉**: `CRUDBase` 中的 `remove_multi` 和 `update_multi` 支持直接执行底层 SQL 进行批量更新与删除，绕过 ORM 实例加载开销，大幅提升海量数据操作性能。
- **分页逻辑下推**: 数据库操作基类 `CRUDBase` 增加 `get_page` 方法，直接在数据库层完成 count 统计与查询，并组装返回完整的 `PageData` 对象，减少各业务服务层的冗余计算逻辑。
- **流式响应兼容优化**: 深度优化 `RequestIdMiddleware` 中间件，改为直接拦截 ASGI 的 `http.response.start` 事件阶段，彻底消除其对 `StreamingResponse` 大数据流式传输造成的闭包性能损耗。

### 🐛 问题修复 (Bug Fixes)
- **OpenAPI Schema 渲染异常**: 移除了导致 Swagger UI 无法推断嵌套模型（显示 "Additional properties allowed"）的自定义 `@model_serializer`，改用兼容性更好的 `ConfigDict(json_encoders=...)`，恢复清晰规范的 API 文档。
- **物理删除事务丢失**: 修复了 `CRUDBase.remove` 及软删除时没有立即 `await self.db.flush()` 导致外部难以捕获数据库状态异常的问题。
- **ULID 默认值生成报错**: 修复了 SQLAlchemy 模型在使用 Callable 作为字段默认值时由于框架自动传递 `context` 参数而引发的 `TypeError: <lambda>() takes 0 positional arguments but 1 was given`。

### ♻️ 重构与代码规范 (Refactoring & Code Quality)
- **全包代码规范肃清**: 编写正则检查脚手架，全面清理了项目中不规范的“中英文夹杂空格”、“注释末尾带句号”等历史遗留问题，严格对齐 `CODING_STANDARDS.md`。
- **导入顺序极致规范**: 彻底对齐了全项目 Python 文件的导包规范，确保同组内 `import` 语句始终在 `from` 之前，并且按变量被调用的先后时间顺序严格排序。
- **IDE 静态告警清零**: 修复了 `crud.py` 等核心文件中的 PyCharm 类型检查警告，包括完善 `Select | Update` 的联合类型注解、消除重复代码块、通过反射安全获取 `is_deleted` 与 `rowcount` 属性。
- **测试用例边界加固**: 全面修复了在模拟环境（无 Redis 依赖）下的 AsyncMock 异步协程陷阱（`AttributeError` / `cancelled` 事件循环处理延迟），并实现 `pytest` 399 个用例 100% 稳健通过。

## [0.2.1] - 2026-06-21

### 🚀 新特性 (Features)
- **异步 MQTT 路由系统**: 新增 `mqtt_client` 管理器，通过 `pip install lumary[mqtt]` (依赖 `aiomqtt`) 获取。
  - **装饰器路由设计**: 使用 `@mqtt_client.on_message("sensor/+/temp")` 实现主题与处理函数的绑定。
  - **一对多并发处理**: 同一个主题模式可以绑定多个处理函数，接收到消息时各函数会自动以 `asyncio.create_task` 相互独立并发执行，避免单点阻塞。
  - **优雅降级**: 未安装 `aiomqtt` 时静默回退为无操作模式。
- **Redis 高级缓存系统**: 新增 `CacheManager` 与 `@cache_response` 装饰器，支持无侵入式缓存。
  - 支持“平滑降级”：若未安装 `redis` 依赖，缓存功能会自动失效但不会阻断业务执行。
  - `CRUDBase` 深度集成：在进行创建、更新、删除等写操作时，自动通过 `SCAN` 清理对应表命名空间下的缓存。
- **可选依赖机制**: 在 `pyproject.toml` 中新增了 `[project.optional-dependencies]`，支持 `pip install lumary[standard]` 或 `lumary[redis]`。

### ⚡ 性能优化 (Performance)
- **底层序列化加速**: 缓存组件等底层模块全面接入内部封装的 `json_dumps`/`json_loads`，在安装了 `orjson` 时自动获得极致的 Rust 级序列化性能。
- **ORM 校验缓存**: 在 `CRUDBase._apply_kwargs_filter` 中引入 `functools.lru_cache`，将高频字典查询键验证的耗时降为 $O(1)$ 级别。
- **生命周期排重优化**: 为 `_HookItem` 实现 `__hash__`，使用 O(1) Hash Set 替代 O(N) 列表遍历，极大提升海量生命周期钉子的挂载排重速度。
- **中间件提取提速**: 在 `RequestIdMiddleware` 中使用 C 层级的字典转换与获取（`dict(scope.get('headers'))`），取代 Python 级的 `for` 循环遍历。
- **路由响应包装优化**: 使用 `type(raw_response) is dict` 的精确类型匹配替代 `isinstance`，绕过 MRO 查找，提升并发响应包装的纳秒级性能。

### 🛠️ 重构与架构调整 (Refactoring)
- **主子应用生命周期统管**: 引入 `AsyncExitStack` 重构生命周期管理机制，实现子应用（挂载的 `Mount`）启动与主应用启动/清理资源的栈式隔离与统一调度。
- **解决中间件重复穿透**: 子应用默认不再注入全局 `RequestIdMiddleware` 和 `CORSMiddleware`，统一交由主应用接管，杜绝 `x-request-id` 头冲突及跨域报错。
- **子应用钩子隔离**: 挂载子应用时，强制分配独立的 `HookRegistry`（空对象模式），防止子应用重复执行主应用的全局钉子。
- **统一异常体系**: 将 `CRUDBase` 中抛出的 `sqlalchemy.exc.NoResultFound` 和 `InvalidRequestError` 彻底替换为框架内置的 HTTP 异常 `NotFoundError` 和 `BadRequestError`。
- **Pydantic V2 完美适配**: 彻底移除 `SchemaBase` 中的弃用属性 `json_encoders`，采用 `@model_serializer(mode='wrap')` 递归接管所有全局时间的格式化处理。

### 🧹 规范与修复 (Fixes)
- 修正 `docs/CODING_STANDARDS.md` 规范：移除所有 Docstring 结尾的句号。
- 修复并优化 `router.py` 中静态类型检查器（Pylance/Mypy）对于联合类型及元组类型的泛型推导报错。
- 修复相对导入引发的代码层次混乱，统一修改为 `lumary.` 绝对路径导入。
