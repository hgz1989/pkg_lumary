# 更新日志 (Changelog)

本文档用于记录 `lumary` 框架的所有显著变更、新特性以及性能优化。

## [0.2.1] - 2026-06-21

### 🚀 新特性 (Features)
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
