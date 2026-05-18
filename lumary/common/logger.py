"""
@Author     : zarkhan
@Date       : 2026/5/14
@Description:
"""
import logging
import sys
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler

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


# ===============================
# ✅ 方法3：配置应用日志
# ===============================
def setup_logger(
    log_dir: str | Path | None = None,
    filename: str = 'app.log',
    when: str = 'midnight',
    backup_count: int = 30,
    encoding: str = 'utf-8',
    enable_console: bool = True
) -> None:
    """一键配置应用的日志（支持控制台开关与文件日志）

    Args:
        log_dir: 日志保存目录。若不提供，则不开启文件日志。
        filename: 日志文件名。
        when: 轮转周期 (如 'midnight' 每天半夜轮转, 'H' 每小时)。
        backup_count: 保留的日志文件数量。
        encoding: 文件编码。
        enable_console: 是否在控制台输出日志。
    """
    root_logger = logging.getLogger()

    # 1. 尝试获取现有的 formatter
    current_formatter = None
    for h in root_logger.handlers:
        if h.formatter:
            current_formatter = h.formatter
            break
    if not current_formatter:
        current_formatter = logging.Formatter(NORMAL_FORMAT)

    # 2. 控制台输出处理
    if enable_console:
        # 检查是否已有非文件的 StreamHandler
        has_console = any(
            isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
            for h in root_logger.handlers
        )
        if not has_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(current_formatter)
            root_logger.addHandler(console_handler)
    else:
        # 移除所有非文件的 StreamHandler
        handlers_to_remove = [
            h for h in root_logger.handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        ]
        for h in handlers_to_remove:
            root_logger.removeHandler(h)

    # 3. 文件输出处理
    if log_dir:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        file_path = log_dir / filename

        # 检查是否已有相同路径的 FileHandler
        has_file_handler = any(
            isinstance(h, logging.FileHandler) and getattr(h, 'baseFilename', '') == str(file_path.absolute())
            for h in root_logger.handlers
        )
        
        if not has_file_handler:
            file_handler = TimedRotatingFileHandler(
                filename=str(file_path),
                when=when,
                interval=1,
                backupCount=backup_count,
                encoding=encoding
            )
            file_handler.setFormatter(current_formatter)
            root_logger.addHandler(file_handler)
