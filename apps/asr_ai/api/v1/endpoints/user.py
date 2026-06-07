"""
@Author     : zarkhan
@CreateDate : 2026/5/15
@Description: 
"""
from logging import getLogger

from fastapi import APIRouter

from lumary import APIResponse, response_success

router = APIRouter(prefix='/user', tags=['User'])

logger = getLogger(__name__)

@router.get('')
async def get_user() -> APIResponse[dict]:
    logger.debug(f'GET /user')
    return response_success({'username': 'admin', 'password': '123'})
