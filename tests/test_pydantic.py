"""
@Author     : zarkhan
@Date       : 2026/6/13
@Description:
"""
from logging import getLogger

import uvicorn
from fastapi import FastAPI, Request, Query, Depends, Form, HTTPException, Body
from pydantic import BaseModel
from starlette import status
from starlette.responses import HTMLResponse, JSONResponse

from lumary import Lumary

logger = getLogger(__name__)

app = Lumary(debug=True)

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


@app.post("/user")
def create_user(body: str= Body()):
    raise ValueError("Unauthorized") from None

if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=8000, log_config=None)
