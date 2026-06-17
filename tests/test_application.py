"""
@Author     : zarkhan
@CreateDate : 2026/6/17
@Description: Lumary 应用核心行为、系统内置接口单元测试
"""
import pytest
from fastapi.testclient import TestClient

from lumary import Lumary
from lumary.lifespan import HookRegistry


# ──────────────────────────────────────────────
# 测试用应用实例（debug=True 以暴露文档路由）
# ──────────────────────────────────────────────
@pytest.fixture(scope='module')
def app():
    return Lumary(debug=True, title='TestApp', version='0.0.1')


@pytest.fixture(scope='module')
def client(app):
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ──────────────────────────────────────────────
# 应用初始化行为
# ──────────────────────────────────────────────
class TestLumaryInit:
    def test_title(self, app):
        assert app.title == 'TestApp'

    def test_version(self, app):
        assert app.version == '0.0.1'

    def test_debug_true(self, app):
        assert app.debug is True

    def test_is_sub_app_default_false(self, app):
        assert app.is_sub_app is False

    def test_start_time_set(self, app):
        assert app._start_time > 0

    def test_non_debug_hides_docs(self):
        """非 debug 模式下文档路由应被禁用"""
        prod_app = Lumary(debug=False)
        assert prod_app.openapi_url is None
        assert prod_app.docs_url is None

    def test_custom_hook_registry(self):
        """可注入独立 HookRegistry"""
        registry = HookRegistry()
        custom_app = Lumary(debug=True, hook_registry=registry)
        assert custom_app._hook_registry is registry

    def test_sub_app_flag(self):
        """is_sub_app=True 时不注册 /system 路由"""
        sub = Lumary(debug=True, is_sub_app=True)
        paths = [r.path for r in sub.routes if hasattr(r, 'path')]
        assert not any(p.startswith('/system') for p in paths)


# ──────────────────────────────────────────────
# 系统内置接口
# ──────────────────────────────────────────────
class TestSystemEndpoints:
    def test_health_200(self, client):
        resp = client.get('/system/health')
        assert resp.status_code == 200

    def test_health_body(self, client):
        body = client.get('/system/health').json()
        assert body['code'] == 0
        assert body['data']['status'] == 'OK'
        assert body['data']['name'] == 'TestApp'
        assert body['data']['version'] == '0.0.1'
        assert body['data']['debug'] is True

    def test_health_has_request_id(self, client):
        headers = client.get('/system/health').headers
        assert 'x-request-id' in headers

    def test_info_200(self, client):
        resp = client.get('/system/info')
        assert resp.status_code == 200

    def test_info_body(self, client):
        body = client.get('/system/info').json()
        assert body['code'] == 0
        data = body['data']
        assert data['name'] == 'TestApp'
        assert 'routes_count' in data
        assert 'sub_apps_count' in data
        assert 'python_version' in data

    def test_metrics_200(self, client):
        resp = client.get('/system/metrics')
        assert resp.status_code == 200

    def test_metrics_body(self, client):
        body = client.get('/system/metrics').json()
        assert body['code'] == 0
        data = body['data']
        assert 'uptime_seconds' in data
        assert data['uptime_seconds'] >= 0
        assert 'memory_mb' in data

    def test_request_id_header_forwarded(self, client):
        """客户端传入 X-Request-ID 时应原样返回"""
        custom_rid = 'my-custom-request-id'
        headers = client.get('/system/health', headers={'x-request-id': custom_rid}).headers
        assert headers.get('x-request-id') == custom_rid

    def test_404_returns_json(self, client):
        """不存在的路由应返回标准 JSON 格式而非 HTML"""
        resp = client.get('/not_exist')
        assert resp.status_code == 404
        body = resp.json()
        assert 'code' in body
        assert 'message' in body
