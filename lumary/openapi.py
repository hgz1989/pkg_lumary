"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: OpenAPI文档自定义配置
"""
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def configure_openapi_schema(app: FastAPI) -> None:
    """配置OpenAPI Schema

    Args:
        app: FastAPI实例对象
    """

    def custom_openapi() -> dict[str, Any] | None:
        """自定义OpenAPI Schema

        Returns:
            OPENAPI模式字典或None
        """
        # 如果 OpenAPI 被显式禁用 (通常在生产环境 debug=False 时)
        if app.openapi_url is None:
            return None

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

        # 删掉ValidationError和HTTPValidationError
        schemas.pop('ValidationError', None)
        schemas.pop('HTTPValidationError', None)

        # 删掉所有接口的422
        paths = openapi_schema.get('paths', {})
        for path in paths.values():
            for method_obj in path.values():
                # 跳过非字典类型的字段（如parameters、summary等）
                if not isinstance(method_obj, dict):
                    continue
                responses = method_obj.get('responses', {})
                responses.pop('422', None)

        # 统一注入全局响应头、安全认证配置等（预留扩展点）
        # components.setdefault('securitySchemes', {
        #     "BearerAuth": {"type": "http", "scheme": "bearer"}
        # })
        # openapi_schema.setdefault('security', [{"BearerAuth": []}])

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    # 重点：不是直接执行，而是赋值给openapi函数
    app.openapi = custom_openapi  # type: ignore
