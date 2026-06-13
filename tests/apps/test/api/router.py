"""
@Author     : zarkhan
@Date       : 2026/6/13
@Description:
"""

from .v1 import v1_router
from lumary import APIRouter

api_router = APIRouter(prefix='/api')
api_router.include_router(v1_router)


