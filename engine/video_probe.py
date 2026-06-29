"""FFmpeg 视频信息探测"""

import subprocess
import re
from engine.paths import get_ffmpeg, get_ffprobe


def get_video_info(path: str) -> dict:
    """返回 {width, height, fps, duration, sample_rate}"""
    info = {"fps": 24.0, "duration": 10, "sample_rate": 48000}
    ffprobe = get_ffprobe()
    ffmpeg = get_ffmpeg()

    try:
        r = subprocess.run(
            [ffprobe, "-v", "error",
             "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate,duration",
             "-of", "csv=p=0", path],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
        )
        parts = r.stdout.strip().split(",")
        if len(parts) >= 2 and parts[0] and parts[1]:
            info["width"], info["height"] = int(parts[0]), int(parts[1])
        if len(parts) >= 3 and parts[2]:
            num, den = parts[2].split("/") if "/" in parts[2] else (parts[2], "1")
            info["fps"] = float(num) / float(den) if float(den) != 0 else 24.0
        if len(parts) >= 4 and parts[3]:
            info["duration"] = float(parts[3])

        r2 = subprocess.run(
            [ffprobe, "-v", "error",
             "-select_streams", "a:0", "-show_entries", "stream=sample_rate",
             "-of", "csv=p=0", path],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
        )
        if r2.stdout.strip():
            info["sample_rate"] = int(r2.stdout.strip())
    except Exception:
        r = subprocess.run([ffmpeg, "-i", path], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=15)
        m = re.search(r"(\d+)x(\d+)", r.stderr)
        if m:
            info["width"], info["height"] = int(m.group(1)), int(m.group(2))
        m = re.search(r"(\d+(?:\.\d+)?)\s*fps", r.stderr)
        if m:
            info["fps"] = float(m.group(1))
        m = re.search(r"(\d+)\s*Hz", r.stderr)
        if m:
            info["sample_rate"] = int(m.group(1))
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", r.stderr)
        if m:
            info["duration"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    return info


def has_audio(path: str) -> bool:
    """检查视频是否有音频轨道"""
    try:
        r = subprocess.run(
            [get_ffprobe(), "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=codec_type", "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=10
        )
        return bool(r.stdout.strip())
    except Exception:
        return False
