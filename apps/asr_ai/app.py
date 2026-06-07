"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 
"""
from lumary import Lumary

# from .api.v1 import v1_router

app = Lumary(debug=True, title='ASR', is_sub_app=True)
# app.include_router(v1_router)

if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host='0.0.0.0', port=8000)
