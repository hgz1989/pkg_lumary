"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: Lumary应用核心类与生命周期管理
"""
import sys
from contextlib import asynccontextmanager, AsyncExitStack
from importlib import import_module
from logging import getLogger
from pathlib import Path
from time import time
from typing import Any, Self, AsyncGenerator

from fastapi import FastAPI, APIRouter, Request
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Mount

from .__version__ import __version__ as lumary_version
from .common import set_log_level
from .handlers import build_exception_handlers
from .lifespan import (
    HookRegistry,
    default_registry,
    fastapi_lifespan
)
from .middleware import RequestIdMiddleware
from .openapi import configure_openapi_schema
from .schemas import (
    APIResponse,
    SystemHealthOut,
    response_success,
    SystemInfoOut,
    SystemMetricsOut
)

_logger = getLogger(__name__)

# 默认元数据常量
_DEFAULT_TERMS_OF_SERVICE = 'https://www.zarkhan.com/terms/'
_DEFAULT_CONTACT = {'name': 'ZarkHan', 'url': 'https://www.zarkhan.com'}
_DEFAULT_LICENSE_INFO = {'name': 'MIT', 'url': 'https://opensource.org/licenses/MIT'}


# 应用类
class Lumary(FastAPI):
    """基于FastAPI封装的生产级Web应用类

    集成：异常处理、中间件、自定义文档、子应用管控、生命周期管理
    """

    # 减少内存占用 + 提升属性访问速度
    __slots__ = ('is_sub_app', '_hook_registry', '_start_time')

    def __init__(
            self,
            *,
            debug: bool = False,
            title: str = 'Lumary',
            summary: str = '',
            description: str = '',
            version: str = lumary_version,
            is_sub_app: bool = False,
            enable_cors: bool = True,
            allow_origins: list[str] | None = None,
            allow_methods: list[str] | None = None,
            allow_headers: list[str] | None = None,
            hook_registry: HookRegistry | None = None,
            **kwargs: Any,
    ):
        """初始化

        Args:
            debug: 是否启用调试模式
            title: 应用标题
            summary: 应用简介
            description: 应用描述
            version: 应用版本
            is_sub_app: 是否为子应用
            enable_cors: 是否启用CORS中间件
            allow_origins: 允许的源列表
            allow_methods: 允许的方法列表
            allow_headers: 允许的头列表
            hook_registry: 生命周期钩子注册表，为None时使用默认全局注册表
            **kwargs: 其他参数
        """
        # 设置属性
        self.is_sub_app = is_sub_app
        
        # 主应用默认使用全局注册表，子应用默认使用独立的空注册表以防重复执行全局钉子
        if hook_registry is not None:
            self._hook_registry = hook_registry
        else:
            self._hook_registry = HookRegistry() if is_sub_app else default_registry

        # 如果是子应用
        if self.is_sub_app:
            # 清空子应用根路径
            if 'root_path' in kwargs:
                kwargs.pop('root_path')
                _logger.debug(f'子应用 [{title}] 的root_path已被自动清除')

        # 默认中间件
        middlewares = []
        
        # 子应用默认由主应用接管中间件，避免头冲突与重复执行
        if not self.is_sub_app:
            middlewares.append(
                Middleware(
                    RequestIdMiddleware,  # type: ignore
                )
            )

            # 添加CORS中间件
            if enable_cors:
                middlewares.append(
                    Middleware(
                        CORSMiddleware,  # type: ignore
                        allow_origins=allow_origins or ['*'],
                        allow_credentials=(allow_origins or ['*']) != ['*'],
                        allow_methods=allow_methods or ['*'],
                        allow_headers=allow_headers or ['*'],
                    )
                )

        # 设置默认值
        kwargs.setdefault('terms_of_service', _DEFAULT_TERMS_OF_SERVICE)
        kwargs.setdefault('contact', _DEFAULT_CONTACT)
        kwargs.setdefault('license_info', _DEFAULT_LICENSE_INFO)
        # 设置默认中间件
        kwargs.setdefault('middleware', middlewares)
        # 设置应用生命周期管理
        kwargs.setdefault('lifespan', self._application_lifespan)
        # 在父类初始化前注入异常处理器
        # middleware stack采用懒加载模式（首次请求时构建），但通过构造函数参数传入是注入handler的标准方式
        kwargs.setdefault('exception_handlers', build_exception_handlers())

        # 如果非调试模式 → 关闭文档、设置日志级别
        if not debug:
            kwargs['openapi_url'] = None
            kwargs['docs_url'] = None
            kwargs['redoc_url'] = None
            kwargs['swagger_ui_oauth2_redirect_url'] = None
            # 设置日志级别
            set_log_level('info')

        # 调用父类初始化
        super().__init__(
            debug=debug,
            title=title,
            summary=summary,
            description=description,
            version=version,
            **kwargs
        )

        # 记录应用启动时间
        self._start_time: float = time()

        # 设置自定义文档
        configure_openapi_schema(self)

        # 如果不是子应用
        if not is_sub_app:
            # 注册系统内置接口
            self._register_system_endpoints()

    def _register_system_endpoints(self) -> None:
        """注册系统内置接口（健康检查、详细信息、运行指标）"""
        router = APIRouter(prefix='/system', tags=['system'])

        @router.get('/health', summary='健康检查')
        async def health(_request: Request) -> APIResponse[SystemHealthOut]:
            """服务健康检查

            Returns:
                响应数据
            """
            data = SystemHealthOut(
                name=self.title,
                version=self.version,
                debug=self.debug
            )
            return response_success(data=data, message='服务运行正常')

        @router.get('/info', summary='详细信息')
        async def info(_request: Request) -> APIResponse[SystemInfoOut]:
            """查看应用详细信息

            Args:
                _request: 请求对象

            Returns:
                响应数据
            """
            data = SystemInfoOut(
                name=self.title,
                version=self.version,
                debug=self.debug,
                sub_apps_count=sum(1 for r in self.routes if isinstance(r, Mount)),
                routes_count=len(self.routes),
                python_version=sys.version,
            )
            return response_success(data=data, message='获取成功')

        @router.get('/metrics', summary='运行指标')
        async def metrics(_request: Request) -> APIResponse[SystemMetricsOut]:
            """查看应用运行指标

            Args:
                _request: 请求对象

            Returns:
                响应数据
            """
            uptime = round(time() - self._start_time, 3)
            memory_mb = -1
            data = SystemMetricsOut(
                uptime_seconds=uptime,
                memory_mb=memory_mb,
            )
            return response_success(data=data, message='获取成功')

        self.include_router(router)

    def _load_sub_app(self, module_path: str, app_name: str) -> Self | None:
        """动态导入单个子应用

        Args:
            module_path: 模块路径
            app_name: 应用变量名

        Returns:
            子应用实例
        """
        try:
            # 动态导入模块
            module = import_module(module_path)
            sub_app = getattr(module, app_name, None)

            if sub_app is None:
                _logger.warning(
                    f'子应用加载失败：在模块 {module_path} 中未找到变量 {app_name}，'
                    f'请检查模块配置与 __init__.py是否正确'
                )
            elif not isinstance(sub_app, self.__class__):
                _logger.warning(
                    f'子应用类型不匹配：{module_path}.{app_name} 不是合法的Lumary应用实例'
                )
            else:
                return sub_app

        except Exception as e:
            _logger.warning(f'无法导入模块：{module_path}，原因：{e}', exc_info=True)

        return None

    def mount_sub_apps(self, apps_path: str | Path = './apps') -> list[Self]:
        """挂载子应用

        Args:
            apps_path: 子应用路径
        """
        apps_path = Path(apps_path)

        if not apps_path.exists():
            err_msg = f'目录 {apps_path} 不存在，程序退出'
            _logger.error(err_msg, exc_info=True)
            raise RuntimeError(err_msg)

        apps_folder_name = apps_path.name

        _logger.info('开始挂载子应用')
        success_mounted_list = []
        # 遍历目录
        for path in apps_path.iterdir():
            if not path.is_dir():
                continue

            # 获取文件夹名称
            app_folder_name = path.name

            # 跳过以下划线/点开头 或 在忽略列表中的目录
            if app_folder_name.startswith(('_', '.', '#', '~')):
                continue

            # 构建模块路径和变量名
            module_path = f'{apps_folder_name}.{app_folder_name}'
            app_var_name = f'{app_folder_name}_app'
            mount_path = f'/{app_folder_name.replace("_", "-")}'

            # 动态导入子应用
            app = self._load_sub_app(module_path, app_var_name)

            # 如果导入成功 → 挂载子应用
            if app is not None:
                # 如果当前实例是子应用 → 直接报错禁止
                if self.is_sub_app:
                    raise RuntimeError(
                        f'禁止将子应用 [{app.title}] 挂载到另一个子应用 [{self.title}] 下'
                    )

                self.mount(mount_path, app, app_folder_name)
                success_mounted_list.append(app)
                _logger.info(f'已成功挂载子应用 [{app.title} -> {mount_path}]')

        # 子应用挂载结束
        _logger.info(f'子应用挂载完成，成功挂载 {[app.title for app in success_mounted_list]}')
        return success_mounted_list

    @asynccontextmanager
    async def _application_lifespan(self, app: FastAPI) -> AsyncGenerator[None, None]:
        """应用生命周期管理（支持栈式统管所有子应用）

        Args:
            app: FastAPI应用实例

        Returns:
            异步生成器
        """
        async with AsyncExitStack() as stack:
            # 1. 优先执行当前应用的生命周期钩子
            await stack.enter_async_context(fastapi_lifespan(app, registry=self._hook_registry))

            # 2. 遍历所有挂载的路由，如果是子应用且有lifespan_context，则自动入栈执行
            for route in app.routes:
                if isinstance(route, Mount):
                    sub_app = route.app
                    # 检查是否为合法的FastAPI/Starlette应用
                    if hasattr(sub_app, 'router') and hasattr(sub_app.router, 'lifespan_context'):
                        await stack.enter_async_context(sub_app.router.lifespan_context(sub_app))

            yield
