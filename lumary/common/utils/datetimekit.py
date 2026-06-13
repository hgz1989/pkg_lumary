"""
@Author     : zarkhan
@CreateDate : 2026/6/12
@Description: 日期时间处理工具
"""
import calendar
from datetime import datetime, timedelta

def add_datetime(
    dt: datetime,
    years: int = 0,
    months: int = 0,
    days: int = 0,
    hours: int = 0,
    minutes: int = 0,
    seconds: int = 0,
) -> datetime:
    """给 datetime 对象添加指定的年月日时分秒，正确处理闰年、月份天数差异

    Args:
        dt: 原始 datetime（可以是 naive 或 aware）
        years: 增加的年数（负数表示减少）
        months: 增加的月数
        days: 增加的天数
        hours: 增加的小时数
        minutes: 增加的分钟数
        seconds: 增加的秒数

    Returns:
        新的 datetime 对象，时区属性与原对象相同
    """
    dt = dt + timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)

    year = dt.year + years
    month = dt.month + months

    while month > 12:
        month -= 12
        year += 1
    while month < 1:
        month += 12
        year -= 1

    _, last_day = calendar.monthrange(year, month)
    day = min(dt.day, last_day)

    return dt.replace(year=year, month=month, day=day)
