"""
@Author     : zarkhan
@CreateDate : 2026/5/18
@Description: 单例与跨进程共享状态基类
"""
import threading
from typing import Any


class ProcessLocalSingleton:
    """进程内单例基类

    提供基于双重检查锁定 (Double-Checked Locking) 的线程安全单例实现。
    
    警告：
    在 Uvicorn 多 Worker 模式下，不同进程的内存是物理隔离的。
    继承此类的对象仅在**当前进程内**是唯一的。如果你需要跨进程共享全局状态，
    请使用 Redis 或数据库。
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
        """重写实例化逻辑实现单例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
