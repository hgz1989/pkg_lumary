"""
@Author     : zarkhan
@CreateDate : 2026/6/17
@Description: add_datetime工具函数全场景单元测试
"""
from datetime import datetime, timezone, timedelta

import pytest

from lumary.common.utils.datetimekit import add_datetime


class TestAddDatetimeDays:
    def test_add_positive_days(self):
        dt = datetime(2026, 1, 1)
        result = add_datetime(dt, days=10)
        assert result == datetime(2026, 1, 11)

    def test_add_negative_days(self):
        dt = datetime(2026, 1, 15)
        result = add_datetime(dt, days=-5)
        assert result == datetime(2026, 1, 10)

    def test_add_zero_days(self):
        dt = datetime(2026, 3, 15, 12, 30, 0)
        assert add_datetime(dt) == dt


class TestAddDatetimeMonths:
    def test_add_one_month(self):
        dt = datetime(2026, 1, 15)
        assert add_datetime(dt, months=1) == datetime(2026, 2, 15)

    def test_add_months_crosses_year(self):
        dt = datetime(2026, 11, 15)
        assert add_datetime(dt, months=2) == datetime(2027, 1, 15)

    def test_subtract_months(self):
        dt = datetime(2026, 3, 10)
        assert add_datetime(dt, months=-2) == datetime(2026, 1, 10)

    def test_subtract_months_crosses_year(self):
        dt = datetime(2026, 2, 5)
        assert add_datetime(dt, months=-3) == datetime(2025, 11, 5)

    def test_add_months_clamps_day_end_of_month(self):
        """1月31日加1个月，2月没有31日，应截断到28日"""
        dt = datetime(2026, 1, 31)
        result = add_datetime(dt, months=1)
        assert result == datetime(2026, 2, 28)

    def test_add_months_leap_year(self):
        """非闰年1月31日 + 1月 → 2月28日；闰年 → 2月29日"""
        dt_non_leap = datetime(2026, 1, 31)
        dt_leap = datetime(2024, 1, 31)
        assert add_datetime(dt_non_leap, months=1).day == 28
        assert add_datetime(dt_leap, months=1).day == 29

    def test_add_12_months_equals_one_year(self):
        dt = datetime(2026, 6, 15)
        assert add_datetime(dt, months=12) == datetime(2027, 6, 15)

    def test_add_large_months(self):
        """超过12个月应正确进位"""
        dt = datetime(2026, 1, 1)
        result = add_datetime(dt, months=25)
        assert result == datetime(2028, 2, 1)


class TestAddDatetimeYears:
    def test_add_one_year(self):
        dt = datetime(2026, 6, 15)
        assert add_datetime(dt, years=1) == datetime(2027, 6, 15)

    def test_subtract_years(self):
        dt = datetime(2026, 6, 15)
        assert add_datetime(dt, years=-2) == datetime(2024, 6, 15)

    def test_add_year_leap_to_non_leap(self):
        """闰年2月29日 + 1年 → 非闰年应截断到2月28日"""
        dt = datetime(2024, 2, 29)
        result = add_datetime(dt, years=1)
        assert result == datetime(2025, 2, 28)


class TestAddDatetimeTime:
    def test_add_hours(self):
        dt = datetime(2026, 1, 1, 10, 0, 0)
        assert add_datetime(dt, hours=3) == datetime(2026, 1, 1, 13, 0, 0)

    def test_add_minutes(self):
        dt = datetime(2026, 1, 1, 10, 0, 0)
        assert add_datetime(dt, minutes=90) == datetime(2026, 1, 1, 11, 30, 0)

    def test_add_seconds(self):
        dt = datetime(2026, 1, 1, 10, 0, 0)
        assert add_datetime(dt, seconds=3661) == datetime(2026, 1, 1, 11, 1, 1)

    def test_add_hours_crosses_day(self):
        dt = datetime(2026, 1, 31, 23, 0, 0)
        result = add_datetime(dt, hours=2)
        assert result == datetime(2026, 2, 1, 1, 0, 0)


class TestAddDatetimeCombined:
    def test_combined_all_params(self):
        dt = datetime(2026, 1, 1, 0, 0, 0)
        result = add_datetime(dt, years=1, months=2, days=3, hours=4, minutes=5, seconds=6)
        assert result == datetime(2027, 3, 4, 4, 5, 6)

    def test_timezone_aware_preserved(self):
        """timezone-aware datetime操作后时区信息保留"""
        tz = timezone(timedelta(hours=8))
        dt = datetime(2026, 6, 1, 12, 0, 0, tzinfo=tz)
        result = add_datetime(dt, days=1)
        assert result.tzinfo == tz

    def test_negative_combined(self):
        dt = datetime(2026, 6, 15, 12, 0, 0)
        result = add_datetime(dt, years=-1, months=-1, days=-1)
        assert result == datetime(2025, 5, 14, 12, 0, 0)
