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

from sqlalchemy.exc import IntegrityError

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

    def _apply_soft_delete_filter(self, stmt: Any) -> Any:
        """为查询语句添加软删除过滤条件

        如果模型支持软删除，则自动过滤已删除的记录

        Args:
            stmt: SQLAlchemy 查询语句

        Returns:
            添加了软删除过滤条件的查询语句
        """
        if hasattr(self.model, 'is_deleted'):
            stmt = stmt.where(getattr(self.model, 'is_deleted').is_(False))
        return stmt

    def _apply_kwargs_filter(self, stmt: Any, kwargs: dict[str, Any]) -> Any:
        """为查询语句添加 kwargs 精确匹配过滤条件

        会校验 kwargs 中的字段是否为模型有效列，无效字段将抛出 ValueError

        Args:
            stmt: SQLAlchemy 查询语句
            kwargs: 精确匹配的过滤条件键值对

        Returns:
            添加了过滤条件的查询语句
        """
        if kwargs:
            invalid_keys = set(kwargs.keys()) - self.valid_columns
            if invalid_keys:
                raise ValueError(f'无效的查询字段: {",".join(invalid_keys)}')
            stmt = stmt.filter_by(**kwargs)
        return stmt

    async def get(self, obj_id: Any, options: list | None = None) -> ModelType | None:
        """根据主键获取单条记录

        Args:
            obj_id: 记录主键
            options: SQLAlchemy 加载策略列表

        Returns:
            查询到的模型实例或为空
        """
        db_obj = await self.db.get(self.model, obj_id, options=options)

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
        stmt = self._apply_soft_delete_filter(stmt)
        stmt = self._apply_kwargs_filter(stmt, kwargs)

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    async def get_count(self, *criteria: Any, **kwargs: Any) -> int:
        """统计记录总数

        Args:
            *criteria: SQLAlchemy 查询条件
            **kwargs: 精确匹配的过滤条件

        Returns:
            记录总数
        """
        stmt = select(func.count()).select_from(self.model)
        stmt = self._apply_soft_delete_filter(stmt)

        if criteria:
            stmt = stmt.where(*criteria)

        stmt = self._apply_kwargs_filter(stmt, kwargs)

        result = await self.db.execute(stmt)
        return result.scalar_one()
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
        stmt = self._apply_soft_delete_filter(stmt)

        if criteria:
            stmt = stmt.where(*criteria)

        stmt = self._apply_kwargs_filter(stmt, kwargs)

        if order_by is not None:
            if isinstance(order_by, (list, tuple)):
                stmt = stmt.order_by(*order_by)
            else:
                stmt = stmt.order_by(order_by)

        stmt = stmt.offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()



    async def batch_create(
            self,
            *,
            objs_in: list[CreateSchemaType | dict],
            ignore_errors: bool = False,
            return_objs: bool = True
    ) -> list[ModelType]:
        """批量创建记录

        Args:
            objs_in: 待创建的数据列表（Schema 或 dict）
            ignore_errors: 是否忽略单条插入的错误（如唯一键冲突）。
                           如果为 False，遇到错误将抛出异常，整个事务可以被调用方回滚。
                           如果为 True，将跳过出错的记录，只插入成功的数据。
            return_objs: 是否需要返回带有数据库默认值（如ID）的完整模型对象。
                         为 True 时使用 add_all + flush（性能略低，但能拿到所有 ID）；
                         为 False 时未来可优化为 execute(insert().values()) 提高性能。

        Returns:
            成功创建的模型实例列表
        """
        db_objs = []

        # 场景 1：要求全部成功，且需要返回对象
        if not ignore_errors:
            for obj_in in objs_in:
                obj_data = obj_in.model_dump() if hasattr(obj_in, "model_dump") else obj_in
                obj_data = {k: v for k, v in obj_data.items() if k in self.valid_columns}
                db_obj = self.model(**obj_data)
                db_objs.append(db_obj)

            self.db.add_all(db_objs)
            if return_objs:
                await self.db.flush()
            return db_objs

        # 场景 2：忽略错误记录（如某条数据冲突不影响其他数据入库）
        # 这种模式下只能逐条 add + flush 并捕获异常，因为 add_all 会导致整个 flush 失败
        successful_objs = []
        for obj_in in objs_in:
            obj_data = obj_in.model_dump() if hasattr(obj_in, "model_dump") else obj_in
            obj_data = {k: v for k, v in obj_data.items() if k in self.valid_columns}
            db_obj = self.model(**obj_data)
            self.db.add(db_obj)
            try:
                # 必须设置嵌套事务(savepoint)，防止一条报错导致外层主事务处于 invalid 状态
                async with self.db.begin_nested():
                    await self.db.flush()
                successful_objs.append(db_obj)
            except IntegrityError:
                # 唯一约束冲突等数据库异常被捕获，跳过该记录
                pass

        return successful_objs

    async def create(self, *, obj_in: CreateSchemaType) -> ModelType:
        """创建新记录

        Args:
            obj_in: 创建记录的 Pydantic 模型

        Returns:
            创建成功的模型实例
        """
        obj_in_data = {
            k: v for k, v in obj_in.model_dump(exclude_unset=True).items()
            if k in self.valid_columns
        }

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

        update_data = {
            k: v for k, v in update_data.items()
            if k in self.valid_columns
        }

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

    async def soft_delete(self, *, obj_id: Any, return_obj: bool = False) -> ModelType | None | bool:
        """软删除记录

        Args:
            obj_id: 记录主键
            return_obj: 是否返回被软删除的模型实例

        Returns:
            return_obj=True 时返回被删除的实例，否则返回 True/False
        """
        if not hasattr(self.model, 'is_deleted'):
            raise NotImplementedError('模型不支持软删除')

        db_obj = await self.get(obj_id)
        if not db_obj:
            return None if return_obj else False

        setattr(db_obj, 'is_deleted', True)
        setattr(db_obj, 'deleted_at', func.now())
        await self.db.flush()
        
        if return_obj:
            await self.db.refresh(db_obj)
            return db_obj
        return True

    async def restore(self, *, obj_id: Any, return_obj: bool = False) -> ModelType | None | bool:
        """恢复软删除的记录

        Args:
            obj_id: 记录主键
            return_obj: 是否返回被恢复的模型实例

        Returns:
            return_obj=True 时返回被恢复的实例，否则返回 True/False
        """
        if not hasattr(self.model, 'is_deleted'):
            raise NotImplementedError('模型不支持软删除')

        db_obj = await self.db.get(self.model, obj_id)
        if not db_obj or not db_obj.is_deleted:
            return None if return_obj else False

        setattr(db_obj, 'is_deleted', False)
        setattr(db_obj, 'deleted_at', None)
        await self.db.flush()
        
        if return_obj:
            await self.db.refresh(db_obj)
            return db_obj
        return True
