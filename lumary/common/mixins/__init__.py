"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: Lumary 模块
"""
from importlib.util import find_spec

__all__ = []

if find_spec('sqlalchemy') is not None:
    from .sqlalchemy import SoftDeleteMixin, AuditMixin

    __all__.append('SoftDeleteMixin')
    __all__.append('AuditMixin')
