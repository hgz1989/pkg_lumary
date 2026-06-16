"""
@Author     : zarkhan
@Date       : 2026/6/16
@Description:
"""
from lumary import Lumary, APIResponse

app = Lumary(debug=True)

@app.get('/aaaa')
async def index()->APIResponse[str]:
    """首页

    Returns:

    """
    print('aaaa')
    raise ValueError('只要开心')


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host='127.0.0.1', port=8000)