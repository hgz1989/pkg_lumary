"""
@Author     : zarkhan
@CreateDate : 2026/5/18
@Description: 线程安全单例基类
"""
from threading import Lock
from typing import Any


class Singleton:
    """线程安全单例基类

    所有需要单例的类，直接继承即可
    每个子类独立维护自己的实例，互不干扰
    """
    _instances: dict[type, Any] = {}
    _lock: Lock = Lock()

    def __new__(cls, *args: Any, **kwargs: Any) -> 'Singleton':
        """创建单例模式实例

        使用双重检查锁实现线程安全单例
        每个子类的实例分开存储，不会相互覆盖

        Args:
            *args: 创建实例的参数
            **kwargs: 创建实例的关键字参数

        Returns:
            当前类的单例实例
        """
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    cls._instances[cls] = super().__new__(cls)
        return cls._instances[cls]
