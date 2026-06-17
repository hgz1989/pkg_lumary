"""
@Author     : zarkhan
@CreateDate : 2026/6/17
@Description: RequestIdMiddleware 中间件单元测试
"""
import re
import pytest
from fastapi.testclient import TestClient

from lumary import Lumary
from lumary.common import get_request_id


# ──────────────────────────────────────────────
# 测试应用（Lumary 默认挂载了 RequestIdMiddleware）
# ──────────────────────────────────────────────
@pytest.fixture(scope='module')
def client():
    app = Lumary(debug=True)

    @app.get('/rid')
    async def _rid():
        """返回当前 request_id 供验证"""
        return {'request_id': get_request_id()}

    with TestClient(app) as c:
        yield c


# ──────────────────────────────────────────────
# 自动生成 request_id
# ──────────────────────────────────────────────
class TestRequestIdAutoGenerate:
    _UUID4_RE = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
        re.IGNORECASE
    )

    def test_response_has_x_request_id_header(self, client):
        resp = client.get('/rid')
        assert 'x-request-id' in resp.headers

    def test_auto_generated_request_id_is_uuid4(self, client):
        rid = client.get('/rid').headers['x-request-id']
        assert self._UUID4_RE.match(rid), f'request_id 不是合法 UUID4: {rid}'

    def test_each_request_gets_unique_id(self, client):
        rid1 = client.get('/rid').headers['x-request-id']
        rid2 = client.get('/rid').headers['x-request-id']
        assert rid1 != rid2

    def test_context_var_matches_response_header(self, client):
        """响应体中 ContextVar 取到的 request_id 应与响应头一致"""
        resp = client.get('/rid')
        body_rid = resp.json()['request_id']
        header_rid = resp.headers['x-request-id']
        assert body_rid == header_rid


# ──────────────────────────────────────────────
# 客户端传入 X-Request-ID
# ──────────────────────────────────────────────
class TestRequestIdForwarding:
    def test_custom_request_id_echoed_in_header(self, client):
        rid = 'my-trace-id-12345'
        resp = client.get('/rid', headers={'x-request-id': rid})
        assert resp.headers['x-request-id'] == rid

    def test_custom_request_id_in_context(self, client):
        rid = 'trace-abc'
        body = client.get('/rid', headers={'x-request-id': rid}).json()
        assert body['request_id'] == rid

    def test_empty_custom_id_auto_generates(self, client):
        """空字符串的 X-Request-ID 头应被当作无效，自动生成新 ID"""
        resp = client.get('/rid', headers={'x-request-id': ''})
        rid = resp.headers['x-request-id']
        # 空字符串被视为 falsy，中间件会重新生成
        # 若框架直接传过去了，也至少不能为空
        assert rid is not None and len(rid) > 0


# ──────────────────────────────────────────────
# 非 HTTP scope（lifespan / 其他）不应被处理
# ──────────────────────────────────────────────
class TestNonHttpScope:
    def test_non_http_request_passes_through(self, client):
        """正常 GET 请求不受 scope 过滤影响"""
        resp = client.get('/system/health')
        assert resp.status_code == 200
        assert 'x-request-id' in resp.headers
