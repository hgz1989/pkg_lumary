"""
@Author     : zarkhan
@CreateDate : 2026/6/17
@Description: Schema、PageData、响应工厂函数单元测试
"""
import pytest
from pydantic import ValidationError

from lumary.middleware import set_request_id
from lumary.schemas import (
    SchemaBase,
    PageParams,
    TimeRangeParams,
    KeywordParams,
    BatchIds,
    PageData,
    APIResponse,
    response_success,
    response_fail)


# ──────────────────────────────────────────────
# 辅助Schema
# ──────────────────────────────────────────────
class _Item(SchemaBase):
    name: str
    value: int


# ──────────────────────────────────────────────
# SchemaBase
# ──────────────────────────────────────────────
class TestSchemaBase:
    def test_extra_fields_ignored(self):
        """多余字段应被忽略，不报错"""
        obj = _Item(name='x', value=1, extra_field='ignored')
        assert not hasattr(obj, 'extra_field')

    def test_from_attributes(self):
        """支持从ORM-like对象读取属性"""
        class _FakeOrm:
            name = 'orm'
            value = 99
        obj = _Item.model_validate(_FakeOrm())
        assert obj.name == 'orm'
        assert obj.value == 99


# ──────────────────────────────────────────────
# PageQuery
# ──────────────────────────────────────────────
class TestPageQuery:
    def test_defaults(self):
        q = PageParams()
        assert q.page == 1
        assert q.size == 100

    def test_valid_values(self):
        q = PageParams(page=3, size=50)
        assert q.page == 3
        assert q.size == 50

    def test_page_minimum(self):
        with pytest.raises(ValidationError):
            PageParams(page=0)

    def test_size_minimum(self):
        with pytest.raises(ValidationError):
            PageParams(size=0)

    def test_size_maximum(self):
        with pytest.raises(ValidationError):
            PageParams(size=1001)


# ──────────────────────────────────────────────
# TimeRangeQuery
# ──────────────────────────────────────────────
class TestTimeRangeQuery:
    def test_defaults_none(self):
        q = TimeRangeParams()
        assert q.start_time is None
        assert q.end_time is None

    def test_with_values(self):
        from datetime import datetime
        dt = datetime(2026, 1, 1)
        q = TimeRangeParams(start_time=dt, end_time=dt)
        assert q.start_time == dt


# ──────────────────────────────────────────────
# KeywordQuery
# ──────────────────────────────────────────────
class TestKeywordQuery:
    def test_default_none(self):
        assert KeywordParams().keyword is None

    def test_max_length(self):
        with pytest.raises(ValidationError):
            KeywordParams(keyword='x' * 101)


# ──────────────────────────────────────────────
# BatchIds
# ──────────────────────────────────────────────
class TestBatchIds:
    def test_int_ids(self):
        b = BatchIds(ids=[1, 2, 3])
        assert b.ids == [1, 2, 3]

    def test_str_ids(self):
        b = BatchIds(ids=['a', 'b'])
        assert b.ids == ['a', 'b']

    def test_empty_ids_raises(self):
        with pytest.raises(ValidationError):
            BatchIds(ids=[])


# ──────────────────────────────────────────────
# PageData & PageData.build
# ──────────────────────────────────────────────
class TestPageData:
    def test_build_calculates_pages(self):
        pd = PageData.build(items=['a', 'b', 'c'], page=1, size=2, total=5)
        assert pd.pages == 3   # ceil(5/2)
        assert pd.total == 5
        assert pd.page == 1
        assert pd.size == 2
        assert list(pd.items) == ['a', 'b', 'c']

    def test_build_exact_division(self):
        pd = PageData.build(items=[], page=2, size=10, total=20)
        assert pd.pages == 2

    def test_build_zero_total(self):
        pd = PageData.build(items=[], page=1, size=10, total=0)
        assert pd.pages == 0

    def test_build_size_zero_safe(self):
        """size=0时不应触发ZeroDivisionError，pages应为0"""
        pd = PageData.build(items=[], page=1, size=0, total=100)
        assert pd.pages == 0

    def test_default_values(self):
        pd = PageData()
        assert pd.page == 1
        assert pd.size == 10
        assert pd.pages == 0
        assert pd.total == 0


# ──────────────────────────────────────────────
# response_success / response_fail
# ──────────────────────────────────────────────
class TestResponseFunctions:
    @pytest.fixture(autouse=True)
    def set_rid(self):
        set_request_id('test-rid-001')

    def test_response_success_defaults(self):
        resp = response_success()
        assert isinstance(resp, APIResponse)
        assert resp.code == 0
        assert resp.message == '操作成功'
        assert resp.data is None
        assert resp.request_id == 'test-rid-001'

    def test_response_success_with_data(self):
        item = _Item(name='x', value=1)
        resp = response_success(data=item, message='ok')
        assert resp.data == item
        assert resp.message == 'ok'

    def test_response_fail(self):
        resp = response_fail(code=404, message='未找到')
        assert resp.code == 404
        assert resp.message == '未找到'
        assert resp.data is None

    def test_response_fail_default_message(self):
        # response_fail必须传入message
        with pytest.raises(TypeError):
            response_fail(code=500)

    def test_response_success_with_extra(self):
        item = _Item(name='x', value=1)
        extra = _Item(name='e', value=2)
        resp = response_success(data=item, extra=extra)
        assert isinstance(resp, APIResponse)
        assert resp.code == 0
        assert resp.data == item
        assert resp.extra == extra

    def test_response_fail_with_extra(self):
        extra = _Item(name='e', value=2)
        resp = response_fail(code=400, message='参数错误', extra=extra)
        assert isinstance(resp, APIResponse)
        assert resp.code == 400
        assert resp.message == '参数错误'
        assert resp.extra == extra
