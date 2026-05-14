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
    '%(asctime)s | %(levelname)-8s | %(name)-20s | %(lineno)4d | %(message)s'
)

# ===============================
# 清空已有日志，避免多次配置重复输出
# ===============================
root = logging.getLogger()
root.handlers.clear()
root.setLevel(logging.DEBUG)

# ===============================
# 配置日志格式
# ===============================
logging.basicConfig(
    level=logging.DEBUG,
    format=NORMAL_FORMAT
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
    logger.setLevel(logging.DEBUG)
