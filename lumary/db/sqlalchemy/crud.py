"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: SQLAlchemy CRUD 泛型基类
"""
from collections.abc import Sequence
from typing import TypeVar, Generic, Any

from pydantic import BaseModel
from sqlalchemy import (
    inspect as sa_inspect,
    Select,
    text
)
from sqlalchemy.exc import (
    NoResultFound,
    IntegrityError,
    InvalidRequestError
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func, select

from .model import ModelBase
from ...common.mixins.sqlalchemy import SoftDeleteMixin
from ...schemas import PageData

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

        # 使用 inspect 获取映射列，兼容性更好，同时缓存避免重复计算
        mapper = sa_inspect(self.model)

        self.valid_columns = {col.key for col in mapper.mapper.column_attrs}

    async def create(self, *, obj_in: CreateSchemaType) -> ModelType:
        """创建新记录

        Args:
            obj_in: 创建记录的 Pydantic 模型

        Returns:
            创建成功的模型实例
        """
        obj_in_data = {k: v for k, v in obj_in.model_dump(exclude_unset=True).items() if k in self.valid_columns}

        db_obj = self.model(**obj_in_data)
        self.db.add(db_obj)
        await self.db.flush()
        return db_obj

    async def batch_create(
            self, *, objs_in: list[CreateSchemaType | dict],
            ignore_errors: bool = False,
            return_objs: bool = True
    ) -> list[ModelType]:
        """批量创建记录

        Args:
            objs_in: 待创建的数据列表（Schema 或 dict）
            ignore_errors: 是否忽略单条插入的错误（如唯一键冲突）
                           如果为 False，遇到错误将抛出异常，整个事务可以被调用方回滚
                           如果为 True，将跳过出错的记录，只插入成功的数据
            return_objs: 是否需要返回带有数据库默认值（如ID）的完整模型对象
                         为 True 时使用 add_all + flush（性能略低，但能拿到所有 ID）；
                         为 False 时未来可优化为 execute(insert().values()) 提高性能

        Returns:
            成功创建的模型实例列表
        """
        # 场景 1：要求全部成功，且需要返回对象
        if not ignore_errors:
            db_objs = []

            for obj_in in objs_in:
                obj_data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump()
                obj_data = {k: v for k, v in obj_data.items() if k in self.valid_columns}

                db_obj = self.model(**obj_data)
                db_objs.append(db_obj)

            self.db.add_all(db_objs)

            if return_objs:
                await self.db.flush()

            return db_objs

        # 场景 2：忽略错误记录（如某条数据冲突不影响其他数据入库）
        # 这种模式下只能逐条 add + flush 并捕获异常，因为批量 add_all 会导致整个 flush 失败
        successful_objs = []

        for obj_in in objs_in:
            obj_data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump()
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
                # 必须从 session 中移除该对象，否则后续 flush 可能再次触发同一错误
                self.db.expunge(db_obj)

        return successful_objs

    async def _update_soft_del_flag(self, obj_id: Any, is_deleted: bool) -> ModelType:
        """统一处理软删除/恢复的公共逻辑

        Args:
            obj_id: 记录主键
            is_deleted: 是否软删除

        Returns:
            被删除或恢复的实例
        """
        if not issubclass(self.model, SoftDeleteMixin):
            raise NotImplementedError('模型不支持软删除')

        # 区分：删除查正常数据，恢复要查已删除数据
        if is_deleted:
            db_obj = await self.get(obj_id)
            db_obj.is_deleted = True
            db_obj.deleted_at = func.now()
        else:
            db_obj = await self.get_with_deleted(obj_id)

            # 必须判空，因为可能返回 None
            if db_obj is None:
                raise NoResultFound(f'{self.model.__name__}记录不存在: id={obj_id}')

            # 有对象才能操作属性
            if not db_obj.is_deleted:
                raise InvalidRequestError('数据未被删除，无需恢复')

            db_obj.is_deleted = False
            db_obj.deleted_at = None

        await self.db.flush()
        await self.db.refresh(db_obj)
        return db_obj

    async def soft_delete(self, *, obj_id: Any) -> ModelType:
        """软删除记录

        Args:
            obj_id: 记录主键

        Returns:
            返回被删除的实例
        """
        return await self._update_soft_del_flag(obj_id=obj_id, is_deleted=True)

    async def restore(self, *, obj_id: Any) -> ModelType:
        """恢复软删除的记录

        Args:
            obj_id: 记录主键

        Returns:
            返回被恢复的实例
        """
        return await self._update_soft_del_flag(obj_id=obj_id, is_deleted=False)

    async def remove(self, *, db_obj: ModelType | None = None, obj_id: Any = None) -> ModelType:
        """物理删除记录

        Args:
            db_obj: 已存在的模型实例（优先使用）
            obj_id: 记录主键（obj 不存在时使用）

        Returns:
            被删除的模型实例
        """
        # 第一步：参数合法性校验
        if db_obj is None and obj_id is None:
            raise ValueError('必须传入db_obj或obj_id中的至少一个')

        # 如果已经传入 obj，直接使用，不再查库
        if db_obj is None:
            db_obj = await self.get(obj_id)

        await self.db.delete(db_obj)
        await self.db.flush()
        return db_obj

    async def update(self, *, db_obj: ModelType, obj_in: UpdateSchemaType | dict[str, Any]) -> ModelType:
        """更新记录

        Args:
            db_obj: 需要更新的数据库模型实例
            obj_in: 包含更新数据的字典或 Pydantic 模型

        Returns:
            更新后的模型实例
        """
        update_data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        update_data = {k: v for k, v in update_data.items() if k in self.valid_columns}

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        await self.db.flush()
        await self.db.refresh(db_obj)
        return db_obj

    async def get(self, obj_id: Any, options: list | None = None, **kwargs: Any) -> ModelType:
        """根据主键获取单条记录

        Args:
            obj_id: 记录主键
            options: SQLAlchemy 加载策略列表

        Returns:
            查询到的模型实例或为空
        """
        db_obj = await self.db.get(self.model, obj_id, options=options, **kwargs)

        if db_obj is None:
            raise NoResultFound(f'{self.model.__name__}记录不存在: id={obj_id}')

        if issubclass(self.model, SoftDeleteMixin) and db_obj.is_deleted:
            raise NoResultFound(f'{self.model.__name__}记录已被删除: id={obj_id}')

        return db_obj

    async def get_with_deleted(self, obj_id: Any) -> ModelType | None:
        """查询主键记录，包含已软删除的数据

        使用 SQLAlchemy 原生主键查找，自动适配任意主键名称和复合主键。

        Args:
            obj_id: 数据主键ID

        Returns:
            匹配主键的实体对象；无匹配数据时返回 None
        """
        return await self.db.get(self.model, obj_id)

    def _apply_soft_delete_filter(self, stmt: Select) -> Select:
        """为查询语句添加软删除过滤条件

        如果模型支持软删除，则自动过滤已删除的记录

        Args:
            stmt: SQLAlchemy 查询语句

        Returns:
            添加了软删除过滤条件的查询语句
        """
        if issubclass(self.model, SoftDeleteMixin):
            stmt = stmt.where(self.model.is_deleted.is_(False))

        return stmt

    def _apply_kwargs_filter(self, stmt: Select, kwargs: dict[str, Any]) -> Select:
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

    async def get_one(self, *, options: list | None = None, **kwargs: Any) -> ModelType | None:
        """根据多个字段条件获取单条记录（AND 关系）

        Args:
            options: SQLAlchemy 加载策略列表，用于外键关联查询
            **kwargs: 字段名和值的键值对

        Returns:
            查询到的模型实例或为空
        """
        stmt = select(self.model)
        stmt = self._apply_soft_delete_filter(stmt)
        stmt = self._apply_kwargs_filter(stmt, kwargs)

        if options:
            stmt = stmt.options(*options)

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_count(self, *criteria: Any, options: list | None = None, **kwargs: Any) -> int:
        """统计记录总数

        Args:
            *criteria: SQLAlchemy 查询条件
            options: SQLAlchemy 加载策略列表，用于外键关联查询
            **kwargs: 精确匹配的过滤条件

        Returns:
            记录总数
        """
        stmt = select(func.count()).select_from(self.model)
        stmt = self._apply_soft_delete_filter(stmt)

        if criteria:
            stmt = stmt.where(*criteria)

        stmt = self._apply_kwargs_filter(stmt, kwargs)
        if options:
            stmt = stmt.options(*options)

        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def get_multi(
            self,
            *criteria: Any,
            skip: int = 0,
            limit: int = 100,
            order_by: Any | Sequence[Any] | None = None,
            options: list | None = None,
            **kwargs: Any,
    ) -> Sequence[ModelType]:
        """获取多条记录支持分页、条件过滤和排序

        Args:
            *criteria: SQLAlchemy 查询条件 (如 model.age > 18)
            skip: 跳过的记录数量
            limit: 返回的最大记录数量
            order_by: 排序字段或字段列表 (如 model.id.desc())
            options: SQLAlchemy 加载策略列表，用于外键关联查询
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
            stmt = stmt.order_by(*order_by) if isinstance(order_by, (list, tuple)) else stmt.order_by(order_by)

        if options:
            stmt = stmt.options(*options)

        stmt = stmt.offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_page(
            self,
            *criteria: Any,
            page: int = 1,
            size: int = 100,
            order_by: Any | Sequence[Any] | None = None,
            options: list | None = None,
            **kwargs: Any,
    ) -> PageData[ModelType]:
        """获取分页数据，自动查询总数并构建 PageData

        封装了先查总数再查分页数据的标准分页流程，调用方无需手动计算 skip

        Args:
            *criteria: SQLAlchemy 查询条件 (如 model.age > 18)
            page: 当前页码（从 1 开始）
            size: 每页数量
            order_by: 排序字段或字段列表 (如 model.id.desc())
            options: SQLAlchemy 加载策略列表，用于外键关联查询
            **kwargs: 精确匹配的过滤条件 (如 status=1)

        Returns:
            包含当前页数据与分页元信息的 PageData 对象
        """
        skip = (page - 1) * size
        total = await self.get_count(*criteria, **kwargs)
        items = await self.get_multi(
            *criteria,
            skip=skip,
            limit=size,
            order_by=order_by,
            options=options,
            **kwargs,
        )
        return PageData.build(items=list(items), page=page, size=size, total=total)

    async def execute_stmt(self, *, stmt: Any, options: list | None = None) -> Any:
        """执行外部传入的 SQLAlchemy 语句

        支持 Select / Insert / Update / Delete 等任意可执行语句，
        调用方自行处理返回结果（scalars / fetchone / fetchall 等）

        Args:
            stmt: SQLAlchemy 可执行语句
            options: SQLAlchemy 加载策略列表，用于外键关联查询

        Returns:
            语句执行结果
        """
        if options:
            stmt = stmt.options(*options)

        return await self.db.execute(stmt)

    async def execute_sql(self, *, sql: str, params: dict[str, Any] | None = None) -> Any:
        """执行原始 SQL 语句

        调用方自行处理返回结果（scalars / fetchone / fetchall 等）

        Args:
            sql: 原始 SQL 语句文本
            params: SQL 参数绑定

        Returns:
            SQL 执行结果
        """
        return await self.db.execute(text(sql), params or {})
