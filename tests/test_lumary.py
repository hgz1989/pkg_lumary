"""
@Author     : zarkhan
@Date       : 2026/6/16
@Description:
"""
from fastapi import Form

from lumary import Lumary, SchemaBase, APIResponse, response_success, APIResponseWithExtra, response_with_extra_success
from lumary.common import setup_logger

app = Lumary(debug=True)
setup_logger(
    './logs'
)

class User(SchemaBase):
    name: str
    age: int


class Tenant(SchemaBase):
    name: str
    age: int


@app.get('/user')
async def index() -> APIResponse[User]:
    """首页

    Returns:

    """
    resp = User(name='lumary', age=18)
    return response_success(data=resp)


@app.post('/tenant')
async def tenant(user: User) -> APIResponseWithExtra[User, Tenant]:
    """租户

    Returns:

    """
    resp = user
    extra = Tenant(name='lumary', age=18)
    return response_with_extra_success(data=resp, extra=extra)


@app.post('/tenant2')
async def tenant2(user: User = Form()) -> APIResponseWithExtra[User, Tenant]:
    """租户2

    Returns:

    """
    resp = user
    extra = Tenant(name='lumary', age=18)
    return response_with_extra_success(data=resp, extra=extra)


@app.post('/error')
async def error():
    raise ValueError('test error')


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host='127.0.0.1', port=8000, log_config=None)
