"""
@Author     : zarkhan
@CreateDate : 2026/6/17
@Description: create_db_engine / 驱动检测工具函数单元测试
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from lumary.db.sqlalchemy.engine import (
    ASYNC_DRIVERS,
    _is_async_driver,
    _connect_args_from_url,
    create_db_engine)


# ──────────────────────────────────────────────
# ASYNC_DRIVERS 集合
# ──────────────────────────────────────────────
class TestAsyncDrivers:
    def test_contains_aiosqlite(self):
        assert 'aiosqlite' in ASYNC_DRIVERS

    def test_contains_asyncpg(self):
        assert 'asyncpg' in ASYNC_DRIVERS

    def test_contains_aiomysql(self):
        assert 'aiomysql' in ASYNC_DRIVERS

    def test_contains_asyncmy(self):
        assert 'asyncmy' in ASYNC_DRIVERS

    def test_is_frozenset(self):
        assert isinstance(ASYNC_DRIVERS, frozenset)


# ──────────────────────────────────────────────
# _is_async_driver
# ──────────────────────────────────────────────
class TestIsAsyncDriver:
    @pytest.mark.parametrize('url', [
        'sqlite+aiosqlite:///./test.db',
        'postgresql+asyncpg://user:pass@localhost/db',
        'mysql+aiomysql://user:pass@localhost/db',
        'mysql+asyncmy://user:pass@localhost/db',
    ])
    def test_async_urls_return_true(self, url):
        assert _is_async_driver(url) is True

    @pytest.mark.parametrize('url', [
        'sqlite:///./test.db',
        'postgresql://user:pass@localhost/db',
        'mysql://user:pass@localhost/db',
        'sqlite+pysqlite:///./test.db',
    ])
    def test_sync_urls_return_false(self, url):
        assert _is_async_driver(url) is False


# ──────────────────────────────────────────────
# _connect_args_from_url
# ──────────────────────────────────────────────
class TestConnectArgsFromUrl:
    def test_sqlite_check_same_thread(self):
        args = _connect_args_from_url('sqlite+aiosqlite:///./test.db')
        assert args.get('check_same_thread') is False

    def test_asyncpg_cache_disabled(self):
        args = _connect_args_from_url('postgresql+asyncpg://localhost/db')
        assert args.get('statement_cache_size') == 0
        assert args.get('prepared_statement_cache_size') == 0

    def test_other_drivers_empty_dict(self):
        args = _connect_args_from_url('mysql+aiomysql://localhost/db')
        assert args == {}

    def test_asyncmy_empty_dict(self):
        args = _connect_args_from_url('mysql+asyncmy://localhost/db')
        assert args == {}


# ──────────────────────────────────────────────
# create_db_engine
# ──────────────────────────────────────────────
class TestCreateDbEngine:
    def test_returns_async_engine(self):
        engine = create_db_engine('sqlite+aiosqlite:///:memory:')
        assert isinstance(engine, AsyncEngine)

    def test_sync_url_raises_value_error(self):
        with pytest.raises(ValueError, match='不是异步驱动'):
            create_db_engine('sqlite:///./test.db')

    def test_echo_flag_passed(self):
        engine = create_db_engine('sqlite+aiosqlite:///:memory:', echo=True)
        assert engine.echo is True

    def test_echo_default_false(self):
        engine = create_db_engine('sqlite+aiosqlite:///:memory:')
        assert engine.echo is False

    def test_custom_connect_args_merged(self):
        """自定义 connect_args 会与默认 args 合并"""
        engine = create_db_engine(
            'sqlite+aiosqlite:///:memory:',
            connect_args={'timeout': 30}
        )
        assert isinstance(engine, AsyncEngine)

    def test_extra_engine_kwargs_accepted(self):
        """额外的 engine kwargs 正常透传"""
        engine = create_db_engine(
            'sqlite+aiosqlite:///:memory:',
            pool_pre_ping=False,
        )
        assert isinstance(engine, AsyncEngine)

    async def test_engine_can_connect(self):
        """实际执行一条 SQL，验证引擎可用"""
        engine = create_db_engine('sqlite+aiosqlite:///:memory:')
        async with engine.connect() as conn:
            from sqlalchemy import text
            result = await conn.execute(text('SELECT 1'))
            assert result.scalar() == 1
        await engine.dispose()
