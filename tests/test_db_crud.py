"""
@Author     : zarkhan
@CreateDate : 2026/6/17
@Description: CRUDBase全方法集成测试（in-memory SQLite + aiosqlite）
"""
import pytest
from pydantic import BaseModel
from sqlalchemy import String
from lumary.exceptions import NotFoundError, BadRequestError, ConflictError
from sqlalchemy.orm import Mapped, mapped_column

from lumary.db.sa.base import Base
from lumary.db.sa.crud import CRUDBase
from lumary.db.sa.engine import create_db_engine
from lumary.db.sa.model import ModelBase
from lumary.db.sa.session import SessionFactory
from lumary.db.sa.mixins import SoftDeleteMixin


# ──────────────────────────────────────────────
# 测试用模型与Schema（普通模型）
# ──────────────────────────────────────────────
class _UserModel(ModelBase):
    __tablename__ = 'test_user'
    name: Mapped[str] = mapped_column(String(64))
    age: Mapped[int] = mapped_column(default=0)


class _UserCreate(BaseModel):
    name: str
    age: int = 0
    extra_field: str | None = None  # 用于测试多余字段容忍


class _UserUpdate(BaseModel):
    name: str | None = None
    age: int | None = None


class _UserCRUD(CRUDBase[_UserModel, _UserCreate, _UserUpdate]):
    model = _UserModel


# ──────────────────────────────────────────────
# 软删除模型
# ──────────────────────────────────────────────
class _PostModel(SoftDeleteMixin, ModelBase):
    __tablename__ = 'test_post'
    title: Mapped[str] = mapped_column(String(128))


class _PostCreate(BaseModel):
    title: str


class _PostUpdate(BaseModel):
    title: str | None = None


class _PostCRUD(CRUDBase[_PostModel, _PostCreate, _PostUpdate]):
    model = _PostModel


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────
@pytest.fixture(scope='module')
async def engine():
    _engine = create_db_engine('sqlite+aiosqlite:///:memory:')
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield _engine
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await _engine.dispose()


@pytest.fixture
async def session(engine):
    """每个测试用独立事务，测试后回滚保证隔离"""
    sf = SessionFactory(engine)
    async with sf.get_session() as db:
        async with db.begin_nested():  # savepoint
            yield db
            await db.rollback()


@pytest.fixture
def user_crud(session):
    return _UserCRUD(db=session)


@pytest.fixture
def post_crud(session):
    return _PostCRUD(db=session)


# ──────────────────────────────────────────────
# 初始化校验
# ──────────────────────────────────────────────
class TestCRUDInit:
    def test_valid_columns_populated(self, user_crud):
        assert 'name' in user_crud.valid_columns
        assert 'age' in user_crud.valid_columns
        assert 'id' in user_crud.valid_columns

    def test_no_model_raises(self, session):
        class _BadCRUD(CRUDBase):
            pass  # 没有model

        with pytest.raises(RuntimeError, match='必须显式定义model属性'):
            _BadCRUD(db=session)


# ──────────────────────────────────────────────
# Create
# ──────────────────────────────────────────────
class TestCreate:
    async def test_create_returns_model(self, user_crud):
        obj = await user_crud.create(obj_in=_UserCreate(name='Alice', age=25))
        assert obj.name == 'Alice'
        assert obj.age == 25

    async def test_create_assigns_id(self, user_crud):
        obj = await user_crud.create(obj_in=_UserCreate(name='Bob', age=30))
        assert obj.id is not None
        assert len(obj.id) > 0

    async def test_create_ignores_extra_fields(self, user_crud):
        """额外字段（不在模型列中）应被过滤掉"""
        schema = _UserCreate(name='Eve', age=20)
        obj = await user_crud.create(obj_in=schema)
        assert obj.name == 'Eve'

    async def test_create_with_extra_fields(self, user_crud):
        """测试Schema中包含ORM没有的额外字段，应被静默过滤"""
        obj_in = _UserCreate(name='Alice_Extra', age=25, extra_field='ignore_me')
        obj = await user_crud.create(obj_in=obj_in)
        assert obj.name == 'Alice_Extra'
        assert not hasattr(obj, 'extra_field')

    async def test_batch_create(self, user_crud):
        """测试批量创建"""
        objs_in = [
            _UserCreate(name='Batch1', age=1),
            _UserCreate(name='Batch2', age=2),
            {'name': 'BatchDict', 'age': 3, 'extra_field': 'ignore'}
        ]
        created_objs = await user_crud.batch_create(objs_in=objs_in)
        assert len(created_objs) == 3
        assert created_objs[0].name == 'Batch1'
        assert created_objs[2].name == 'BatchDict'

    async def test_batch_create_ignore_errors(self, user_crud):
        """测试批量创建忽略错误（SQLite in-memory对唯一约束支持有限，这里测试基本逻辑执行成功）"""
        objs_in = [
            _UserCreate(name='BatchErr1', age=1),
            _UserCreate(name='BatchErr2', age=2),
        ]
        created_objs = await user_crud.batch_create(objs_in=objs_in, ignore_errors=True)
        assert len(created_objs) == 2


# ──────────────────────────────────────────────
# Batch Create
# ──────────────────────────────────────────────
class TestBatchCreate:
    async def test_batch_create_all(self, user_crud):
        items = [_UserCreate(name=f'U{i}', age=i) for i in range(3)]
        objs = await user_crud.batch_create(objs_in=items)
        assert len(objs) == 3

    async def test_batch_create_from_dict(self, user_crud):
        dicts = [{'name': 'D1', 'age': 1}, {'name': 'D2', 'age': 2}]
        objs = await user_crud.batch_create(objs_in=dicts)
        assert len(objs) == 2

    async def test_batch_create_no_return_objects(self, user_crud):
        """return_objs=False应返回空列表"""
        items = [_UserCreate(name='NR1', age=10)]
        objs = await user_crud.batch_create(objs_in=items, return_objs=False)
        assert len(objs) == 0


# ──────────────────────────────────────────────
# Get
# ──────────────────────────────────────────────
class TestGet:
    async def test_get_by_id(self, user_crud):
        obj = await user_crud.create(obj_in=_UserCreate(name='Carol', age=40))
        fetched = await user_crud.get(obj.id)
        assert fetched.id == obj.id
        assert fetched.name == 'Carol'

    async def test_get_nonexistent_returns_none(self, user_crud):
        result = await user_crud.get('nonexistent-id')
        assert result is None

    async def test_get_with_options(self, user_crud):
        """测试带options查询不报错"""
        from sqlalchemy.orm import undefer
        obj = await user_crud.create(obj_in=_UserCreate(name='GetOpt', age=1))
        # sqlite没啥好join的，随便传个undefer验证不报错
        found = await user_crud.get(obj_id=obj.id, options=[undefer(_UserModel.name)])
        assert found is not None
        assert found.name == 'GetOpt'

    async def test_get_with_deleted_returns_none_for_missing(self, post_crud):
        result = await post_crud.get('nope', include_deleted=True)
        assert result is None


# ──────────────────────────────────────────────
# Get One
# ──────────────────────────────────────────────
class TestGetOne:
    async def test_get_one_by_field(self, user_crud):
        obj = await user_crud.create(obj_in=_UserCreate(name='GetOne', age=99))
        found = await user_crud.get_one(name='GetOne')
        assert found is not None
        assert found.id == obj.id

    async def test_get_one_not_found_returns_none(self, user_crud):
        result = await user_crud.get_one(name='__not_exist__')
        assert result is None

    async def test_get_one_invalid_field_raises(self, user_crud):
        with pytest.raises(BadRequestError, match='无效的查询字段'):
            await user_crud.get_one(invalid_col='x')


# ──────────────────────────────────────────────
# Get Count
# ──────────────────────────────────────────────
class TestGetCount:
    async def test_count_all(self, user_crud):
        await user_crud.create(obj_in=_UserCreate(name='C1', age=1))
        await user_crud.create(obj_in=_UserCreate(name='C2', age=2))
        count = await user_crud.get_count()
        assert count >= 2

    async def test_count_with_kwargs(self, user_crud):
        await user_crud.create(obj_in=_UserCreate(name='Unique_cnt', age=77))
        count = await user_crud.get_count(name='Unique_cnt')
        assert count >= 1


# ──────────────────────────────────────────────
# Get Multi
# ──────────────────────────────────────────────
class TestGetMulti:
    async def test_get_multi_returns_list(self, user_crud):
        await user_crud.create(obj_in=_UserCreate(name='M1', age=1))
        await user_crud.create(obj_in=_UserCreate(name='M2', age=2))
        items = await user_crud.get_multi()
        assert len(items) >= 2

    async def test_get_multi_with_limit(self, user_crud):
        for i in range(5):
            await user_crud.create(obj_in=_UserCreate(name=f'Lim{i}', age=i))
        items = await user_crud.get_multi(limit=2)
        assert len(items) <= 2

    async def test_get_multi_with_skip(self, user_crud):
        for i in range(3):
            await user_crud.create(obj_in=_UserCreate(name=f'Skip{i}', age=i))
        all_items = await user_crud.get_multi(limit=100)
        skipped = await user_crud.get_multi(skip=1, limit=100)
        assert len(skipped) == len(all_items) - 1

    async def test_get_multi_order_by(self, user_crud):
        await user_crud.create(obj_in=_UserCreate(name='Ord_A', age=10))
        await user_crud.create(obj_in=_UserCreate(name='Ord_B', age=20))
        items = await user_crud.get_multi(order_by=_UserModel.age.desc(), name='Ord_A')
        # 至少有一条结果，且结果正确
        assert any(i.name == 'Ord_A' for i in items)

    async def test_get_multi_invalid_kwarg_raises(self, user_crud):
        with pytest.raises(BadRequestError, match='无效的查询字段'):
            await user_crud.get_multi(bad_field='x')


# ──────────────────────────────────────────────
# Get Page
# ──────────────────────────────────────────────
class TestGetPage:
    async def test_get_page_returns_page_data(self, user_crud):
        for i in range(5):
            await user_crud.create(obj_in=_UserCreate(name=f'P{i}', age=i))
        page = await user_crud.get_page(page=1, size=3)
        assert page.size == 3
        assert page.total >= 5
        assert len(page.items) <= 3

    async def test_get_page_calculates_pages(self, user_crud):
        for i in range(4):
            await user_crud.create(obj_in=_UserCreate(name=f'Pg{i}', age=i))
        page = await user_crud.get_page(page=1, size=2)
        assert page.pages >= 2

    async def test_get_page(self, user_crud):
        """测试自动分页方法get_page"""
        # 清空环境数据或使用特定的特征标识
        await user_crud.create(obj_in=_UserCreate(name='Page1', age=100))
        await user_crud.create(obj_in=_UserCreate(name='Page2', age=100))
        await user_crud.create(obj_in=_UserCreate(name='Page3', age=100))
        
        # 请求第一页，每页2条
        page_data = await user_crud.get_page(age=100, page=1, size=2)
        assert page_data.total == 3
        assert page_data.pages == 2
        assert len(page_data.items) == 2
        
        # 请求第二页，每页2条
        page_data_2 = await user_crud.get_page(age=100, page=2, size=2)
        assert len(page_data_2.items) == 1
        
        # 请求没有数据的一页
        page_data_empty = await user_crud.get_page(age=999, page=1, size=10)
        assert page_data_empty.total == 0
        assert len(page_data_empty.items) == 0


# ──────────────────────────────────────────────
# Update
# ──────────────────────────────────────────────
class TestUpdate:
    async def test_update_with_schema(self, user_crud):
        obj = await user_crud.create(obj_in=_UserCreate(name='UpdOld', age=1))
        updated, changed = await user_crud.update(db_obj_in=obj, obj_in=_UserUpdate(name='UpdNew'))
        assert updated.name == 'UpdNew'
        assert changed is True

    async def test_update_with_dict(self, user_crud):
        obj = await user_crud.create(obj_in=_UserCreate(name='Bob', age=30))
        updated, changed = await user_crud.update(db_obj_in=obj, obj_in={'name': 'BobDict', 'age': 32})
        assert updated.name == 'BobDict'
        assert updated.age == 32
        assert changed is True

    async def test_update_with_extra_fields(self, user_crud):
        """测试Update Schema中有多余字段"""
        obj = await user_crud.create(obj_in=_UserCreate(name='Extra', age=20))
        updated, changed = await user_crud.update(db_obj_in=obj, obj_in={'name': 'Extra2', 'extra_field': 'hello'})
        assert updated.name == 'Extra2'
        assert not hasattr(updated, 'extra_field')
        assert changed is True

    async def test_update_ignores_invalid_fields(self, user_crud):
        """字典中不在valid_columns的字段应被过滤"""
        obj = await user_crud.create(obj_in=_UserCreate(name='FilterOld', age=3))
        updated, changed = await user_crud.update(db_obj_in=obj, obj_in={'name': 'FilterNew', 'bad_col': 'x'})
        assert updated.name == 'FilterNew'
        assert changed is True

    async def test_update_no_real_change(self, user_crud):
        """测试没有实际变更的情况"""
        obj = await user_crud.create(obj_in=_UserCreate(name='NoChange', age=10))
        updated, changed = await user_crud.update(db_obj_in=obj, obj_in={'name': 'NoChange', 'age': 10})
        assert changed is False


# ──────────────────────────────────────────────
# Remove（物理删除）
# ──────────────────────────────────────────────
class TestRemove:
    async def test_remove_by_obj(self, user_crud):
        obj = await user_crud.create(obj_in=_UserCreate(name='DelObj', age=1))
        deleted = await user_crud.remove(db_obj_in=obj)
        assert deleted.id == obj.id
        result = await user_crud.get(obj.id)
        assert result is None

    async def test_remove_by_id(self, user_crud):
        obj = await user_crud.create(obj_in=_UserCreate(name='DelId', age=2))
        await user_crud.remove(obj_id=obj.id)
        result = await user_crud.get(obj.id)
        assert result is None

    async def test_remove_no_args_raises(self, user_crud):
        with pytest.raises(BadRequestError, match='必须传入'):
            await user_crud.remove()

    async def test_remove_nonexistent_id_returns_none(self, user_crud):
        result = await user_crud.remove(obj_id='ghost-id')
        assert result is None


# ──────────────────────────────────────────────
# 软删除（soft_delete / restore）
# ──────────────────────────────────────────────
class TestSoftDelete:
    async def test_soft_delete_sets_flag(self, post_crud):
        obj = await post_crud.create(obj_in=_PostCreate(title='ToDelete'))
        deleted = await post_crud.soft_delete(obj_id=obj.id)
        assert deleted.is_deleted is True
        assert deleted.deleted_at is not None

    async def test_soft_deleted_hidden_from_get(self, post_crud):
        obj = await post_crud.create(obj_in=_PostCreate(title='Hidden'))
        await post_crud.soft_delete(obj_id=obj.id)
        result = await post_crud.get(obj.id)
        assert result is None

    async def test_soft_deleted_visible_via_get_with_deleted(self, post_crud):
        obj = await post_crud.create(obj_in=_PostCreate(title='Visible'))
        await post_crud.soft_delete(obj_id=obj.id)
        result = await post_crud.get(obj.id, include_deleted=True)
        assert result is not None
        assert result.is_deleted is True

    async def test_restore_clears_flag(self, post_crud):
        obj = await post_crud.create(obj_in=_PostCreate(title='Restore'))
        await post_crud.soft_delete(obj_id=obj.id)
        restored = await post_crud.restore(obj_id=obj.id)
        assert restored.is_deleted is False
        assert restored.deleted_at is None

    async def test_soft_delete_on_non_soft_model_raises(self, user_crud):
        """普通模型（无SoftDeleteMixin）调用软删除应抛出ConflictError"""
        obj = await user_crud.create(obj_in=_UserCreate(name='NonSoft', age=1))
        with pytest.raises(ConflictError, match='不支持软删除'):
            await user_crud.soft_delete(obj_id=obj.id)

    async def test_soft_delete_return_obj(self, post_crud):
        """测试软删除时返回被删除的实体"""
        obj = await post_crud.create(obj_in=_PostCreate(title='ReturnObj'))
        deleted_obj = await post_crud.soft_delete(obj_id=obj.id)
        assert deleted_obj.id == obj.id
        assert deleted_obj.is_deleted is True

    async def test_restore_unsupported_model(self, user_crud):
        obj = await user_crud.create(obj_in=_UserCreate(name='NoRestore', age=1))
        with pytest.raises(ConflictError):
            await user_crud.restore(obj_id=obj.id)

    async def test_restore_success(self, post_crud):
        """测试恢复软删除"""
        obj = await post_crud.create(obj_in=_PostCreate(title='ToRestore'))
        await post_crud.soft_delete(obj_id=obj.id)

        # 已软删除，正常get查不到
        result = await post_crud.get(obj.id)
        assert result is None

        # 恢复
        restored_obj = await post_crud.restore(obj_id=obj.id)
        assert restored_obj.is_deleted is False
        assert restored_obj.deleted_at is None

        # 恢复后可以get到
        found = await post_crud.get(obj.id)
        assert found.id == obj.id

    async def test_soft_deleted_hidden_from_get_multi(self, post_crud):
        obj = await post_crud.create(obj_in=_PostCreate(title='MultiHide'))
        await post_crud.soft_delete(obj_id=obj.id)
        items = await post_crud.get_multi()
        ids = [i.id for i in items]
        assert obj.id not in ids

    async def test_soft_deleted_hidden_from_get_count(self, post_crud):
        obj = await post_crud.create(obj_in=_PostCreate(title='CountHide'))
        count_before = await post_crud.get_count()
        await post_crud.soft_delete(obj_id=obj.id)
        count_after = await post_crud.get_count()
        assert count_after == count_before - 1


# ──────────────────────────────────────────────
# execute_stmt / execute_sql
# ──────────────────────────────────────────────
class TestExecute:
    async def test_execute_sql_select(self, user_crud):
        result = await user_crud.execute_sql(sql='SELECT 1 AS val')
        assert result.fetchone()[0] == 1

    async def test_execute_sql_with_params(self, user_crud):
        await user_crud.create(obj_in=_UserCreate(name='SqlParam', age=11))
        result = await user_crud.execute_sql(
            sql='SELECT name FROM test_user WHERE age = :age',
            params={'age': 11}
        )
        rows = result.fetchall()
        assert any(r[0] == 'SqlParam' for r in rows)

    async def test_execute_stmt_select(self, user_crud):
        from sqlalchemy.sql import select as sa_select
        stmt = sa_select(_UserModel).limit(5)
        result = await user_crud.execute_stmt(stmt=stmt)
        assert result is not None
