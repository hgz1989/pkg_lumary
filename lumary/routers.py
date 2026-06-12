"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 
"""
from typing import Any, Callable, Type

from fastapi import APIRouter, Depends, Query, Path

from .schemas import APIResponse, PageData, PageQuery, response_success
from .services import BaseService


class CRUDRouter:
    """通用 CRUD 路由工厂

    通过传入依赖注入获取 Service 的函数，自动生成标准的增删改查 REST API 端点。
    """

    def __init__(
            self,
            service_dep: Callable[..., BaseService],
            out_schema: Type[Any],
            create_schema: Type[Any],
            update_schema: Type[Any],
            prefix: str = '',
            tags: list[str] | None = None,
            summary_prefix: str = '记录',
    ):
        """初始化 CRUD 路由

        Args:
            service_dep: 能够获取 Service 实例的 FastAPI Depends 函数
            out_schema: 输出 Schema 类
            create_schema: 创建 Schema 类
            update_schema: 更新 Schema 类
            prefix: 路由前缀
            tags: OpenAPI 标签
            summary_prefix: 接口 summary 描述前缀
        """
        self.router = APIRouter(prefix=prefix, tags=tags)
        self.service_dep = service_dep
        self.out_schema = out_schema
        self.create_schema = create_schema
        self.update_schema = update_schema
        self.summary_prefix = summary_prefix

        self._register_routes()

    def _register_routes(self) -> None:
        """注册标准 CRUD 路由"""

        @self.router.get(
            '/{obj_id}',
            summary=f'获取{self.summary_prefix}详情'
        )
        async def get_obj(
                obj_id: str = Path(description='主键ID'),
                service: BaseService = Depends(self.service_dep)
        ) -> APIResponse[self.out_schema]:  # type: ignore
            data = await service.get(obj_id)
            return response_success(data)

        @self.router.get(
            '',
            summary=f'分页获取{self.summary_prefix}列表'
        )
        async def get_page(
                query: PageQuery = Depends(),
                service: BaseService = Depends(self.service_dep)
        ) -> APIResponse[PageData[self.out_schema]]:  # type: ignore
            skip = (query.page - 1) * query.size
            total = await service.count()
            items = await service.get_list(skip=skip, limit=query.size)
            
            pages = (total + query.size - 1) // query.size
            page_data = PageData(
                page=query.page,
                size=query.size,
                total=total,
                pages=pages,
                items=items
            )
            return response_success(page_data)

        @self.router.post(
            '',
            summary=f'创建{self.summary_prefix}'
        )
        async def create_obj(
                obj_in: self.create_schema,  # type: ignore
                service: BaseService = Depends(self.service_dep)
        ) -> APIResponse[self.out_schema]:  # type: ignore
            data = await service.create(obj_in)
            return response_success(data)

        @self.router.post(
            '/{obj_id}/update',
            summary=f'更新{self.summary_prefix}'
        )
        async def update_obj(
                obj_in: self.update_schema,  # type: ignore
                obj_id: str = Path(description='主键ID'),
                service: BaseService = Depends(self.service_dep)
        ) -> APIResponse[self.out_schema]:  # type: ignore
            data = await service.update(obj_id, obj_in)
            return response_success(data)

        @self.router.post(
            '/{obj_id}/delete',
            summary=f'软删除{self.summary_prefix}'
        )
        async def delete_obj(
                obj_id: str = Path(description='主键ID'),
                service: BaseService = Depends(self.service_dep)
        ) -> APIResponse:
            await service.delete(obj_id)
            return response_success(message='删除成功')

        @self.router.post(
            '/{obj_id}/destroy',
            summary=f'物理删除{self.summary_prefix}'
        )
        async def destroy_obj(
                obj_id: str = Path(description='主键ID'),
                service: BaseService = Depends(self.service_dep)
        ) -> APIResponse:
            await service.destroy(obj_id)
            return response_success(message='彻底删除成功')
