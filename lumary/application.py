"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 
"""
from importlib import import_module
from logging import getLogger
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import FastAPIError

from .handlers import setup_exception_handlers
from .lifespan import fastapi_lifespan
from .middleware import setup_middlewares
from .openapi import setup_custom_openapi
from .schemas import APIResponse, SystemHealthInfo, response_success

logger = getLogger(__name__)

# ===============================
# 默认元数据常量
# ===============================
_DEFAULT_TERMS_OF_SERVICE = 'https://www.zarkhan.com/terms/'
_DEFAULT_CONTACT = {
    'name': 'ZarkHan',
    'url': 'https://www.zarkhan.com'
}
_DEFAULT_LICENSE_INFO = {
    'name': 'MIT',
    'url': 'https://opensource.org/licenses/MIT'
}
_IGNORE_DIRS = {'__pycache__', 'tests', 'test', 'utils'}


# ===============================
# 应用类
# ===============================
class Lumary(FastAPI):
    """基于FastAPI封装的生产级Web应用类

    集成：异常处理、中间件、自定义文档、子应用管控、生命周期管理
    """
    # 减少内存占用 + 提升属性访问速度
    __slots__ = ('user_lifespan', 'is_sub_app')

    def __init__(
            self,
            *,
            debug: bool = False,
            title: str = 'Lumary',
            summary: str = '',
            description: str = '',
            version: str = '0.1.0',
            enable_cors: bool = True,
            allow_origins: list[str] | None = None,
            allow_methods: list[str] | None = None,
            allow_headers: list[str] | None = None,
            enable_health_check: bool = False,
            enable_access_log: bool = True,
            **kwargs: Any
    ):
        """初始化

        Args:
            debug: 是否启用调试模式
            title: 应用标题
            summary: 应用简介
            description: 应用描述
            version: 应用版本
            enable_cors: 是否启用 CORS 中间件
            allow_origins: 允许的源列表
            allow_methods: 允许的方法列表
            allow_headers: 允许的头列表
            enable_health_check: 是否启用健康检查
            enable_access_log: 是否启用访问日志
            **kwargs: 其他参数
        """
        user_lifespan = kwargs.pop('lifespan', None)

        # 👇 设置默认值
        kwargs.setdefault('terms_of_service', _DEFAULT_TERMS_OF_SERVICE)
        kwargs.setdefault('contact', _DEFAULT_CONTACT)
        kwargs.setdefault('license_info', _DEFAULT_LICENSE_INFO)
        kwargs.setdefault('lifespan', fastapi_lifespan)

        # 👇 如果非调试模式 → 关闭文档
        if not debug:
            kwargs['openapi_url'] = None
            kwargs['docs_url'] = None
            kwargs['redoc_url'] = None
            kwargs['swagger_ui_oauth2_redirect_url'] = None

        # 👇 调用父类初始化
        super().__init__(
            debug=debug,
            title=title,
            summary=summary,
            description=description,
            version=version,
            **kwargs
        )

        # 👇 设置异常处理
        setup_exception_handlers(self)

        # 👇 设置中间件
        setup_middlewares(
            self,
            enable_cors=enable_cors,
            allow_origins=allow_origins,
            allow_methods=allow_methods,
            allow_headers=allow_headers
        )

        # 👇 设置自定义文档
        setup_custom_openapi(self)

        # 👇 标记当前实例不是子应用
        self.user_lifespan = user_lifespan
        self.is_sub_app = False

        # 👇 如果启用健康检查 → 注册健康检查接口
        if enable_health_check:
            self._register_health_check()

    def _register_health_check(self) -> None:
        """注册健康检查接口"""

        @self.get('/health', tags=['system'], summary='服务健康检查')
        async def health(_request: Request) -> APIResponse[SystemHealthInfo]:
            """服务健康检查

            Returns:
                响应数据
            """
            data = SystemHealthInfo(
                name=self.title,
                version=self.version,
                debug=self.debug
            )
            return response_success(data=data, message='服务运行正常')

    def _load_sub_app(self, module_path: str, app_name: str) -> 'Lumary | None':
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

            # 👇 如果存在且类型正确 → 返回子应用实例
            if isinstance(sub_app, type(self)):
                return sub_app

            logger.warning(f'The sub app {module_path}.{app_name} does not exist or is not the correct type')
        except Exception as e:
            logger.error(f'❌ Loading sub app module exception: {module_path}, exception info: {str(e)}')

        return None

    def mount(self, path: str, app: 'Lumary', name: str | None = None) -> None:
        """挂载子应用

        Args:
            path: 挂载路径
            app: 子应用实例
            name:
        """
        # 👇 如果当前实例是子应用 → 直接报错禁止
        if self.is_sub_app:
            raise FastAPIError('❌ To prevent continuing to mount subapps in subapps, use APIRouter!')

        # 👇 标记子应用
        app.is_sub_app = True
        # 警告
        # 👇 清空子应用不允许的配置
        if app.root_path:
            logger.warning('The sub-app root_path has been automatically cleared')
            app.root_path = ''
        if app.user_lifespan:
            logger.warning('️The sub-app lifespan has been automatically cleared')
            app.user_lifespan = None

        # 主应用 → 正常执行原生 mount
        super().mount(path, app, name)
        logger.info(f'🚀 The sub-app is mounted: {path} -> {app.title}')

    def mount_sub_apps(self, apps_path: str | Path) -> None:
        """挂载子应用

        Args:
            apps_path: 子应用路径
        """
        apps_path = Path(apps_path)

        if not apps_path.exists():
            logger.warning(f'{apps_path} 目录不存在，跳过子应用挂载')
            return

        # 👇 遍历目录
        for path in apps_path.iterdir():
            if not path.is_dir():
                continue

            # 👇 获取文件夹名称
            folder_name = path.name

            # 跳过以下划线/点开头 或 在忽略列表中的目录
            if folder_name.startswith(('_', '.')) or (folder_name in _IGNORE_DIRS):
                continue

            # 👇 构建模块路径和变量名
            module_path = f'apps.{folder_name}'
            app_var_name = f'{folder_name}_app'
            mount_path = f'/{folder_name}'

            # 👇 动态导入子应用
            app = self._load_sub_app(module_path, app_var_name)

            # 👇 如果导入成功 → 挂载子应用
            if app is not None:
                self.mount(mount_path, app, folder_name)
