"""
@Author     : zarkhan
@Date       : 2026/6/16
@Description:
"""
from lumary import Lumary, SchemaBase, APIResponse, response_success, APIResponseWithExtra

app = Lumary(debug=True)


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


@app.get('/tenant')
async def tenant() -> APIResponseWithExtra[User, Tenant]:
    """租户

    Returns:

    """
    resp = User(name='lumary', age=18)
    extra = Tenant(name='lumary', age=18)
    return response_success(data=resp, extra=extra)


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host='127.0.0.1', port=8000, log_config=None)
