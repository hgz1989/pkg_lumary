"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 
"""
from enum import Enum
from typing import Any


class BaseEnum(Enum):
    """枚举基类"""

    @property
    def val(self) -> Any:
        """获取枚举值

        Returns:
            枚举值
        """
        if isinstance(self.value, (list, tuple)):
            return self.value[0]
        return self.value

    @property
    def label(self) -> str:
        """获取枚举标签

        Returns:
            枚举描述标签
        """
        if isinstance(self.value, (list, tuple)) and len(self.value) >= 2:
            return self.value[1]
        return self.name