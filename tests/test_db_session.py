"""
@Author     : zarkhan
@CreateDate : 2026/6/17
@Description: SessionFactory 会话管理单元测试（使用 in-memory SQLite）
"""
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lumary.db.sqlalchemy.engine import create_db_engine
from lumary.db.sqlalchemy.session import SessionFactory


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────
@pytest.fixture
async def factory():
    engine = create_db_engine('sqlite+aiosqlite:///:memory:')
    sf = SessionFactory(engine)
    yield sf
    await engine.dispose()


# ──────────────────────────────────────────────
# 初始化
# ──────────────────────────────────────────────
class TestSessionFactoryInit:
    def test_engine_stored(self, factory):
        from sqlalchemy.ext.asyncio import AsyncEngine
        assert isinstance(factory.engine, AsyncEngine)

    def test_session_factory_created(self, factory):
        assert factory.session_factory is not None


# ──────────────────────────────────────────────
# get_session 上下文管理器
# ──────────────────────────────────────────────
class TestGetSession:
    async def test_yields_async_session(self, factory):
        async with factory.get_session() as session:
            assert isinstance(session, AsyncSession)

    async def test_session_executes_sql(self, factory):
        """能执行 SQL 语句"""
        async with factory.get_session() as session:
            result = await session.execute(text('SELECT 1'))
            assert result.scalar() == 1

    async def test_session_rollback_on_exception(self, factory):
        """发生异常时自动回滚，异常向外传播"""
        with pytest.raises(RuntimeError, match='test_rollback'):
            async with factory.get_session() as session:
                await session.execute(text('SELECT 1'))
                raise RuntimeError('test_rollback')

    async def test_multiple_sessions_independent(self, factory):
        """多次调用 get_session 产生独立的会话"""
        async with factory.get_session() as s1:
            async with factory.get_session() as s2:
                assert s1 is not s2


# ──────────────────────────────────────────────
# get_service 依赖工厂
# ──────────────────────────────────────────────
class TestGetService:
    def test_returns_callable(self, factory):
        class _FakeService:
            def __init__(self, db: AsyncSession):
                self.db = db

        dep = factory.get_service(_FakeService)
        assert callable(dep)

    def test_dependency_name(self, factory):
        class MyService:
            def __init__(self, db: AsyncSession):
                self.db = db

        dep = factory.get_service(MyService)
        assert dep.__name__ == 'MyServiceService'

    def test_dependency_doc(self, factory):
        class MyService:
            def __init__(self, db: AsyncSession):
                self.db = db

        dep = factory.get_service(MyService)
        assert 'MyService' in (dep.__doc__ or '')

    async def test_service_receives_session(self, factory):
        """依赖注入的服务实例中应含有 AsyncSession"""
        class _Svc:
            def __init__(self, db: AsyncSession):
                self.db = db

        dep = factory.get_service(_Svc)
        async for svc in dep():
            assert isinstance(svc.db, AsyncSession)
            break

# ──────────────────────────────────────────────
# service 装饰器 (FastAPI 依赖注入)
# ──────────────────────────────────────────────
class TestServiceDecorator:
    def test_decorator_returns_class(self, factory):
        @factory.service()
        class MyService:
            def __init__(self, db: AsyncSession):
                self.db = db

        assert isinstance(MyService, type)
        assert MyService.__name__ == 'MyService'

    def test_signature_rewritten_with_depends(self, factory):
        """测试服务类的 __init__ 签名中 db 参数被替换为 Depends"""
        import inspect
        from fastapi.params import Depends

        @factory.service()
        class MyService:
            def __init__(self, db: AsyncSession):
                self.db = db

        sig = inspect.signature(MyService)
        db_param = sig.parameters.get('db')
        
        assert db_param is not None
        assert isinstance(db_param.default, Depends)

    def test_signature_rewritten_by_type_annotation(self, factory):
        """测试通过类型提示 AsyncSession 自动识别并注入"""
        import inspect
        from fastapi.params import Depends

        @factory.service()
        class AnotherService:
            # 参数名不是 db，但类型是 AsyncSession
            def __init__(self, custom_session: AsyncSession):
                self.custom_session = custom_session

        sig = inspect.signature(AnotherService)
        session_param = sig.parameters.get('custom_session')
        
        assert session_param is not None
        assert isinstance(session_param.default, Depends)

    def test_fastapi_integration(self, factory):
        """模拟在 FastAPI 中使用的完整流程"""
        from fastapi import FastAPI, Depends
        from fastapi.testclient import TestClient

        @factory.service()
        class EndpointService:
            def __init__(self, db: AsyncSession):
                self.db = db
                
            async def get_data(self):
                # 简单验证 db 能够执行 SQL
                res = await self.db.execute(text("SELECT 'success'"))
                return res.scalar()

        app = FastAPI()

        @app.get("/test-service")
        async def test_endpoint(service: EndpointService = Depends()):
            data = await service.get_data()
            return {"result": data}

        client = TestClient(app)
        response = client.get("/test-service")
        
        assert response.status_code == 200
        assert response.json() == {"result": "success"}
