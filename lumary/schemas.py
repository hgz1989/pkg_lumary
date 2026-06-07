"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 
"""
from datetime import datetime
from typing import TypeVar, Any, Generic

from pydantic import BaseModel, ConfigDict, model_validator, Field

T = TypeVar('T')


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

        # ✅ 4. 自定义 JSON 编码器（处理 datetime 类型）
        json_encoders={
            datetime: lambda v: v.strftime('%Y-%m-%d %H:%M:%S')
        }
    )

    @model_validator(mode='before')
    @classmethod
    def sort_id_first(cls, values: dict[str, Any]) -> dict[str, Any]:
        """将 id 字段提到最前面

        最理想方案：在验证之前调整字典顺序
        不重建实例、不二次验证、不破坏内部、零副作用

        Args:
            values: 验证的字典数据

        Returns:
           调整顺序后的字典数据
        """
        if isinstance(values, dict) and 'id' in values:
            # 把 id 提到最前面，其余保持顺序
            return {
                'id': values['id'],
                **{key: val for key, val in values.items() if key != 'id'}
            }
        return values

    # 🔥 核心：强制自动排除 None，保留空字符串
    def model_dump(self, **kwargs) -> dict[str, Any]:
        """重写 model_dump 方法，强制自动排除 None，保留空字符串

        Args:
            **kwargs: 其他参数

        Returns:
            dict: 序列化后的字典数据
        """
        kwargs['exclude_none'] = True
        return super().model_dump(**kwargs)

    # 🔥 兼容 FastAPI 自动序列化
    def model_dump_json(self, **kwargs) -> str:
        """重写 model_dump_json 方法，强制自动排除 None，保留空字符串

        Args:
            **kwargs: 其他参数

        Returns:
            str: 序列化后的 JSON 字符串数据
        """
        kwargs.setdefault('exclude_none', True)
        return super().model_dump_json(**kwargs)


class APIResponse(BaseSchema, Generic[T]):
    """全局统一的 API 响应模型"""
    code: int = Field(default=200, description='业务状态码')
    message: str = Field(default='Success', description='提示信息')
    data: T | None = Field(default=None, description='响应数据')


class PageData(BaseSchema, Generic[T]):
    """通用分页响应数据（全量信息）"""
    page: int = Field(default=1, description='当前页码')
    size: int = Field(default=10, description='每页数量')
    total: int = Field(default=0, description='总记录数')
    pages: int = Field(default=0, description='总页数')
    items: list[T] = Field(default_factory=list, description='当前页数据列表')


class SystemHealthInfo(BaseSchema):
    """系统健康检查信息"""
    status: str = Field(default='ok', description='系统状态')
    name: str = Field(default='lumary', description='系统名称')
    version: str = Field(default='1.0.0', description='系统版本')
    debug: bool = Field(default=False, description='是否处于调试模式')


class PageQuery(BaseSchema):
    """通用分页请求参数（适用于后台管理系统）"""
    page: int = Field(default=1, description='当前页码', ge=1)
    size: int = Field(default=10, description='每页数量', ge=1, le=1000)


def response_success(data: T | None = None, message: str = 'Success') -> APIResponse[T]:
    """返回成功响应

    Args:
        data: 响应数据
        message: 提示信息
    """
    return APIResponse(code=200, message=message, data=data)


def response_fail(code: int = 400, message: str = 'Fail', data: T | None = None) -> APIResponse[T]:
    """返回失败响应

    Args:
        code: 错误码
        message: 错误信息
        data: 附加错误数据
    """
    return APIResponse(code=code, message=message, data=data)
