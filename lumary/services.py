"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 
"""
from typing import TypeVar, Any, Generic, Sequence
from pydantic import BaseModel

from .exceptions import NotFoundError

OutSchemaType = TypeVar('OutSchemaType', bound=BaseModel)
CreateSchemaType = TypeVar('CreateSchemaType', bound=BaseModel)
UpdateSchemaType = TypeVar('UpdateSchemaType', bound=BaseModel)
CRUDType = TypeVar('CRUDType')


class BaseService(Generic[CRUDType, OutSchemaType, CreateSchemaType, UpdateSchemaType]):
    """通用服务基类

    封装了基于 CRUD 实例的基础业务逻辑，包括创建、更新、查询和删除。
    子类需在初始化时传入具体的 CRUD 实例。
    """
    entity_name: str = '记录'

    def __init__(self, crud: CRUDType, out_schema: type[OutSchemaType]):
        """初始化服务基类

        Args:
            crud: 数据访问层实例
            out_schema: 返回给前端的 Pydantic 模型类
        """
        self.crud = crud
        self.out_schema = out_schema

    async def create(self, obj_in: CreateSchemaType) -> OutSchemaType:
        """创建记录

        Args:
            obj_in: 创建数据的 Pydantic 模型

        Returns:
            创建成功并转换后的输出模型
        """
        db_obj = await self.crud.create(obj_in=obj_in)
        await self.crud.db.commit()
        return self.out_schema.model_validate(db_obj)

    async def update(self, obj_id: Any, obj_in: UpdateSchemaType) -> OutSchemaType:
        """更新记录

        Args:
            obj_id: 记录主键
            obj_in: 更新数据的 Pydantic 模型

        Returns:
            更新成功并转换后的输出模型
        """
        db_obj = await self.crud.get(obj_id)
        if not db_obj:
            raise NotFoundError(message=f'{self.entity_name}不存在')

        db_obj = await self.crud.update(db_obj=db_obj, obj_in=obj_in)
        await self.crud.db.commit()
        return self.out_schema.model_validate(db_obj)

    async def delete(self, obj_id: Any) -> None:
        """软删除记录

        Args:
            obj_id: 记录主键
        """
        db_obj = await self.crud.get(obj_id)
        if not db_obj:
            raise NotFoundError(message=f'{self.entity_name}不存在')

        await self.crud.soft_delete(obj_id=obj_id)
        await self.crud.db.commit()

    async def destroy(self, obj_id: Any) -> None:
        """物理删除记录

        Args:
            obj_id: 记录主键
        """
        db_obj = await self.crud.get(obj_id)
        if not db_obj:
            raise NotFoundError(message=f'{self.entity_name}不存在')

        await self.crud.remove(db_obj=db_obj)
        await self.crud.db.commit()

    async def get(self, obj_id: Any) -> OutSchemaType | None:
        """获取单条记录

        Args:
            obj_id: 记录主键

        Returns:
            查询成功并转换后的输出模型，不存在则返回 None
        """
        db_obj = await self.crud.get(obj_id)
        if not db_obj:
            return None
        return self.out_schema.model_validate(db_obj)

    async def get_list(self, skip: int = 0, limit: int = 100, **kwargs: Any) -> Sequence[OutSchemaType]:
        """获取多条记录列表

        Args:
            skip: 跳过的记录数
            limit: 返回的记录数
            **kwargs: 其他过滤条件

        Returns:
            转换后的输出模型列表
        """
        db_objs = await self.crud.get_multi(skip=skip, limit=limit, **kwargs)
        return [self.out_schema.model_validate(obj) for obj in db_objs]

    async def count(self, **kwargs: Any) -> int:
        """统计记录总数

        Args:
            **kwargs: 过滤条件

        Returns:
            记录总数
        """
        return await self.crud.get_count(**kwargs)
