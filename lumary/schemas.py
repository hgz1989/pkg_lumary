"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 核心响应与请求数据模型
"""
from datetime import datetime, date
from math import ceil
from typing import TypeVar, Generic, Sequence

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_pascal

from .__version__ import __version__ as lumary_version
from .common import get_request_id

T = TypeVar('T')
E = TypeVar('E')  # 扩展结构体


class SchemaBase(BaseModel):
    """全局所有Pydantic Schema基类

    统一配置、统一行为
    """
    model_config = ConfigDict(
        # ✅ 1. 核心：允许从ORM对象读取属性（必须）
        from_attributes=True,

        # ✅ 2. 允许使用别名（例如camelCase字段）
        populate_by_name=True,

        # ✅ 3. 忽略多余字段（安全！前端传多余字段不会报错）
        extra='ignore',

        # ✅ 4. 允许任意类型（支持泛型绑定ORM模型等）
        arbitrary_types_allowed=True,

        # ✅ 5. 开启别名生成器（支持驼峰等），如果你项目需要全局驼峰响应
        alias_generator=to_pascal,

        # ✅ 6. 其他配置...
        json_encoders={
            datetime: lambda v: v.isoformat().replace('T', ' '),
            date: lambda v: v.isoformat(),
        }
    )


class PageParams(SchemaBase):
    """通用分页请求参数（适用于后台管理系统）"""
    page: int = Field(default=1, description='当前页码', ge=1)
    size: int = Field(default=100, description='每页数量', ge=1, le=1000)


class TimeRangeParams(SchemaBase):
    """通用时间范围查询参数"""
    start_time: datetime | None = Field(default=None, description='开始时间')
    end_time: datetime | None = Field(default=None, description='结束时间')


class KeywordParams(SchemaBase):
    """通用关键字搜索参数"""
    keyword: str | None = Field(default=None, description='搜索关键字', max_length=100)


class BatchIds(SchemaBase):
    """通用批量操作参数（如批量删除/更新）"""
    ids: list[int] | list[str] = Field(description='ID列表', min_length=1)


class SystemHealthOut(SchemaBase):
    """系统健康检查输出"""
    status: str = Field(default='OK', description='系统状态')
    name: str = Field(default='Lumary', description='系统名称')
    version: str = Field(default=lumary_version, description='系统版本')
    debug: bool = Field(default=False, description='是否处于调试模式')


class SystemInfoOut(SchemaBase):
    """系统详细信息输出"""
    name: str = Field(description='系统名称')
    version: str = Field(description='系统版本')
    debug: bool = Field(description='是否处于调试模式')
    routes_count: int = Field(description='已注册路由数量')
    sub_apps_count: int = Field(description='已挂载子应用数量')
    python_version: str = Field(description='Python运行时版本')


class SystemMetricsOut(SchemaBase):
    """系统运行指标输出"""
    uptime_seconds: float = Field(description='应用运行时长（秒）')
    memory_mb: float = Field(description='进程组总内存占用（MB）')
    cpu_percent: float = Field(description='进程组CPU总使用率（%）')
    disk_usage_percent: float = Field(description='系统磁盘使用率（%）')
    workers_count: int = Field(description='当前工作进程数量')
    threads_count: int = Field(description='当前活动线程数量')
    tasks_count: int = Field(description='当前异步任务数量')


class PageData(SchemaBase, Generic[T]):
    """通用分页响应数据（全量信息）"""
    items: Sequence[T] = Field(default_factory=list, description='当前页数据列表')
    page: int = Field(default=1, description='当前页码')
    size: int = Field(default=10, description='每页数量')
    pages: int = Field(default=0, description='总页数')
    total: int = Field(default=0, description='总记录数')

    @classmethod
    def build(
            cls,
            items: list[T] | Sequence[T],
            *,
            page: int,
            size: int,
            total: int
    ) -> PageData[T]:
        """根据查询结果构建分页响应

        自动计算总页数，避免调用方重复手动计算

        Args:
            items: 当前页数据列表
            page: 当前页码
            size: 每页数量
            total: 总记录数

        Returns:
            构建好的分页响应对象
        """
        pages = ceil(total / size) if size > 0 else 0
        return cls(items=items, page=page, size=size, pages=pages, total=total)


class APIResponse(SchemaBase, Generic[T, E]):
    """统一API响应模型, T为业务数据类型, E为扩展数据类型"""
    request_id: str = Field(default_factory=get_request_id, description='请求唯一追踪ID')
    code: int = Field(default=0, description='状态码，0为成功，其他为错误')
    message: str = Field(default='操作成功', description='提示信息')
    data: T | None = Field(default=None, description='业务主体响应数据')
    extra: E | None = Field(default=None, description='自定义扩展信息')


def build_response(
        code: int = 0,
        message: str = '操作成功',
        data: T | None = None,
        extra: E | None = None
) -> APIResponse[T, E]:
    """构建统一API响应

    Args:
        code: 状态码 (0为成功，非0为错误)
        message: 提示信息
        data: 响应数据 (可选)
        extra: 扩展数据 (可选)

    Returns:
        APIResponse[T, E]
    """
    kwargs = {
        'code': code,
        'message': message,
    }

    if data is not None:
        kwargs['data'] = data

    if extra is not None:
        kwargs['extra'] = extra

    return APIResponse(**kwargs)


def response_success(
        message: str = '操作成功',
        data: T | None = None,
        extra: E | None = None
) -> APIResponse[T, E]:
    """返回成功响应快捷方法

    Args:
        message: 提示信息
        data: 响应数据
        extra: 扩展数据

    Returns:
        APIResponse[T, E]
    """
    return build_response(message=message, data=data, extra=extra)


def response_fail(
        code: int,
        message: str,
        extra: E | None = None
) -> APIResponse[T, E]:
    """返回失败响应快捷方法

    Args:
        code: 错误码 (必须非0)
        message: 错误提示信息
        extra: 扩展数据

    Returns:
        APIResponse[Any, E]
    """
    return build_response(code=code, message=message, extra=extra)
