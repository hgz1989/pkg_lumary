"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 
"""
from typing import Any, Generic, Sequence, TypeVar

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func, select

from .model import ModelBase

ModelType = TypeVar('ModelType', bound=ModelBase)
CreateSchemaType = TypeVar('CreateSchemaType', bound=BaseModel)
UpdateSchemaType = TypeVar('UpdateSchemaType', bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """CRUD 泛型基类

    提供标准创建、读取、更新、删除操作(仅支持异步)
    子类必须在类级别显式定义 model 属性
    """
    model: type[ModelType]

    def __init__(self, db: AsyncSession):
        """初始化 CRUD 对象

        Args:
            db: 异步数据库会话对象
        """
        self.db = db

        if not hasattr(self, 'model') or self.model is None:
            raise ValueError(f'{self.__class__.__name__} 必须显式定义 model 属性')

        self.valid_columns = set(self.model.__table__.columns.keys())

    async def get(self, obj_id: Any) -> ModelType | None:
        """根据主键获取单条记录

        Args:
            obj_id: 记录主键

        Returns:
            查询到的模型实例或为空
        """
        db_obj = await self.db.get(self.model, obj_id)

        if db_obj and hasattr(db_obj, 'is_deleted') and db_obj.is_deleted:
            return None

        return db_obj

    async def get_one(self, **kwargs: Any) -> ModelType | None:
        """根据多个字段条件获取单条记录（AND 关系）

        Args:
            **kwargs: 字段名和值的键值对

        Returns:
            查询到的模型实例或为空
        """
        stmt = select(self.model)

        if kwargs:
            invalid_keys = set(kwargs.keys()) - self.valid_columns
            if invalid_keys:
                raise ValueError(f'无效的查询字段: {",".join(invalid_keys)}')
            stmt = stmt.filter_by(**kwargs)

        if hasattr(self.model, 'is_deleted'):
            stmt = stmt.where(getattr(self.model, 'is_deleted').is_(False))

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_multi(
            self,
            *criteria: Any,
            skip: int = 0,
            limit: int = 100,
            order_by: Any | Sequence[Any] | None = None,
            **kwargs: Any
    ) -> Sequence[ModelType]:
        """获取多条记录支持分页、条件过滤和排序

        Args:
            *criteria: SQLAlchemy 查询条件 (如 model.age > 18)
            skip: 跳过的记录数量
            limit: 返回的最大记录数量
            order_by: 排序字段或字段列表 (如 model.id.desc())
            **kwargs: 精确匹配的过滤条件 (如 status=1)

        Returns:
            模型实例序列
        """
        stmt = select(self.model)

        if hasattr(self.model, 'is_deleted'):
            stmt = stmt.where(getattr(self.model, 'is_deleted').is_(False))

        if criteria:
            stmt = stmt.where(*criteria)

        if kwargs:
            invalid_keys = set(kwargs.keys()) - self.valid_columns
            if invalid_keys:
                raise ValueError(f'无效的查询字段: {",".join(invalid_keys)}')
            stmt = stmt.filter_by(**kwargs)

        if order_by is not None:
            if isinstance(order_by, (list, tuple)):
                stmt = stmt.order_by(*order_by)
            else:
                stmt = stmt.order_by(order_by)

        stmt = stmt.offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_count(self, *criteria: Any, **kwargs: Any) -> int:
        """统计记录总数

        Args:
            *criteria: SQLAlchemy 查询条件
            **kwargs: 精确匹配的过滤条件

        Returns:
            记录总数
        """
        stmt = select(func.count()).select_from(self.model)

        if hasattr(self.model, 'is_deleted'):
            stmt = stmt.where(getattr(self.model, 'is_deleted').is_(False))

        if criteria:
            stmt = stmt.where(*criteria)

        if kwargs:
            invalid_keys = set(kwargs.keys()) - self.valid_columns
            if invalid_keys:
                raise ValueError(f'无效的查询字段: {",".join(invalid_keys)}')
            stmt = stmt.filter_by(**kwargs)

        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def create(self, *, obj_in: CreateSchemaType) -> ModelType:
        """创建新记录

        Args:
            obj_in: 创建记录的 Pydantic 模型

        Returns:
            创建成功的模型实例
        """
        obj_in_data = obj_in.model_dump(exclude_unset=True)

        invalid_keys = set(obj_in_data.keys()) - self.valid_columns
        if invalid_keys:
            raise ValueError(f'无效的创建字段: {",".join(invalid_keys)}')

        db_obj = self.model(**obj_in_data)
        self.db.add(db_obj)
        await self.db.flush()
        await self.db.refresh(db_obj)
        return db_obj

    async def update(
            self,
            *,
            db_obj: ModelType,
            obj_in: UpdateSchemaType | dict[str, Any]
    ) -> ModelType:
        """更新记录

        Args:
            db_obj: 需要更新的数据库模型实例
            obj_in: 包含更新数据的字典或 Pydantic 模型

        Returns:
            更新后的模型实例
        """
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        invalid_keys = set(update_data.keys()) - self.valid_columns
        if invalid_keys:
            raise ValueError(f'无效的更新字段: {",".join(invalid_keys)}')

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        await self.db.flush()
        await self.db.refresh(db_obj)
        return db_obj

    async def remove(self, *, db_obj: ModelType | None = None, obj_id: Any = None) -> ModelType | None:
        """物理删除记录

        Args:
            db_obj: 已存在的模型实例（优先使用）
            obj_id: 记录主键（obj 不存在时使用）

        Returns:
            被删除的模型实例或为空
        """
        # 如果已经传入 obj，直接使用，不再查库
        if not db_obj:
            db_obj = await self.get(obj_id)

        if db_obj:
            await self.db.delete(db_obj)
            await self.db.flush()
        return db_obj

    async def soft_delete(self, *, obj_id: Any) -> bool:
        """软删除记录

        Args:
            obj_id: 记录主键

        Returns:
            删除成功返回 True 否则返回 False
        """
        if not hasattr(self.model, 'is_deleted'):
            raise NotImplementedError('模型不支持软删除')

        db_obj = await self.get(obj_id)
        if not db_obj:
            return False

        setattr(db_obj, 'is_deleted', True)
        setattr(db_obj, 'deleted_at', func.now())
        await self.db.flush()
        return True
