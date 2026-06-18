"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 核心响应与请求数据模型
"""
from datetime import datetime
from math import ceil
from typing import TypeVar, Generic, Sequence, Any

from pydantic import BaseModel, ConfigDict, Field

from .__version__ import __version__ as lumary_version
from .common import get_request_id

T = TypeVar('T')
E = TypeVar('E')  # 扩展结构体


class SchemaBase(BaseModel):
    """全局所有 Pydantic Schema 基类

    统一配置、统一行为
    """
    model_config = ConfigDict(
        # ✅ 1. 核心：允许从 ORM 对象读取属性（必须）
        from_attributes=True,

        # ✅ 2. 允许使用别名（例如 camelCase 字段）
        populate_by_name=True,

        # ✅ 3. 忽略多余字段（安全！前端传多余字段不会报错）
        extra='ignore',

        # ✅ 4. 允许任意类型（支持泛型绑定 ORM 模型等）
        arbitrary_types_allowed=True,
        
        # ✅ 5. 全局配置 datetime 序列化格式（原生支持，完美兼容 OpenAPI）
        json_encoders={
            datetime: lambda v: v.strftime('%Y-%m-%d %H:%M:%S')
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
    python_version: str = Field(description='Python 运行时版本')


class SystemMetricsOut(SchemaBase):
    """系统运行指标输出"""
    uptime_seconds: float = Field(description='应用运行时长（秒）')
    memory_mb: float = Field(description='进程内存占用（MB），不支持则为 -1')


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
    ) -> 'PageData[T]':
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


class APIResponseBase(SchemaBase):
    """底层基础响应，同时承载 data + extra 两套泛型"""
    model_config = ConfigDict(extra='forbid')
    request_id: str = Field(description='请求唯一追踪ID')
    code: int = Field(default=0, description='状态码，0为成功，其他为错误')
    message: str = Field(default='成功', description='提示信息')


class APIResponse(APIResponseBase, Generic[T]):
    """仅携带业务数据的通用响应, T为业务数据类型"""
    data: T | None = Field(default=None, description='业务主体响应数据')


class APIResponseWithExtra(APIResponseBase, Generic[T, E]):
    """携带业务数据+自定义结构化扩展的响应, T为业务数据类型，E为扩展数据类型"""
    data: T | None = Field(default=None, description='业务主体响应数据')
    extra: E | None = Field(default=None, description='自定义扩展信息')


def _response(
        code: int | None = None,
        message: str | None = None,
        data: T | None = None,
        extra: E | None = None
) -> dict[str, Any]:
    """返回通用响应

    Args:
        code: 状态码
        message: 提示信息
        data: 响应数据
        extra: 扩展数据

    Returns:
        APIResponse[T]
    """
    kwargs: dict[str, Any] = {
        'request_id': get_request_id()
    }

    if code is not None:
        kwargs['code'] = code

    if message is not None:
        kwargs['message'] = message

    if data is not None:
        kwargs['data'] = data

    if extra is not None:
        kwargs['extra'] = extra

    return kwargs


def response_success(
        message: str | None = None,
        data: T | None = None
) -> APIResponse[T]:
    """返回成功响应

    Args:
        message: 提示信息
        data: 响应数据

    Returns:
        APIResponse[T]
    """
    resp_data = _response(code=0, message=message, data=data)
    return APIResponse(**resp_data)


def response_fail(
        code: int,
        message: str = '失败',
        data: T | None = None
) -> APIResponse[T]:
    """返回失败响应

    Args:
        code: 错误码
        message: 错误信息
        data: 附加错误数据

    Returns:
        APIResponse[T]
    """
    resp_data = _response(code=code, message=message, data=data)
    return APIResponse(**resp_data)


def response_with_extra_success(
        message: str | None = None,
        data: T | None = None,
        extra: E | None = None
) -> APIResponseWithExtra[T, E]:
    """返回携带扩展数据的成功响应

    Args:
        message: 提示信息
        data: 响应数据
        extra: 扩展数据

    Returns:
        APIResponseWithExtra[T, E]
    """
    resp_data = _response(code=0, message=message, data=data, extra=extra)
    return APIResponseWithExtra(**resp_data)


def response_with_extra_fail(
        code: int,
        message: str | None = None,
        data: T | None = None,
        extra: E | None = None
) -> APIResponseWithExtra[T, E]:
    """返回携带扩展数据的失败响应

    Args:
        code: 错误码
        message: 错误信息
        data: 附加错误数据
        extra: 扩展数据

    Returns:
        APIResponseWithExtra[T, E]
    """
    resp_data = _response(code=code, message=message, data=data, extra=extra)
    return APIResponseWithExtra(**resp_data)
