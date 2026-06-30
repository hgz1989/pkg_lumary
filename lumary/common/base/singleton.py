"""
@Author     : zarkhan
@CreateDate : 2026/5/18
@Description: 单例与跨进程共享状态基类
"""
import json
import os
import tempfile
from pathlib import Path
from threading import Lock
from typing import Any

from lumary.common.utils.locks import CrossProcessLock


class ProcessLocalSingleton:
    """进程内线程安全单例基类

    所有需要单例的类，直接继承即可
    注意：在 Uvicorn 多 Worker 模式下，每个 Worker 进程会独立维护自己的实例，互不干扰！
    """
    _instances: dict[type, Any] = {}
    _lock: Lock = Lock()

    def __new__(cls, *args: Any, **kwargs: Any) -> 'ProcessLocalSingleton':
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


# 兼容老版本名称
Singleton = ProcessLocalSingleton


class CrossProcessSharedDict:
    """跨进程共享字典

    基于本地文件与跨进程锁实现的多进程共享状态字典。
    适用于需要在多个 Uvicorn Worker 之间共享简单配置、计数器或状态的场景。
    
    注意: 
    1. 性能不如纯内存字典，适用于读写频率不高的状态共享。
    2. 存储的数据必须能够被 JSON 序列化。
    """

    def __init__(self, name: str):
        self.name = name
        self.file_path = Path(tempfile.gettempdir()) / f"lumary_shared_{name}.json"
        self._lock = CrossProcessLock(f"shared_dict_{name}")
        
        # 初始化文件
        if not self.file_path.exists():
            if self._lock.acquire(blocking=True):
                try:
                    if not self.file_path.exists():
                        with open(self.file_path, 'w', encoding='utf-8') as f:
                            json.dump({}, f)
                finally:
                    self._lock.release()

    def _read(self) -> dict[str, Any]:
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _write(self, data: dict[str, Any]) -> None:
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)

    def get(self, key: str, default: Any = None) -> Any:
        if self._lock.acquire(blocking=True):
            try:
                data = self._read()
                return data.get(key, default)
            finally:
                self._lock.release()
        return default

    def set(self, key: str, value: Any) -> None:
        if self._lock.acquire(blocking=True):
            try:
                data = self._read()
                data[key] = value
                self._write(data)
            finally:
                self._lock.release()

    def delete(self, key: str) -> None:
        if self._lock.acquire(blocking=True):
            try:
                data = self._read()
                if key in data:
                    del data[key]
                    self._write(data)
            finally:
                self._lock.release()

    def get_all(self) -> dict[str, Any]:
        if self._lock.acquire(blocking=True):
            try:
                return self._read()
            finally:
                self._lock.release()
        return {}

    def clear(self) -> None:
        if self._lock.acquire(blocking=True):
            try:
                self._write({})
            finally:
                self._lock.release()
