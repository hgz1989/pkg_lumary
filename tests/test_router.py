"""
@Author     : zarkhan
@CreateDate : 2026/6/17
@Description: LumaryRoute自动响应包装单元测试
"""
import pytest
from fastapi import FastAPI, APIRouter
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from pydantic import BaseModel

from lumary.routing import WrapAPIRoute
from lumary.common.context import set_request_id


class UserOut(BaseModel):
    name: str
    age: int


class UserExtra(BaseModel):
    role: str


@pytest.fixture
def client():
    app = FastAPI()
    # 使用自定义路由类
    router = APIRouter(route_class=WrapAPIRoute)

    @router.get("/normal-data", response_model=UserOut)
    def normal_data():
        return UserOut(name="张三", age=25)

    @router.get("/tuple-data", response_model=tuple[UserOut, UserExtra])
    def tuple_data():
        return UserOut(name="李四", age=30), UserExtra(role="admin")

    @router.get("/dict-pass")
    def dict_pass():
        return {"code": 0, "message": "自定义成功", "data": {"foo": "bar"}}

    @router.get("/response-pass")
    def response_pass():
        return JSONResponse(content={"raw": "data"}, status_code=201)

    app.include_router(router)
    return TestClient(app)


@pytest.fixture(autouse=True)
def setup_request_id():
    set_request_id("test-router-id-123")


def test_normal_data_wrap(client: TestClient):
    response = client.get("/normal-data")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["message"] == "操作成功"
    assert data["data"] == {"name": "张三", "age": 25}
    assert data["request_id"] == "test-router-id-123"
    assert data["extra"] is None


def test_tuple_data_wrap(client: TestClient):
    response = client.get("/tuple-data")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["message"] == "操作成功"
    assert data["data"] == {"name": "李四", "age": 30}
    assert data["extra"] == {"role": "admin"}
    assert data["request_id"] == "test-router-id-123"


def test_dict_passthrough(client: TestClient):
    response = client.get("/dict-pass")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["message"] == "自定义成功"
    assert data["data"] == {"foo": "bar"}
    # 虽然是透传字典，但如果没带request_id，我们在schemas的APIResponse解析时会自动补全
    assert "request_id" in data


def test_response_passthrough(client: TestClient):
    response = client.get("/response-pass")
    assert response.status_code == 201
    assert response.json() == {"raw": "data"}

