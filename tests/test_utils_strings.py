"""
@Author     : zarkhan
@CreateDate : 2026/6/17
@Description: strings工具函数单元测试
"""
import json
import pytest

from lumary.common.utils.strings import (
    camel_to_snake,
    snake_to_camel,
    random_string,
    json_dumps,
    json_loads,
    ORJSON_INSTALLED)


# ──────────────────────────────────────────────
# camel_to_snake
# ──────────────────────────────────────────────
class TestCamelToSnake:
    @pytest.mark.parametrize('input_s, expected', [
        ('CamelCase',        'camel_case'),
        ('camelCase',        'camel_case'),
        ('MyHTTPRequest',    'my_h_t_t_p_request'),
        ('simple',           'simple'),
        ('A',                'a'),
        ('ABCDef',           'a_b_c_def'),
        ('already_snake',    'already_snake'),
    ])
    def test_conversion(self, input_s, expected):
        assert camel_to_snake(input_s) == expected

    def test_empty_string(self):
        assert camel_to_snake('') == ''

    def test_single_uppercase(self):
        assert camel_to_snake('X') == 'x'

    def test_no_leading_underscore(self):
        """首字符大写不应产生前导下划线"""
        result = camel_to_snake('MyClass')
        assert not result.startswith('_')


# ──────────────────────────────────────────────
# snake_to_camel
# ──────────────────────────────────────────────
class TestSnakeToCamel:
    @pytest.mark.parametrize('input_s, expected', [
        ('snake_case',       'SnakeCase'),
        ('my_http_request',  'MyHttpRequest'),
        ('simple',           'Simple'),
        ('a_b_c',            'ABC'),
        ('already',          'Already'),
        ('one_word',         'OneWord'),
    ])
    def test_conversion(self, input_s, expected):
        assert snake_to_camel(input_s) == expected

    def test_empty_string(self):
        assert snake_to_camel('') == ''

    def test_leading_underscore_ignored(self):
        """下划线开头时第一个分量为空，title() 产生空字符串"""
        result = snake_to_camel('_hidden')
        assert 'Hidden' in result


# ──────────────────────────────────────────────
# random_string
# ──────────────────────────────────────────────
class TestRandomString:
    def test_default_length(self):
        s = random_string()
        assert len(s) == 16

    def test_custom_length(self):
        for length in (1, 8, 32, 64):
            assert len(random_string(length)) == length

    def test_contains_only_alphanumeric(self):
        s = random_string(100)
        assert s.isalnum()

    def test_uniqueness(self):
        results = {random_string() for _ in range(100)}
        # 随机性足够，100次几乎不会重复
        assert len(results) > 90

    def test_zero_length(self):
        assert random_string(0) == ''


# ──────────────────────────────────────────────
# json_dumps / json_loads（标准库路径）
# ──────────────────────────────────────────────
class TestJsonDumps:
    def test_serialize_dict(self):
        data = {'key': 'value', 'num': 42}
        result = json_dumps(data)
        assert isinstance(result, str)
        assert json.loads(result) == data

    def test_serialize_list(self):
        data = [1, 2, 3]
        assert json.loads(json_dumps(data)) == data

    def test_serialize_nested(self):
        data = {'a': {'b': [1, 2, {'c': True}]}}
        assert json.loads(json_dumps(data)) == data

    def test_serialize_chinese(self):
        """中文字符不应被ASCII转义"""
        data = {'name': '张三'}
        result = json_dumps(data)
        assert '张三' in result

    def test_serialize_empty_dict(self):
        assert json_dumps({}) == '{}'

    def test_serialize_none(self):
        assert json.loads(json_dumps(None)) is None


class TestJsonLoads:
    def test_deserialize_str(self):
        assert json_loads('{"k": 1}') == {'k': 1}

    def test_deserialize_bytes(self):
        assert json_loads(b'{"k": 2}') == {'k': 2}

    def test_deserialize_list(self):
        assert json_loads('[1,2,3]') == [1, 2, 3]

    def test_deserialize_null(self):
        assert json_loads('null') is None

    def test_round_trip(self):
        data = {'chinese': '中文', 'num': 3.14, 'flag': True}
        assert json_loads(json_dumps(data)) == data


# ──────────────────────────────────────────────
# HAS_ORJSON标志
# ──────────────────────────────────────────────
class TestHasOrjson:
    def test_has_orjson_is_bool(self):
        assert isinstance(ORJSON_INSTALLED, bool)
