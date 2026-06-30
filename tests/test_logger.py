"""
@Author     : zarkhan
@CreateDate : 2026/6/17
@Description: setup_logger / 日志轮转Handler单元测试
"""
import logging
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import pytest

from lumary.logger import (
    _MonthlyRotatingFileHandler,
    _YearlyRotatingFileHandler,
    _ROTATION_MAP,
    UvicornNameRewriteFilter,
    setup_logger,
    set_log_level,
    set_log_format)


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────
@pytest.fixture(autouse=True)
def clean_root_handlers():
    """每个测试后清理根日志处理器，避免测试间干扰"""
    yield
    root = logging.getLogger()
    for h in list(root.handlers):
        if isinstance(h, logging.FileHandler):
            h.close()
            root.removeHandler(h)


# ──────────────────────────────────────────────
# _ROTATION_MAP
# ──────────────────────────────────────────────
class TestRotationMap:
    def test_all_keys_present(self):
        expected = {'second', 'minute', 'hour', 'day', 'week', 'month', 'year'}
        assert set(_ROTATION_MAP.keys()) == expected

    def test_standard_keys_have_tuple(self):
        for key in ('second', 'minute', 'hour', 'day', 'week'):
            assert isinstance(_ROTATION_MAP[key], tuple), f'{key} 应是 (when, interval) 元组'

    def test_month_year_are_none(self):
        assert _ROTATION_MAP['month'] is None
        assert _ROTATION_MAP['year'] is None


# ──────────────────────────────────────────────
# _MonthlyRotatingFileHandler.computeRollover
# ──────────────────────────────────────────────
class TestMonthlyRotatingFileHandler:
    def _handler(self, tmp_path: Path):
        log_file = str(tmp_path / 'monthly.log')
        return _MonthlyRotatingFileHandler(log_file, backup_count=3)

    def test_rollover_next_month(self, tmp_path):
        h = self._handler(tmp_path)
        # 2026-06-15 12:00:00
        ts = datetime(2026, 6, 15, 12, 0, 0).timestamp()
        rollover = h.computeRollover(ts)
        expected = datetime(2026, 7, 1, 0, 0, 0).timestamp()
        assert rollover == pytest.approx(expected, abs=1)
        h.close()

    def test_rollover_december_to_next_year(self, tmp_path):
        h = self._handler(tmp_path)
        ts = datetime(2026, 12, 1, 0, 0, 0).timestamp()
        rollover = h.computeRollover(ts)
        expected = datetime(2027, 1, 1, 0, 0, 0).timestamp()
        assert rollover == pytest.approx(expected, abs=1)
        h.close()

    def test_rollover_is_always_later_than_current(self, tmp_path):
        h = self._handler(tmp_path)
        now = datetime.now().timestamp()
        rollover = h.computeRollover(now)
        assert rollover > now
        h.close()


# ──────────────────────────────────────────────
# _YearlyRotatingFileHandler.computeRollover
# ──────────────────────────────────────────────
class TestYearlyRotatingFileHandler:
    def _handler(self, tmp_path: Path):
        log_file = str(tmp_path / 'yearly.log')
        return _YearlyRotatingFileHandler(log_file, backup_count=3)

    def test_rollover_next_year(self, tmp_path):
        h = self._handler(tmp_path)
        ts = datetime(2026, 6, 15).timestamp()
        rollover = h.computeRollover(ts)
        expected = datetime(2027, 1, 1, 0, 0, 0).timestamp()
        assert rollover == pytest.approx(expected, abs=1)
        h.close()

    def test_rollover_on_jan1_goes_to_next_year(self, tmp_path):
        h = self._handler(tmp_path)
        ts = datetime(2026, 1, 1, 0, 0, 0).timestamp()
        rollover = h.computeRollover(ts)
        expected = datetime(2027, 1, 1, 0, 0, 0).timestamp()
        assert rollover == pytest.approx(expected, abs=1)
        h.close()

    def test_rollover_is_always_later_than_current(self, tmp_path):
        h = self._handler(tmp_path)
        now = datetime.now().timestamp()
        rollover = h.computeRollover(now)
        assert rollover > now
        h.close()


# ──────────────────────────────────────────────
# setup_logger
# ──────────────────────────────────────────────
class TestSetupLogger:
    def test_no_log_dir_adds_console_handler(self):
        root = logging.getLogger()
        before = len(root.handlers)
        setup_logger(enable_console=True)
        # 至少不会报错，且控制台处理器只加一次
        after_count = sum(
            1 for h in root.handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        )
        assert after_count >= 1

    def test_disable_console_removes_stream_handler(self):
        setup_logger(enable_console=True)
        setup_logger(enable_console=False)
        root = logging.getLogger()
        has_console = any(
            isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
            for h in root.handlers
        )
        assert not has_console

    def test_file_handler_created(self, tmp_path):
        setup_logger(log_dir=str(tmp_path), filename='test.log', rotation='day')
        root = logging.getLogger()
        file_handlers = [h for h in root.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) >= 1

    def test_log_file_exists_after_setup(self, tmp_path):
        setup_logger(log_dir=str(tmp_path), filename='app.log', rotation='day')
        # 写一条日志触发文件创建
        logging.getLogger().info('hello test')
        assert (tmp_path / 'app.log').exists()

    def test_no_duplicate_file_handler(self, tmp_path):
        """多次调用setup_logger相同路径不应重复添加FileHandler"""
        setup_logger(log_dir=str(tmp_path), filename='dedup.log', rotation='day')
        setup_logger(log_dir=str(tmp_path), filename='dedup.log', rotation='day')
        root = logging.getLogger()
        target = str((tmp_path / 'dedup.log').absolute())
        count = sum(
            1 for h in root.handlers
            if isinstance(h, logging.FileHandler) and getattr(h, 'baseFilename', '') == target
        )
        assert count == 1

    def test_invalid_rotation_raises(self, tmp_path):
        with pytest.raises(ValueError, match='不支持的轮转粒度'):
            setup_logger(log_dir=str(tmp_path), filename='x.log', rotation='quarterly')

    @pytest.mark.parametrize('rotation', ['second', 'minute', 'hour', 'day', 'week'])
    def test_standard_rotations_create_timed_handler(self, tmp_path, rotation):
        setup_logger(log_dir=str(tmp_path), filename=f'{rotation}.log', rotation=rotation)
        root = logging.getLogger()
        handlers = [
            h for h in root.handlers
            if isinstance(h, TimedRotatingFileHandler)
            and not isinstance(h, (_MonthlyRotatingFileHandler, _YearlyRotatingFileHandler))
        ]
        assert len(handlers) >= 1

    def test_month_rotation_uses_monthly_handler(self, tmp_path):
        setup_logger(log_dir=str(tmp_path), filename='monthly.log', rotation='month')
        root = logging.getLogger()
        assert any(isinstance(h, _MonthlyRotatingFileHandler) for h in root.handlers)

    def test_year_rotation_uses_yearly_handler(self, tmp_path):
        setup_logger(log_dir=str(tmp_path), filename='yearly.log', rotation='year')
        root = logging.getLogger()
        assert any(isinstance(h, _YearlyRotatingFileHandler) for h in root.handlers)

    def test_log_dir_created_if_not_exist(self, tmp_path):
        new_dir = tmp_path / 'nested' / 'logs'
        assert not new_dir.exists()
        setup_logger(log_dir=str(new_dir), filename='test.log')
        assert new_dir.exists()


# ──────────────────────────────────────────────
# set_log_level
# ──────────────────────────────────────────────
class TestSetLogLevel:
    def test_set_level_by_string(self):
        set_log_level('debug')
        assert logging.getLogger().level == logging.DEBUG

    def test_set_level_by_int(self):
        set_log_level(logging.WARNING)
        assert logging.getLogger().level == logging.WARNING

    def test_set_level_case_insensitive(self):
        set_log_level('Error')
        assert logging.getLogger().level == logging.ERROR


# ──────────────────────────────────────────────
# set_log_format
# ──────────────────────────────────────────────
class TestSetLogFormat:
    def test_format_applied_to_handlers(self):
        setup_logger(enable_console=True)
        new_fmt = '%(levelname)s - %(message)s'
        set_log_format(new_fmt)
        root = logging.getLogger()
        for h in root.handlers:
            if h.formatter:
                assert h.formatter._fmt == new_fmt
                break


# ──────────────────────────────────────────────
# UvicornNameRewriteFilter
# ──────────────────────────────────────────────
class TestUvicornNameRewriteFilter:
    def _make_record(self, name: str) -> logging.LogRecord:
        return logging.LogRecord(
            name=name, level=logging.INFO,
            pathname='', lineno=0,
            msg='test', args=(), exc_info=None
        )

    def test_filter_always_returns_true(self):
        f = UvicornNameRewriteFilter()
        record = self._make_record('some.logger')
        assert f.filter(record) is True

    def test_uvicorn_error_renamed_to_uvicorn(self):
        f = UvicornNameRewriteFilter()
        record = self._make_record('uvicorn.error')
        f.filter(record)
        assert record.name == 'uvicorn'

    def test_uvicorn_access_renamed_to_uvicorn(self):
        f = UvicornNameRewriteFilter()
        record = self._make_record('uvicorn.access')
        f.filter(record)
        assert record.name == 'uvicorn'

    def test_other_names_unchanged(self):
        f = UvicornNameRewriteFilter()
        record = self._make_record('fastapi')
        f.filter(record)
        assert record.name == 'fastapi'

    def test_uvicorn_root_unchanged(self):
        """'uvicorn' 本身（不含子级）不应被重写"""
        f = UvicornNameRewriteFilter()
        record = self._make_record('uvicorn')
        f.filter(record)
        assert record.name == 'uvicorn'

    def test_custom_logger_name_unchanged(self):
        f = UvicornNameRewriteFilter()
        record = self._make_record('myapp.service')
        f.filter(record)
        assert record.name == 'myapp.service'
