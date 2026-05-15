"""
@Author     : zarkhan
@Date       : 2026/5/14
@Description:
"""
import logging

# ===============================
# 日志格式定义
# ===============================
NORMAL_FORMAT = (
    '%(asctime)s | %(levelname)-8s | %(name)-50.50s | %(lineno)4d | %(message)s'
)

# ===============================
# 配置日志格式
# ===============================
logging.basicConfig(
    level=logging.DEBUG,
    format=NORMAL_FORMAT,
    force=True
)

# ===============================
# 强制接管 uvicorn 的所有日志（核心！）
# ===============================
uvicorn_logger_names = [
    'uvicorn',
    'uvicorn.error',
    'uvicorn.access',
    'fastapi',
    'httpx'
]

for logger_name in uvicorn_logger_names:
    logger = logging.getLogger(logger_name)
    logger.handlers.clear()  # 清空默认处理器
    logger.propagate = True  # 让它走根日志


# ===============================
# ✅ 方法1：动态修改全局日志级别
# ===============================
def set_log_level(level: str | int) -> None:
    """修改全局日志级别（包括 FastAPI/Uvicorn 所有日志）

    Args:
        level: 支持传入 'debug' / 'info' / 'warn' / 'error' 或 logging.DEBUG 等
    """
    # 字符串转 logging 级别
    if isinstance(level, str):
        level = level.upper()
        level = getattr(logging, level, logging.INFO)

    # 1. 修改根日志（全局生效）
    root_logger = logging.getLogger()
    root_logger.setLevel(level)


# ===============================
# ✅ 方法2：动态修改全局日志格式
# ===============================
def set_log_format(log_format: str) -> None:
    """修改全局日志格式，所有输出立即生效

    Args:
        log_format: 新的日志格式字符串
    """
    root_logger = logging.getLogger()
    formatter = logging.Formatter(log_format)

    # 给根日志下的所有处理器重新设置格式
    for handler in root_logger.handlers:
        handler.setFormatter(formatter)
