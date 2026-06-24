"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 日志配置与管理
"""
import logging
import sys
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from typing import Any

from .context import get_request_id

# -------------------------------------
# 全局注入request_id到日志记录
# -------------------------------------
old_factory = logging.getLogRecordFactory()


def _record_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
    """自定义日志记录工厂，在每条日志记录上注入当前请求的request_id

    Args:
        *args: 传递给原始工厂的位置参数
        **kwargs: 传递给原始工厂的关键字参数

    Returns:
        注入了request_id属性的日志记录对象
    """
    record = old_factory(*args, **kwargs)
    record.request_id = get_request_id() or '-'
    return record


logging.setLogRecordFactory(_record_factory)


# -------------------------------------
# 日志接管
# -------------------------------------
class UvicornNameRewriteFilter(logging.Filter):
    """日志过滤器，统一uvicorn.error / uvicorn.access的名称为uvicorn"""

    def filter(self, record: logging.LogRecord) -> bool:
        """将uvicorn.error / uvicorn.access的日志名称统一重写为uvicorn

        Args:
            record: 当前日志记录对象

        Returns:
            始终返回True，确保日志记录正常输出
        """
        # 把uvicorn.error / uvicorn.access的日志名称统一改成uvicorn
        if record.name in ('uvicorn.error', 'uvicorn.access'):
            record.name = 'uvicorn'

        return True


# 强制接管uvicorn的所有日志（核心！）
only_takeover = ['uvicorn', 'uvicorn.access', 'uvicorn.error', 'fastapi']

for logger_name in only_takeover:
    logger = logging.getLogger(logger_name)
    logger.handlers.clear()  # 清空默认处理器
    logger.propagate = True  # 让它走根日志
    logger.setLevel(logging.INFO)  # 屏蔽外部库的DEBUG日志，最低只输出INFO

    # 给error / access附加名称重写过滤器
    if logger_name in ('uvicorn.error', 'uvicorn.access'):
        logger.addFilter(UvicornNameRewriteFilter())

logging.getLogger('asyncio').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)


# -------------------------------------
# 文件轮转
# -------------------------------------
class _MonthlyRotatingFileHandler(TimedRotatingFileHandler):
    """按月轮转的日志处理器，以每月1日00:00:00为节点"""

    def __init__(self, filename: str, backup_count: int = 12, encoding: str = 'utf-8'):
        """初始化按月轮转处理器

        Args:
            filename: 日志文件路径
            backup_count: 保留的日志文件数量
            encoding: 文件编码
        """
        # 使用 'midnight' 作为基础，后续重写computeRollover实现按月整点
        super().__init__(filename, when='midnight', backupCount=backup_count, encoding=encoding)

    def computeRollover(self, current_time: float) -> float:
        """计算下次轮转时间（下月1日00:00:00）

        Args:
            current_time: 当前UNIX时间戳

        Returns:
            下次轮转的UNIX时间戳
        """
        dt = datetime.fromtimestamp(current_time)

        # 下月第一天的零点
        if dt.month == 12:
            next_month = datetime(dt.year + 1, 1, 1)
        else:
            next_month = datetime(dt.year, dt.month + 1, 1)

        return next_month.timestamp()


class _YearlyRotatingFileHandler(TimedRotatingFileHandler):
    """按年轮转的日志处理器，以每年1月1日00:00:00为节点"""

    def __init__(self, filename: str, backup_count: int = 5, encoding: str = 'utf-8'):
        """初始化按年轮转处理器

        Args:
            filename: 日志文件路径
            backup_count: 保留的日志文件数量
            encoding: 文件编码
        """
        super().__init__(filename, when='midnight', backupCount=backup_count, encoding=encoding)

    def computeRollover(self, current_time: float) -> float:
        """计算下次轮转时间（下一年1月1日00:00:00）

        Args:
            current_time: 当前UNIX时间戳

        Returns:
            下次轮转的UNIX时间戳
        """
        dt = datetime.fromtimestamp(current_time)
        next_year = datetime(dt.year + 1, 1, 1)
        return next_year.timestamp()


# 轮转周期映射：用户传入的语义字符串 → (when, interval) 或自定义Handler
_ROTATION_MAP: dict[str, tuple[str, int] | None] = {
    'second': ('S', 1),
    'minute': ('M', 1),
    'hour': ('H', 1),
    'day': ('midnight', 1),
    'week': ('W0', 1),  # 每周一00:00轮转
    'month': None,  # 自定义处理器
    'year': None,  # 自定义处理器
}
# 日志格式定义 (增加了时区和线程/进程信息，更利于排查并发问题)
NORMAL_FORMAT = '%(asctime)s.%(msecs)03d | %(levelname)-8s | %(process)d:%(thread)d | %(request_id)-32.32s | %(name)-30.30s | %(lineno)-4d | %(message)s'
# 配置日志格式
logging.basicConfig(level=logging.DEBUG, format=NORMAL_FORMAT, datefmt='%Y-%m-%d %H:%M:%S', force=True)


# 方法1：动态修改全局日志级别
def set_log_level(level: str | int) -> None:
    """修改全局日志级别（包括FastAPI/Uvicorn所有日志）

    Args:
        level: 支持传入 'debug' / 'info' / 'warn' / 'error' 或logging.DEBUG等
    """
    # 字符串转logging级别
    if isinstance(level, str):
        level = level.upper()
        level = getattr(logging, level, logging.INFO)

    # 1. 修改根日志（全局生效）
    root_logger = logging.getLogger()
    root_logger.setLevel(level)


# 方法2：动态修改全局日志格式
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


# 方法3：配置应用日志
def setup_logger(
        log_dir: str | Path | None = None,
        filename: str = 'app.log',
        rotation: str = 'day',
        backup_count: int = 30,
        encoding: str = 'utf-8',
        enable_console: bool = True,
) -> None:
    """一键配置应用的日志（支持控制台开关与文件日志）

    支持以整点为节点的日志轮转，可选粒度：
    - ``'second'``  — 每整秒
    - ``'minute'``  — 每整分钟（:00秒）
    - ``'hour'``    — 每整点小时（:00分）
    - ``'day'``     — 每天00:00（默认）
    - ``'week'``    — 每周一00:00
    - ``'month'``   — 每月1日00:00
    - ``'year'``    — 每年1月1日00:00

    Args:
        log_dir: 日志保存目录，若不提供则不开启文件日志
        filename: 日志文件名
        rotation: 轮转粒度，见上方说明，默认 ``'day'``
        backup_count: 保留的历史日志文件数量
        encoding: 文件编码
        enable_console: 是否在控制台输出日志
    """
    root_logger = logging.getLogger()

    # 1. 尝试获取现有的formatter
    current_formatter = None

    for h in root_logger.handlers:
        if h.formatter:
            current_formatter = h.formatter
            break

    if not current_formatter:
        current_formatter = logging.Formatter(NORMAL_FORMAT)

    # 2. 控制台输出处理
    if enable_console:
        # 检查是否已有非文件的StreamHandler
        has_console = any(
            isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
            for h in root_logger.handlers
        )

        if not has_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(current_formatter)
            root_logger.addHandler(console_handler)
    else:
        # 移除所有非文件的StreamHandler
        handlers_to_remove = [
            h
            for h in root_logger.handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        ]

        for h in handlers_to_remove:
            root_logger.removeHandler(h)

    # 3. 文件输出处理
    if log_dir:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        file_path = log_dir / filename

        # 检查是否已有相同路径的FileHandler
        has_file_handler = any(
            isinstance(h, logging.FileHandler) and getattr(h, 'baseFilename', '') == str(file_path.absolute())
            for h in root_logger.handlers
        )

        if not has_file_handler:
            rotation_key = rotation.lower()

            if rotation_key not in _ROTATION_MAP:
                raise ValueError(
                    f'不支持的轮转粒度 {rotation!r}，'
                    f'可选值：{list(_ROTATION_MAP.keys())}'
                )

            if rotation_key == 'month':
                file_handler = _MonthlyRotatingFileHandler(
                    str(file_path), backup_count=backup_count, encoding=encoding
                )
            elif rotation_key == 'year':
                file_handler = _YearlyRotatingFileHandler(
                    str(file_path), backup_count=backup_count, encoding=encoding
                )
            else:
                when, interval = _ROTATION_MAP[rotation_key]
                file_handler = TimedRotatingFileHandler(
                    filename=str(file_path), when=when, interval=interval,
                    backupCount=backup_count, encoding=encoding
                )

            file_handler.setFormatter(current_formatter)
            root_logger.addHandler(file_handler)
