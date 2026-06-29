"""语音转文案 — Whisper 封装"""
import subprocess
import os
from pathlib import Path
from engine.paths import get_ffmpeg
from config.logger import log

from collections import OrderedDict
import threading as _threading

_model_cache = OrderedDict()
_model_lock = _threading.Lock()
_MAX_CACHE = 2
_TRANSCRIBE_LOCK = _threading.Lock()

def extract_audio(video_path: str, output_dir: str) -> str:
    """提取视频音频到 wav，动态计算超时"""
    audio_path = os.path.join(output_dir, f"{Path(video_path).stem}_audio.wav")
    
    timeout = 60
    try:
        from engine.video_probe import get_video_info
        info = get_video_info(video_path)
        dur = info.get("duration", 60)
        timeout = max(60, dur * 0.5 + 30)
    except Exception:
        pass

    try:
        r = subprocess.run(
            [get_ffmpeg(), "-y", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
             "-ar", "16000", "-ac", "1", audio_path],
            capture_output=True, timeout=timeout
        )
        if r.returncode != 0:
            log.error(f"FFmpeg提取音频失败: {r.stderr.decode()[:200] if r.stderr else 'unknown'}")
            if os.path.exists(audio_path):
                os.remove(audio_path)
            return ""
    except Exception:
        log.error("FFmpeg提取音频异常", exc_info=True)
        if os.path.exists(audio_path):
            os.remove(audio_path)
        return ""
    return audio_path if os.path.exists(audio_path) else ""

def transcribe_audio(audio_path: str, model_name: str = "base") -> dict:
    """使用 Whisper 转录音频，全局互斥避免并发内存溢出"""
    import whisper
    
    with _TRANSCRIBE_LOCK:
        with _model_lock:
            if model_name not in _model_cache:
                if len(_model_cache) >= _MAX_CACHE:
                    _model_cache.popitem(last=False)
                _model_cache[model_name] = whisper.load_model(model_name)
            _model_cache.move_to_end(model_name)
            model = _model_cache[model_name]

        result = model.transcribe(audio_path, fp16=False, language="zh")
        segments = result.get("segments", [])

        if segments:
            parts = []
            for seg in segments:
                t = seg.get("text", "").strip()
                if not t:
                    continue
                if not t.endswith(("。", "！", "？", ".", "!", "?")):
                    t += "。"
                parts.append(t)
            text = "".join(parts).strip()
        else:
            text = result.get("text", "").strip()

        return {"text": text, "segments": segments, "language": result.get("language", "zh")}
