"""
@Author     : zarkhan
@CreateDate : 2026/6/17
@Description: SoftDeleteMixin / AuditMixin字段定义测试
"""
import pytest
from sqlalchemy import String, inspect as sa_inspect
from sqlalchemy.orm import Mapped, mapped_column

from lumary.db.sqlalchemy.base import Base
from lumary.db.sqlalchemy.model import ModelBase
from lumary.common.mixins.sqlalchemy import SoftDeleteMixin, AuditMixin


# ──────────────────────────────────────────────
# 测试用模型
# ──────────────────────────────────────────────
class _SoftModel(SoftDeleteMixin, ModelBase):
    __tablename__ = 'mixin_soft'
    title: Mapped[str] = mapped_column(String(64))


class _AuditModel(AuditMixin, ModelBase):
    __tablename__ = 'mixin_audit'
    title: Mapped[str] = mapped_column(String(64))


class _FullModel(SoftDeleteMixin, AuditMixin, ModelBase):
    __tablename__ = 'mixin_full'
    title: Mapped[str] = mapped_column(String(64))


# ──────────────────────────────────────────────
# SoftDeleteMixin
# ──────────────────────────────────────────────
class TestSoftDeleteMixin:
    def _cols(self, model):
        mapper = sa_inspect(model)
        return {c.key for c in mapper.mapper.column_attrs}

    def test_has_is_deleted_column(self):
        assert 'is_deleted' in self._cols(_SoftModel)

    def test_has_deleted_at_column(self):
        assert 'deleted_at' in self._cols(_SoftModel)

    def test_is_deleted_default_false(self):
        obj = _SoftModel(title='t')
        # 通过列的default属性验证
        col = _SoftModel.__table__.c['is_deleted']
        assert col.default.arg is False

    def test_deleted_at_nullable(self):
        col = _SoftModel.__table__.c['deleted_at']
        assert col.nullable is True

    def test_model_is_subclass_of_soft_delete_mixin(self):
        assert issubclass(_SoftModel, SoftDeleteMixin)

    def test_plain_model_not_subclass(self):
        class _Plain(ModelBase):
            __tablename__ = 'mixin_plain'
            title: Mapped[str] = mapped_column(String(16))

        assert not issubclass(_Plain, SoftDeleteMixin)


# ──────────────────────────────────────────────
# AuditMixin
# ──────────────────────────────────────────────
class TestAuditMixin:
    def _cols(self, model):
        mapper = sa_inspect(model)
        return {c.key for c in mapper.mapper.column_attrs}

    def test_has_created_by_column(self):
        assert 'created_by' in self._cols(_AuditModel)

    def test_has_updated_by_column(self):
        assert 'updated_by' in self._cols(_AuditModel)

    def test_created_by_nullable(self):
        col = _AuditModel.__table__.c['created_by']
        assert col.nullable is True

    def test_updated_by_nullable(self):
        col = _AuditModel.__table__.c['updated_by']
        assert col.nullable is True

    def test_created_by_max_length(self):
        col = _AuditModel.__table__.c['created_by']
        assert col.type.length == 64


# ──────────────────────────────────────────────
# 组合Mixin
# ──────────────────────────────────────────────
class TestFullMixinModel:
    def _cols(self, model):
        mapper = sa_inspect(model)
        return {c.key for c in mapper.mapper.column_attrs}

    def test_has_all_columns(self):
        cols = self._cols(_FullModel)
        for col in ('id', 'created_at', 'updated_at', 'is_deleted', 'deleted_at', 'created_by', 'updated_by'):
            assert col in cols, f'缺少列：{col}'

    def test_is_subclass_of_both_mixins(self):
        assert issubclass(_FullModel, SoftDeleteMixin)
        assert issubclass(_FullModel, AuditMixin)


# ──────────────────────────────────────────────
# ModelBase基础字段
# ──────────────────────────────────────────────
class TestModelBase:
    def _cols(self, model):
        mapper = sa_inspect(model)
        return {c.key for c in mapper.mapper.column_attrs}

    def test_has_id_column(self):
        assert 'id' in self._cols(_SoftModel)

    def test_has_created_at_column(self):
        assert 'created_at' in self._cols(_SoftModel)

    def test_has_updated_at_column(self):
        assert 'updated_at' in self._cols(_SoftModel)

    def test_id_is_primary_key(self):
        col = _SoftModel.__table__.c['id']
        assert col.primary_key is True

    def test_id_max_length_26(self):
        col = _SoftModel.__table__.c['id']
        assert col.type.length == 26

    def test_id_default_generates_ulid(self):
        obj = _SoftModel(title='test')
        # 触发default函数
        if callable(_SoftModel.__table__.c['id'].default.arg):
            try:
                generated = _SoftModel.__table__.c['id'].default.arg(None)
            except TypeError:
                generated = _SoftModel.__table__.c['id'].default.arg()
            assert isinstance(generated, str)
            assert len(generated) == 26
