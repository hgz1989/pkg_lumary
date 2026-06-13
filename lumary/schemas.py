"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 核心响应与请求数据模型
"""
from collections.abc import Sequence
from datetime import datetime
from typing import TypeVar, Any, Generic

from pydantic import (
    BaseModel,
    ConfigDict,
    Field
)

from .__version__ import (
    __version__ as lumary_version
)

T = TypeVar('T')


class SchemaBase(BaseModel):
    """全局所有 Pydantic Schema 基类

    统一配置、统一行为
    """
    model_config = ConfigDict(
        # 1. 核心：允许从 ORM 对象读取属性（必须）
        from_attributes=True,
        # 2. 允许使用别名（例如 camelCase 字段）
        populate_by_name=True,
        # 3. 忽略多余字段（安全！前端传多余字段不会报错）
        extra='ignore',
        # 4. 自定义 JSON 编码器（处理 datetime 类型）
        json_encoders={datetime: lambda v: v.strftime('%Y-%m-%d %H:%M:%S')},
    )

    # 核心：强制自动排除 None，并在序列化时将 id 提到最前
    def model_dump(self, **kwargs) -> dict[str, Any]:
        """重写 model_dump 方法，强制自动排除 None，并在序列化时将 id 提到最前

        Args:
            **kwargs: 其他参数

        Returns:
             序列化后的字典数据
        """
        kwargs['exclude_none'] = True
        data = super().model_dump(**kwargs)

        # 在最终输出时，强行将 id 字段排在第一个
        if 'id' in data:
            return {'id': data['id'], **{k: v for k, v in data.items() if k != 'id'}}
        return data


class PageQuery(SchemaBase):
    """通用分页请求参数（适用于后台管理系统）"""
    page: int = Field(default=1, description='当前页码', ge=1)
    size: int = Field(default=100, description='每页数量', ge=1, le=1000)


class TimeRangeQuery(SchemaBase):
    """通用时间范围查询参数"""
    start_time: datetime | None = Field(default=None, description='开始时间')
    end_time: datetime | None = Field(default=None, description='结束时间')


class KeywordQuery(SchemaBase):
    """通用关键字搜索参数"""
    keyword: str | None = Field(default=None, description='搜索关键字', max_length=100)


class BatchIds(SchemaBase):
    """通用批量操作参数（如批量删除/更新）"""
    ids: list[int] | list[str] = Field(..., description='ID 列表', min_length=1)


class APIResponse(SchemaBase, Generic[T]):
    """响应结构基础模型"""
    code: int = Field(default=0, description='状态码，0为成功，其他为错误')
    message: str = Field(default='Success', description='提示信息')
    data: T | None = Field(default=None, description='响应数据')


class PageData(SchemaBase, Generic[T]):
    """通用分页响应数据（全量信息）"""
    total: int = Field(default=0, description='总记录数')
    size: int = Field(default=10, description='每页数量')
    pages: int = Field(default=0, description='总页数')
    page: int = Field(default=1, description='当前页码')
    items: Sequence[T] | list[T] = Field(default_factory=list, description='当前页数据列表')


class SystemHealthOut(SchemaBase):
    """系统健康检查输出"""
    status: str = Field(default='OK', description='系统状态')
    name: str = Field(default='Lumary', description='系统名称')
    version: str = Field(default=lumary_version, description='系统版本')
    debug: bool = Field(default=False, description='是否处于调试模式')


def response_success(
        message: str | None = None,
        data: T | None = None
) -> APIResponse[T]:
    """返回成功响应

    Args:
        data: 响应数据
        message: 提示信息
    """
    kwargs = {}
    if message is not None:
        kwargs['message'] = message
    if data is not None:
        kwargs['data'] = data

    return APIResponse(**kwargs)


def response_fail(code: int, message: str = 'Fail', data: T | None = None) -> APIResponse[T]:
    """返回失败响应

    Args:
        code: 错误码
        message: 错误信息
        data: 附加错误数据
    """
    kwargs = {}
    if message is not None:
        kwargs['message'] = message
    if data is not None:
        kwargs['data'] = data

    return APIResponse(code=code, **kwargs)
