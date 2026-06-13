"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: OpenAPI 文档自定义配置
"""
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

def setup_custom_openapi(app: FastAPI) -> None:
    """设置自定义OPENAPI

    Args:
        app: FastAPI实例对象
    """

    def custom_openapi() -> dict[str, Any] | None:
        """自定义OPENAPI

        Returns:
            OPENAPI模式字典或None
        """
        if app.openapi_schema:
            return app.openapi_schema

        # 关键：这里会自动拿到全部正确的路由（包括子应用）
        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            openapi_version=app.openapi_version,
            summary=app.summary,
            description=app.description,
            routes=app.routes,
            tags=app.openapi_tags,
            servers=app.servers,
            terms_of_service=app.terms_of_service,
            contact=app.contact,
            license_info=app.license_info,
            separate_input_output_schemas=app.separate_input_output_schemas,
        )

        components = openapi_schema.setdefault('components', {})
        schemas = components.setdefault('schemas', {})

        # 删掉 ValidationError 和 HTTPValidationError
        schemas.pop('ValidationError', None)
        schemas.pop('HTTPValidationError', None)

        # 删掉所有接口的 422
        paths = openapi_schema.get('paths', {})
        for path in paths.values():
            for method in path.values():
                responses = method.get('responses', {})
                responses.pop('422', None)

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    # 重点：不是直接执行，而是赋值给 openapi 函数
    app.openapi = custom_openapi
