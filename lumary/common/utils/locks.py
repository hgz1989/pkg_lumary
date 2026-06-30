"""
@Author     : zarkhan
@CreateDate : 2026/6/27
@Description: 跨进程锁工具
"""
import os
import tempfile
from sys import platform

class CrossProcessLock:
    """跨进程文件锁，用于在多进程环境下（如 Uvicorn/Gunicorn workers）
    确保某些初始化操作（如 MQTT 订阅、定时任务启动）只执行一次。
    """
    
    __slots__ = ('name', 'lock_file', 'fd')
    
    def __init__(self, name: str = 'lumary_global'):
        self.name = name
        self.lock_file = os.path.join(tempfile.gettempdir(), f'{name}.lock')
        self.fd: int | None = None
        
    def acquire(self, blocking: bool = False) -> bool:
        """尝试获取锁
        
        Args:
            blocking: 是否阻塞等待
            
        Returns:
            是否成功获取到锁
        """
        try:
            if platform == 'win32':
                import msvcrt
                # Windows 下使用 msvcrt.locking
                self.fd = os.open(self.lock_file, os.O_CREAT | os.O_RDWR)
                mode = msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK
                try:
                    msvcrt.locking(self.fd, mode, 1)
                    return True
                except OSError:
                    os.close(self.fd)
                    self.fd = None
                    return False
            else:
                import fcntl
                # Linux/macOS 下使用 fcntl.flock
                self.fd = os.open(self.lock_file, os.O_CREAT | os.O_RDWR)
                mode = fcntl.LOCK_EX if blocking else (fcntl.LOCK_EX | fcntl.LOCK_NB)
                try:
                    fcntl.flock(self.fd, mode)
                    return True
                except OSError:
                    os.close(self.fd)
                    self.fd = None
                    return False
        except Exception:
            return False
            
    def release(self) -> None:
        """释放锁"""
        if self.fd is not None:
            try:
                if platform == 'win32':
                    import msvcrt
                    os.lseek(self.fd, 0, os.SEEK_SET)
                    msvcrt.locking(self.fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.fd, fcntl.LOCK_UN)
            except OSError:
                pass
            finally:
                os.close(self.fd)
                self.fd = None
                
    def __enter__(self):
        self.acquire(blocking=True)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
