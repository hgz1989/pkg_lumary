"""
@Author     : zarkhan
@CreateDate : 2026/5/15
@Description: 
"""
from fastapi import APIRouter

from .endpoints import user_router

router = APIRouter(prefix='/v1')
router.include_router(user_router)
