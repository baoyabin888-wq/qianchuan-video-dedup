"""统一日志系统 — 分级输出到文件，支持按天切割"""
import logging
import logging.handlers
import sys
from engine.paths import user_data_dir

_LOG_DIR = user_data_dir() / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_LOG_FILE = _LOG_DIR / "app.log"

# 全局初始化标记，仅配置一次根日志器
_initialized = False

def _init_root_logger():
    """初始化根日志器，全局仅执行一次"""
    global _initialized
    if _initialized:
        return
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.propagate = False

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 文件处理器：按天切割，保留7天
    file_handler = logging.handlers.TimedRotatingFileHandler(
        _LOG_FILE, when="D", interval=1, backupCount=7,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(fmt)
    root_logger.addHandler(file_handler)

    # 控制台输出（开发调试用）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(fmt)
    root_logger.addHandler(console_handler)
    
    _initialized = True

def get_logger(name: str = "app") -> logging.Logger:
    """获取日志器，全局单例配置"""
    _init_root_logger()
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    return logger

# 全局默认日志器
log = get_logger("app")
