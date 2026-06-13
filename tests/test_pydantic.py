"""
@Author     : zarkhan
@Date       : 2026/6/13
@Description:
"""
from typing import Annotated
import uvicorn
from fastapi import FastAPI, Request, Query, Depends, Form, HTTPException
from pydantic import BaseModel
from starlette.responses import HTMLResponse, JSONResponse

from lumary import response_fail

app = FastAPI()


@app.exception_handler(400)
@app.exception_handler(401)
@app.exception_handler(403)
@app.exception_handler(404)
@app.exception_handler(405)
@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    """处理 FastAPI 内置的 HTTP 异常

    捕获框架自动抛出或通过 `raise HTTPException` 抛出的错误（如 401 鉴权失败、404 路由不存在）
    将其重新封装为符合项目规范的 JSON 结构

    Args:
        _request: 当前请求对象（未使用）
        exc: FastAPI 抛出的 HTTP 异常实例

    Returns:
        继承原状态码及统一错误格式的 JSON 响应
    """
    # 调试模式截取异常信息，避免内容过长
    err_detail = str(exc.detail)[:300] if app.debug else None
    resp = response_fail(
        code=exc.status_code * 100,
        message=str(exc.detail),
        data=err_detail
    )
    return JSONResponse(resp.model_dump(), status_code=exc.status_code)


class UserBody(BaseModel):
    username: str
    age: int


# POST 接口，接收 JSON Body

# 接收普通 form-data 表单
@app.post("/form")
def receive_form(
        username: str = Form(),
        age: int = Form()
):
    return {
        "username": username,
        "age": age
    }


if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=8000, log_config=None)
