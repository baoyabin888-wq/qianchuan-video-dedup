"""FFmpeg 7 种去重操作"""
import os
import random
import subprocess
import threading
import time
from pathlib import Path
from engine.paths import get_ffmpeg
from engine.video_probe import get_video_info, has_audio
from engine.proc_manager import register as _reg_proc
from config.logger import log
from config.constants import (
    SPEED_RANGE, PITCH_RANGE, COLOR_RANGE,
    SATURATION_RANGE, CONTRAST_RANGE,
    DROPFRAME_MIN, DROPFRAME_MAX,
    BLACKFRAME_DURATION, BLACKFRAME_FPS,
    FFMPEG_TIMEOUT, MAX_FFMPEG_WORKERS
)

FFMPEG = get_ffmpeg()
_FFMPEG_SEM = threading.Semaphore(MAX_FFMPEG_WORKERS)

def _run(cmd, timeout=FFMPEG_TIMEOUT, stop_event=None):
    """统一 FFmpeg 调用"""
    proc = None
    start = time.time()
    stderr_lines = []
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError:
        raise RuntimeError("未检测到 FFmpeg，请先安装并配置环境变量")
    try:
        _reg_proc(proc)
        def _drain_stderr():
            for line in proc.stderr:
                stderr_lines.append(line)
        threading.Thread(target=_drain_stderr, daemon=True).start()
        while True:
            try:
                proc.wait(timeout=0.3)
                break
            except subprocess.TimeoutExpired:
                if stop_event and stop_event.is_set():
                    proc.kill()
                    proc.wait()
                    raise RuntimeError("已取消")
                if time.time() - start > timeout:
                    proc.kill()
                    proc.wait()
                    raise RuntimeError(f"FFmpeg 超时 ({timeout}s)")
        if proc.returncode != 0:
            err = "".join(stderr_lines).strip()[-100:]
            raise RuntimeError(f"FFmpeg: {err}")
    finally:
        if proc and proc.poll() is None:
            proc.kill()
            proc.wait()

OPS = [
    ("⏏", "抽帧"),
    ("⟳", "变速"),
    ("◐", "色彩"),
    ("⇲", "缩放"),
    ("♪", "音频"),
    ("⬚", "裁边"),
    ("■", "黑帧"),
]

INTENSITY_MAP = {
    "标准": 4,
    "重度": 6,
}

def _build_filter_chain(enabled_mask, video_info):
    """根据选中操作构建视频+音频滤镜链"""
    v_filters = []
    a_filters = []
    w, h = video_info.get("width"), video_info.get("height")
    fps = video_info.get("fps", 24.0)
    sr = video_info.get("sample_rate", 48000)
    duration = max(video_info.get("duration", 1.0), 1.0)
    total_frames = max(int(duration * fps), 1)

    if enabled_mask[0]:
        max_drop = min(DROPFRAME_MAX, max(1, total_frames // 15))
        min_drop = min(DROPFRAME_MIN, max_drop)
        n_drop = random.randint(min_drop, max_drop) if min_drop <= max_drop else 1
        start_zone = max(0, int(total_frames * 0.1))
        end_zone = max(start_zone + n_drop, min(total_frames - 1, int(total_frames * 0.9)))
        if end_zone - start_zone < n_drop:
            start_zone, end_zone = 0, total_frames
        sample_count = min(n_drop, end_zone - start_zone)
        if sample_count <= 0:
            sample_count = 1
            end_zone = total_frames
            start_zone = 0
        drop_frames = sorted(random.sample(range(start_zone, end_zone), sample_count))
        v_cond = "+".join([f"eq(n,{f})" for f in drop_frames])
        v_filters.append(f"select='not({v_cond})'")
        v_filters.append("setpts=N/FRAME_RATE/TB")
        a_cond = "+".join([f"between(t,{f/fps},{f/fps+1/fps})" for f in drop_frames])
        a_filters.append(f"aselect='not({a_cond})'")
        a_filters.append("asetpts=N/SR/TB")

    if enabled_mask[1]:
        factor = round(random.uniform(*SPEED_RANGE), 2)
        v_filters.append(f"setpts={1/factor}*PTS")
        a_filters.append(f"atempo={factor}")

    if enabled_mask[2]:
        b = round(random.uniform(*COLOR_RANGE), 2)
        c = round(random.uniform(*CONTRAST_RANGE), 2)
        s = round(random.uniform(*SATURATION_RANGE), 2)
        v_filters.append(f"eq=brightness={b}:contrast={c}:saturation={s}")

    if enabled_mask[3] and w and h:
        v_filters.append(f"scale=iw*0.99:ih*0.99,scale={w}:{h}:flags=lanczos")

    if enabled_mask[4]:
        pitch = round(random.uniform(*PITCH_RANGE), 2)
        a_filters.append(f"asetrate={sr}*{pitch}")
        a_filters.append(f"atempo={1/pitch}")

    if enabled_mask[5] and w and h:
        cw = random.randint(1, max(1, min(4, w // 8)))
        ch = random.randint(1, max(1, min(4, h // 8)))
        if w > cw * 2 and h > ch * 2:
            v_filters.append(f"crop={w-cw*2}:{h-ch*2}:{cw}:{ch}")
            v_filters.append(f"scale={w}:{h}")

    return v_filters, a_filters

def process_one(video_path, output_dir, enabled_mask, progress_cb, stop_event=None):
    """处理单个视频"""
    name = Path(video_path).stem
    ext = Path(video_path).suffix or ".mp4"
    final = os.path.join(output_dir, f"{name}_去重{ext}")

    for old in Path(output_dir).glob(f"_tmp_{name}_*{ext}"):
        try:
            old.unlink()
        except Exception:
            pass

    ops_to_run = [op_name for (_icon, op_name), enabled in zip(OPS, enabled_mask) if enabled]
    if not ops_to_run:
        return {"status": "error", "ops": ["未选择任何操作"]}

    safe_mask = list(enabled_mask)
    while len(safe_mask) < len(OPS):
        safe_mask.append(False)
    if len(OPS) != len(enabled_mask):
        log.warning(f"enabled_mask 长度({len(enabled_mask)})与 OPS({len(OPS)})不匹配，已补齐")

    try:
        acquired = False
        while True:
            if stop_event and stop_event.is_set():
                return {"status": "error", "ops": ["已取消"]}
            if _FFMPEG_SEM.acquire(timeout=0.5):
                acquired = True
                break

        info = get_video_info(video_path)
        has_audio_track = has_audio(video_path)
        v_filters, a_filters = _build_filter_chain(safe_mask, info)
        black_frame_enabled = safe_mask[6] if len(safe_mask) > 6 else False

        if progress_cb:
            progress_cb(f"处理中 ({'、'.join(ops_to_run)})")

        cmd = [FFMPEG, "-y", "-i", video_path]
        output_args = []

        if not black_frame_enabled:
            if v_filters:
                cmd += ["-vf", ",".join(v_filters)]
                output_args += ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "23"]
            else:
                output_args += ["-c:v", "copy"]
            if a_filters and has_audio_track:
                cmd += ["-af", ",".join(a_filters)]
                output_args += ["-c:a", "aac", "-b:a", "128k"]
            elif has_audio_track:
                output_args += ["-c:a", "copy"]
            else:
                output_args += ["-an"]
            cmd += output_args + [final]
            _run(cmd, stop_event=stop_event)
        else:
            w, h = info.get("width"), info.get("height")
            fps = info.get("fps", 24.0)
            sr = info.get("sample_rate", 48000)
            if not w or not h:
                raise RuntimeError("无法解析视频尺寸")

            filter_parts = []
            v_out = "v_main"
            a_out = "a_main"
            if v_filters:
                filter_parts.append(f"[1:v]{','.join(v_filters)}[{v_out}]")
            else:
                v_out = "1:v"
            if has_audio_track and a_filters:
                filter_parts.append(f"[1:a]{','.join(a_filters)}[{a_out}]")
            elif has_audio_track:
                a_out = "1:a"

            cmd = [
                FFMPEG, "-y",
                "-f", "lavfi", "-i", f"color=black:s={w}x{h}:d={BLACKFRAME_DURATION}:r={fps}",
                "-i", video_path,
                "-f", "lavfi", "-i", f"color=black:s={w}x{h}:d={BLACKFRAME_DURATION}:r={fps}",
            ]
            if has_audio_track:
                cmd += [
                    "-f", "lavfi", "-i", f"anullsrc=r={sr}:cl=stereo:d={BLACKFRAME_DURATION}",
                    "-f", "lavfi", "-i", f"anullsrc=r={sr}:cl=stereo:d={BLACKFRAME_DURATION}",
                ]
                concat_inputs = f"[0:v][3:a][{v_out}][{a_out}][2:v][4:a]"
                filter_parts.append(f"{concat_inputs}concat=n=3:v=1:a=1[outv][outa]")
                output_args = ["-map", "[outv]", "-map", "[outa]", "-c:a", "aac", "-b:a", "128k"]
            else:
                concat_inputs = f"[0:v][{v_out}][2:v]"
                filter_parts.append(f"{concat_inputs}concat=n=3:v=1:a=0[outv]")
                output_args = ["-map", "[outv]", "-an"]

            cmd += ["-filter_complex", ";".join(filter_parts),
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23"] + output_args + [final]
            _run(cmd, stop_event=stop_event)

        return {"status": "done", "ops": ops_to_run}
    except Exception as e:
        log.error(f"视频处理失败: {e}", exc_info=True)
        if os.path.exists(final):
            try:
                os.remove(final)
            except Exception:
                pass
        return {"status": "error", "ops": [str(e)[:50]]}
    finally:
        if acquired:
            _FFMPEG_SEM.release()
