"""
@Author     : zarkhan
@Date       : 2026/5/18
@Description:
"""
from threading import Lock


class Singleton:
    """线程安全单例基类

    所有需要单例的类，直接继承即可
    """
    _cls_ins = None
    _cls_lock = Lock()

    def __new__(cls, *args, **kwargs):
        """创建单例模式实例

        Args:
            *args: 创建实例的参数
            **kwargs: 创建实例的关键字参数
        """
        if cls._cls_ins is None:
            with cls._cls_lock:
                if cls._cls_ins is None:
                    cls._cls_ins = super().__new__(cls)
        return cls._cls_ins
