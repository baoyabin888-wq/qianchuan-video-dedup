"""跨平台路径助手"""

import os
import sys
from pathlib import Path


def user_data_dir() -> Path:
    """用户数据目录：Mac ~/、Win %APPDATA%"""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return Path(base) / "ecom_toolbox"
    return Path.home() / ".ecom_toolbox"


def desktop_dir() -> Path:
    return Path.home() / "Desktop"


def resource_path(name: str) -> Path:
    """打包后资源路径"""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / name
    return Path(__file__).parent.parent / "assets" / name


def get_ffmpeg() -> str:
    """跨平台 ffmpeg 路径"""
    if getattr(sys, "frozen", False):
        name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
        return str(Path(sys._MEIPASS) / name)
    return "ffmpeg"


def get_ffprobe() -> str:
    if getattr(sys, "frozen", False):
        name = "ffprobe.exe" if sys.platform == "win32" else "ffprobe"
        return str(Path(sys._MEIPASS) / name)
    return "ffprobe"


def get_ytdlp() -> str:
    if getattr(sys, "frozen", False):
        name = "yt-dlp.exe" if sys.platform == "win32" else "yt-dlp"
        return str(Path(sys._MEIPASS) / name)
    return "yt-dlp"
