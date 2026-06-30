"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: Lumary模块
"""
from importlib.util import find_spec

__all__ = []

if find_spec('sqlalchemy') is not None:
    from .sa import SoftDeleteMixin

    __all__.append('SoftDeleteMixin')
