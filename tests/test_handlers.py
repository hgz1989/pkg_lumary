"""
@Author     : zarkhan
@CreateDate : 2026/6/17
@Description: 全局异常处理器集成测试（通过TestClient发起真实HTTP请求验证响应格式）
"""
import pytest
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import BaseModel

from lumary import Lumary
from lumary.exceptions import (
    BadRequestError,
    UnauthorizedError,
    ForbiddenError,
    NotFoundError)


# ──────────────────────────────────────────────
# 测试应用
# ──────────────────────────────────────────────
@pytest.fixture(scope='module')
def client():
    app = Lumary(debug=False)

    class _Body(BaseModel):
        name: str
        value: int

    @app.get('/ok')
    async def _ok():
        return {'ok': True}

    @app.post('/validate')
    async def _validate(body: _Body):
        return body

    @app.get('/http-400')
    async def _http400():
        raise BadRequestError('自定义400')

    @app.get('/http-401')
    async def _http401():
        raise UnauthorizedError()

    @app.get('/http-403')
    async def _http403():
        raise ForbiddenError()

    @app.get('/http-404')
    async def _http404():
        raise NotFoundError('not found detail')

    @app.get('/runtime-error')
    async def _runtime():
        raise RuntimeError('unexpected crash')

    @app.get('/value-error')
    async def _value():
        raise ValueError('value error message')

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ──────────────────────────────────────────────
# 字段校验失败 → 422
# ──────────────────────────────────────────────
class TestValidationExceptionHandler:
    def test_missing_field_returns_422(self, client):
        resp = client.post('/validate', json={'name': 'x'})  # 缺少value
        assert resp.status_code == 422

    def test_422_body_format(self, client):
        body = client.post('/validate', json={'name': 'x'}).json()
        assert body['code'] == 422
        assert '参数校验失败' in body['message']

    def test_wrong_type_returns_422(self, client):
        resp = client.post('/validate', json={'name': 'x', 'value': 'not_int'})
        assert resp.status_code == 422

    def test_invalid_json_returns_400(self, client):
        """Content-Type: application/json但body无效 → 400"""
        resp = client.post(
            '/validate',
            content=b'{invalid json}',
            headers={'content-type': 'application/json'},
        )
        assert resp.status_code == 400
        assert resp.json()['code'] == 400


# ──────────────────────────────────────────────
# HTTP协议异常 → 对应状态码
# ──────────────────────────────────────────────
class TestHttpExceptionHandler:
    def test_400_status_code(self, client):
        assert client.get('/http-400').status_code == 400

    def test_400_body(self, client):
        body = client.get('/http-400').json()
        assert body['code'] == 400
        assert body['message'] == '自定义400'

    def test_401_status_code(self, client):
        assert client.get('/http-401').status_code == 401

    def test_401_default_message(self, client):
        assert client.get('/http-401').json()['message'] == 'Unauthorized'

    def test_403_status_code(self, client):
        assert client.get('/http-403').status_code == 403

    def test_404_status_code(self, client):
        assert client.get('/http-404').status_code == 404

    def test_404_body_detail(self, client):
        body = client.get('/http-404').json()
        assert 'not found detail' in body['message']

    def test_framework_404(self, client):
        """框架自动抛出的404也应返回标准格式"""
        body = client.get('/totally_nonexistent').json()
        assert 'code' in body
        assert 'message' in body


# ──────────────────────────────────────────────
# 未知异常兜底 → 500
# ──────────────────────────────────────────────
class TestGenericExceptionHandler:
    def test_runtime_error_returns_500(self, client):
        resp = client.get('/runtime-error')
        assert resp.status_code == 500

    def test_500_body_format(self, client):
        body = client.get('/runtime-error').json()
        assert body['code'] == 500
        assert '系统内部错误' in body['message']

    def test_value_error_returns_500(self, client):
        assert client.get('/value-error').status_code == 500

    def test_error_response_has_request_id(self, client):
        body = client.get('/runtime-error').json()
        assert 'request_id' in body
