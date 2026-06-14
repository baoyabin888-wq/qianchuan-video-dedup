"""
电商工具箱 v3.2 — Flet 版本
Tab 1: 视频去重 | Tab 2: 无水印下载 | Tab 3: 语音转文案 | Tab 4: AI生图
"""
import os, sys, random, subprocess, re, time, threading, json
from pathlib import Path

# 仅在 PyInstaller 打包后（Windows EXE 环境）绕过 SSL 证书问题
# 开发环境保留 SSL 验证确保安全
import ssl
if getattr(sys, 'frozen', False):
    ssl._create_default_https_context = ssl._create_unverified_context

import flet as ft

# ═══════════════════════════════════════════════════════
# 处理引擎
# ═══════════════════════════════════════════════════════

if getattr(sys, 'frozen', False):
    _IS_WIN = sys.platform == 'win32'
    FFMPEG = os.path.join(sys._MEIPASS, "ffmpeg.exe" if _IS_WIN else "ffmpeg")
    YTDLP = os.path.join(sys._MEIPASS, "yt-dlp.exe" if _IS_WIN else "yt-dlp")
else:
    FFMPEG = "ffmpeg"
    YTDLP = "yt-dlp"

def run_ffmpeg(cmd, timeout=300):
    """统一 FFmpeg 调用，默认 5 分钟超时"""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            raise RuntimeError(f"FFmpeg: {r.stderr.strip()[-100:]}")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"FFmpeg 超时 ({timeout}s)")

def op_speed(inp, out, cb):
    factor = round(random.uniform(0.96, 1.04), 2)
    cb(f"变速 ×{factor}")
    # 无音频流时只处理视频
    run_ffmpeg([FFMPEG, "-y", "-i", inp, "-filter_complex",
                f"[0:v]setpts={1/factor}*PTS[v];[0:a]atempo={factor}[a]",
                "-map", "[v]", "-map", "[a]?", "-c:v", "libx264", "-preset", "ultrafast",
                "-crf", "23", "-c:a", "aac", "-b:a", "128k", out])

def op_color(inp, out, cb):
    b, c, s = round(random.uniform(-0.05, 0.05), 2), round(random.uniform(0.95, 1.05), 2), round(random.uniform(0.95, 1.05), 2)
    cb(f"色彩 b{b} c{c} s{s}")
    run_ffmpeg([FFMPEG, "-y", "-i", inp, "-vf",
                f"eq=brightness={b}:contrast={c}:saturation={s}",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-c:a", "copy", out])

def op_scale(inp, out, cb):
    cb("微缩放 99%")
    run_ffmpeg([FFMPEG, "-y", "-i", inp, "-vf",
                "scale=iw*0.99:ih*0.99,scale=iw:ih:flags=lanczos",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-c:a", "copy", out])

def get_ffprobe():
    """返回 ffprobe 路径"""
    if getattr(sys, 'frozen', False):
        return [FFMPEG]  # 打包后用 ffmpeg 代替 ffprobe
    return ["ffprobe"]

def get_video_info(path):
    """返回 {width, height, fps, duration, sample_rate}"""
    info = {"fps": 24.0, "duration": 10, "sample_rate": 48000}
    try:
        r = subprocess.run(
            get_ffprobe() + ["-v", "error",
             "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate,duration",
             "-select_streams", "a:0", "-show_entries", "stream=sample_rate",
             "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=10
        )
        lines = [ln for ln in r.stdout.strip().split('\n') if ln]
        if lines:
            parts = lines[0].split(',')
            if len(parts) >= 2 and parts[0] and parts[1]:
                info["width"] = int(parts[0]); info["height"] = int(parts[1])
            if len(parts) >= 3 and parts[2]:
                num, den = parts[2].split('/') if '/' in parts[2] else (parts[2], '1')
                info["fps"] = float(num) / float(den) if float(den) != 0 else 24.0
            if len(parts) >= 4 and parts[3]:
                info["duration"] = float(parts[3])
        if len(lines) >= 2 and lines[1]:
            info["sample_rate"] = int(lines[1])
    except Exception:
        # 回退：用 ffmpeg -i 解析（打包环境无需 ffprobe）
        r = subprocess.run([FFMPEG, "-i", path], capture_output=True, text=True, timeout=15)
        m = re.search(r'(\d+)x(\d+)', r.stderr)
        if m: info["width"], info["height"] = int(m.group(1)), int(m.group(2))
        m = re.search(r'(\d+(?:\.\d+)?)\s*fps', r.stderr)
        if m: info["fps"] = float(m.group(1))
        m = re.search(r'(\d+)\s*Hz', r.stderr)
        if m: info["sample_rate"] = int(m.group(1))
        m = re.search(r'Duration:\s*(\d+):(\d+):(\d+\.\d+)', r.stderr)
        if m:
            info["duration"] = int(m.group(1))*3600 + int(m.group(2))*60 + float(m.group(3))
    return info

def op_audio(inp, out, cb):
    pitch = round(random.uniform(0.98, 1.02), 2)
    cb(f"音频变调 ×{pitch}")
    # atempo 支持 0.5~2.0，[a]? 使无音频流时可选，避免崩溃
    run_ffmpeg([FFMPEG, "-y", "-i", inp, "-filter_complex",
                f"[0:a]atempo={pitch}[a]",
                "-map", "0:v", "-map", "[a]?", "-c:v", "libx264", "-preset", "ultrafast",
                "-crf", "23", "-c:a", "aac", "-b:a", "128k", out])

def op_crop(inp, out, cb):
    info = get_video_info(inp)
    w, h = info.get("width"), info.get("height")
    if not w or not h:
        raise RuntimeError("无法解析视频尺寸")
    cw = random.randint(1, max(1, min(4, w // 8)))
    ch = random.randint(1, max(1, min(4, h // 8)))
    if w <= cw * 2 or h <= ch * 2:
        raise RuntimeError(f"视频尺寸过小，无法裁剪: {w}x{h}")
    cb(f"边缘微裁 {cw}px")
    run_ffmpeg([FFMPEG, "-y", "-i", inp, "-vf",
                f"crop={w-cw*2}:{h-ch*2}:{cw}:{ch},scale={w}:{h}",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-c:a", "copy", out])

def op_black(inp, out, cb):
    cb("首尾黑帧")
    info = get_video_info(inp)
    w, h = info.get("width"), info.get("height")
    sr = info.get("sample_rate", 48000)
    if not w or not h:
        raise RuntimeError("无法解析视频尺寸")
    run_ffmpeg([FFMPEG, "-y", "-f", "lavfi", "-i",
                f"color=black:s={w}x{h}:d=0.05:r=24",
                "-ar", str(sr),
                "-i", inp, "-f", "lavfi", "-i",
                f"color=black:s={w}x{h}:d=0.05:r=24",
                "-ar", str(sr),
                "-filter_complex", "[0:v][1:v][1:a][2:v]concat=n=3:v=1:a=1[outv][outa]",
                "-map", "[outv]", "-map", "[outa]", "-c:v", "libx264", "-preset", "ultrafast",
                "-crf", "23", "-c:a", "aac", "-b:a", "128k", "-shortest", out])

def op_dropframe(inp, out, cb):
    info = get_video_info(inp)
    fps = info["fps"]
    duration = max(info["duration"], 5.0)  # 最小5秒，防止过短视频
    total_frames = int(duration * fps)
    if total_frames < 10:
        raise RuntimeError(f"视频过短无法抽帧: {duration:.1f}s")
    
    n_drop = random.randint(3, min(5, total_frames // 20))  # 最多抽5%帧
    start_zone = max(1, int(total_frames * 0.1))
    end_zone = min(total_frames - 1, int(total_frames * 0.9))
    if end_zone - start_zone < n_drop:
        start_zone, end_zone = 0, total_frames
    drop_frames = sorted(random.sample(range(start_zone, end_zone), min(n_drop, end_zone - start_zone)))
    
    cb(f"抽帧 ×{len(drop_frames)}")
    select_expr = "+".join([f"eq(n,{f})" for f in drop_frames])
    
    # 视频 select
    vf = f"select='not({select_expr})',setpts=N/FRAME_RATE/TB"
    # 音频: 按帧时间戳精确匹配
    af = "aselect='not(" + "+".join([f"between(t,{f/fps},{f/fps+1/fps})" for f in drop_frames]) + ")',asetpts=N/SR/TB"
    
    run_ffmpeg([FFMPEG, "-y", "-i", inp,
                "-vf", vf, "-af", af,
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k", out])


OTHERS = [
    ("变速", op_speed), ("色彩微调", op_color), ("微缩放", op_scale),
    ("音频变调", op_audio), ("边缘微裁", op_crop), ("首尾黑帧", op_black),
]
MUST = ("抽帧", op_dropframe)
INTENSITY_MAP = {"标准": 3, "重度": 5}

def process_one(video_path, output_dir, intensity, progress_cb):
    name = Path(video_path).stem
    ext = Path(video_path).suffix or ".mp4"
    n = min(INTENSITY_MAP[intensity], len(OTHERS) + 1)
    ops = [MUST] + random.sample(OTHERS, n - 1)

    # 清理上次残留的临时文件
    for old_tmp in Path(output_dir).glob(f"_tmp_{name}_*{ext}"):
        try: old_tmp.unlink()
        except Exception: pass

    tmp = video_path
    tmp_files = []
    ops_used = []

    try:
        for i, (op_name, op_func) in enumerate(ops):
            progress_cb(f"{op_name} ({i+1}/{n})")
            tmp_out = os.path.join(output_dir, f"_tmp_{name}_{i}{ext}")
            try:
                op_func(tmp, tmp_out, lambda msg: progress_cb(f"{op_name} {msg}"))
                tmp_files.append(tmp_out)
                tmp = tmp_out
                ops_used.append(op_name)
            except Exception as e:
                progress_cb(f"✕ {op_name}: {str(e)[:50]}")
                ops_used.append(f"✕{op_name}")
                break
    finally:
        # 确保清理临时文件
        final = os.path.join(output_dir, f"{name}_去重{ext}")
        if tmp != video_path and os.path.exists(tmp):
            os.replace(tmp, final)
        for tf in tmp_files:
            if os.path.exists(tf) and tf != final:
                try: os.remove(tf)
                except Exception: pass

    return {"status": "done" if ops_used and not ops_used[-1].startswith("✕") else "error", "ops": ops_used}


# ═══════════════════════════════════════════════════════
# Flet UI
# ═══════════════════════════════════════════════════════

def main(page: ft.Page):
    page.title = "电商工具箱 v3.2"
    page.window.width = 1000
    page.window.height = 720
    page.window.min_width = 850
    page.window.min_height = 600
    page.padding = 0
    page.bgcolor = "#08090A"
    page.theme_mode = ft.ThemeMode.DARK

    # 线程安全更新
    def safe_update():
        try:
            page.update()
        except Exception:
            pass

    # ── Theme ──
    ACCENT = "#5E6AD2"
    BG_PANEL = "#0F1011"
    BG_SURFACE = "#191A1B"
    TEXT = "#D0D6E0"
    TEXT_PRIMARY = "#F7F8F8"
    TEXT_MUTED = "#8A8F98"
    BORDER = "#23252A"
    GREEN = "#34D399"
    RED = "#F87171"

    # Border helper — 兼容 PyInstaller 打包
    def _bd():
        bs = ft.BorderSide(1, BORDER)
        return ft.Border(top=bs, left=bs, right=bs, bottom=bs)

    # ── State ──
    state_lock = threading.Lock()
    files = []
    running = False
    current_idx = 0
    completed = 0
    intensity = "标准"
    output_dir = os.path.join(os.path.expanduser("~"), "Desktop", "去重输出")

    # ═══════════════════════════════════════════════
    # Tab 1: 视频去重 — widgets
    # ═══════════════════════════════════════════════

    file_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("文件", size=13, color=TEXT_PRIMARY)),
            ft.DataColumn(ft.Text("时长", size=13, color=TEXT_PRIMARY)),
            ft.DataColumn(ft.Text("大小", size=13, color=TEXT_PRIMARY)),
            ft.DataColumn(ft.Text("状态", size=13, color=TEXT_PRIMARY)),
            ft.DataColumn(ft.Text("操作", size=13, color=TEXT_PRIMARY)),
        ],
        border_radius=6,
        heading_row_color={"": "#191A1B"},
        data_row_color={"": "#0F1011"},
        heading_text_style=ft.TextStyle(size=13, weight=ft.FontWeight.W_600),
    )

    progress_bar = ft.ProgressBar(value=0, bgcolor="#23252A", color=ACCENT, height=4)
    progress_text = ft.Text("就绪", size=12, color=TEXT_MUTED)

    intensity_dropdown = ft.Dropdown(
        value="标准",
        options=[
            ft.dropdown.Option("标准", "标准 — 3项"),
            ft.dropdown.Option("重度", "重度 — 5项"),
        ],
        width=160, bgcolor=BG_SURFACE, color=TEXT_PRIMARY,
        border_color=BORDER, border_radius=6, text_size=13,
    )

    output_field = ft.TextField(
        value=output_dir, width=320,
        bgcolor=BG_SURFACE, color=TEXT_PRIMARY,
        border_color=BORDER, border_radius=6,
        text_size=13, content_padding=ft.Padding(left=12, right=12, top=8, bottom=8),
    )

    # ═══════════════════════════════════════════════
    # Tab 2: 视频下载 — widgets
    # ═══════════════════════════════════════════════

    url_input = ft.TextField(
        hint_text="每行一条链接 · 支持抖音 / TikTok / 快手 / B站",
        multiline=True, min_lines=5, max_lines=8,
        bgcolor=BG_SURFACE, color=TEXT_PRIMARY,
        border_color=BORDER, border_radius=8,
        text_size=13, content_padding=ft.Padding(left=12, top=12, right=12, bottom=12),
        hint_style=ft.TextStyle(color="#62666D"),
    )

    dl_output_field = ft.TextField(
        value=os.path.join(os.path.expanduser("~"), "Desktop", "千川素材下载"),
        width=220, bgcolor=BG_SURFACE, color=TEXT_PRIMARY,
        border_color=BORDER, border_radius=6,
        text_size=13, content_padding=ft.Padding(left=12, right=12, top=8, bottom=8),
    )

    dl_list = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO)
    dl_status = ft.Text("", size=12, color=TEXT_MUTED)

    # ═══════════════════════════════════════════════
    # Tab 3: 语音转文字 — widgets
    # ═══════════════════════════════════════════════

    extract_file_text = ft.Text("选择视频文件", size=14, color=TEXT_MUTED)
    extract_video_path = [None]  # list so closures can mutate
    whisper_model_dropdown = ft.Dropdown(
        value="base",
        options=[
            ft.dropdown.Option("tiny", "tiny — 最快/精度低"),
            ft.dropdown.Option("base", "base — 平衡"),
            ft.dropdown.Option("small", "small — 较准"),
            ft.dropdown.Option("medium", "medium — 精准/较慢"),
        ],
        width=180, bgcolor=BG_SURFACE, color=TEXT_PRIMARY,
        border_color=BORDER, border_radius=6, text_size=12,
    )
    extract_results = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO)
    extract_status = ft.Text("", size=12, color=TEXT_MUTED)

    # ═══════════════════════════════════════════════
    # Tab 1: 视频去重 — callbacks
    # ═══════════════════════════════════════════════

    def get_dur(path):
        try:
            r = subprocess.run([FFMPEG, "-i", path], capture_output=True, text=True, timeout=10)
            m = re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)', r.stderr)
            if m:
                return f"{int(m.group(1))*3600+int(m.group(2))*60+float(m.group(3)):.1f}s"
        except Exception: pass
        return "?"

    def add_files_to_list(paths):
        with state_lock:
            for p in paths:
                if p in [f["path"] for f in files]: continue
                dur = get_dur(p)
                size = f"{Path(p).stat().st_size/1024/1024:.1f} MB"
                files.append({"path": p, "name": Path(p).name, "dur": dur, "size": size})
        refresh_file_table()

    def refresh_file_table():
        file_table.rows.clear()
        for f in files:
            file_table.rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(f["name"], size=12, color=TEXT_PRIMARY)),
                ft.DataCell(ft.Text(f["dur"], size=12, color=TEXT_MUTED)),
                ft.DataCell(ft.Text(f["size"], size=12, color=TEXT_MUTED)),
                ft.DataCell(ft.Text(f.get("status", "等待"), size=12, color=TEXT_MUTED)),
                ft.DataCell(ft.Text(f.get("ops", ""), size=12, color=TEXT_MUTED)),
            ]))
        safe_update()

    def pick_files_result(e: ft.FilePickerResultEvent):
        if e.files: add_files_to_list([f.path for f in e.files])

    def pick_folder_result(e: ft.FilePickerResultEvent):
        if e.path:
            exts = {'.mp4', '.mov', '.avi', '.mkv'}
            add_files_to_list([str(p) for p in sorted(Path(e.path).iterdir())
                               if p.suffix.lower() in exts])

    def pick_output_result(e: ft.FilePickerResultEvent):
        if e.path:
            nonlocal output_dir
            output_dir = e.path
            output_field.value = e.path
            safe_update()

    file_picker = ft.FilePicker()
    file_picker.on_result = pick_files_result
    folder_picker = ft.FilePicker()
    folder_picker.on_result = pick_folder_result
    output_picker = ft.FilePicker()
    output_picker.on_result = pick_output_result
    page.overlay.extend([file_picker, folder_picker, output_picker])

    def clear_files_click(e):
        with state_lock:
            files.clear()
        file_table.rows.clear()
        progress_bar.value = 0
        progress_text.value = "就绪"
        safe_update()

    def update_file_status(path, status, ops=""):
        with state_lock:
            for f in files:
                if f["path"] == path:
                    f["status"] = status; f["ops"] = ops; break
        for row, f in zip(file_table.rows, files):
            if f["path"] == path:
                row.cells[3].content.value = status
                row.cells[4].content.value = ops
                break
        safe_update()

    def process_queue():
        nonlocal current_idx, completed, running
        with state_lock:
            if not running or current_idx >= len(files):
                finish_batch(); return
            path = files[current_idx]["path"]
        os.makedirs(output_dir, exist_ok=True)
        update_file_status(path, "处理中", "启动...")

        def cb(msg):
            with state_lock:
                for f in files:
                    if f["path"] == path: f["status"] = "处理中"; f["ops"] = msg; break
            for row, f in zip(file_table.rows, files):
                if f["path"] == path:
                    row.cells[3].content.value = "处理中"
                    row.cells[4].content.value = msg
                    break
            try: safe_update()
            except Exception: pass

        def worker():
            nonlocal current_idx, completed
            try:
                result = process_one(path, output_dir, intensity, cb)
            except Exception as e:
                result = {"status": "error", "ops": [f"✕{str(e)[:30]}"]}
            if result["status"] == "done":
                update_file_status(path, "✓ 完成", ", ".join(result["ops"]))
            else:
                update_file_status(path, "✕ 失败", ", ".join(result["ops"]))
            with state_lock:
                completed += 1; current_idx += 1
                progress_bar.value = completed / len(files)
                progress_text.value = f"已完成 {completed}/{len(files)}"
            safe_update()
            process_queue()

        threading.Thread(target=worker).start()

    def start_processing(e):
        nonlocal running, current_idx, completed
        if not files:
            page.snack_bar = ft.SnackBar(ft.Text("请先添加视频文件")); page.snack_bar.open = True; safe_update(); return
        outdir = output_dir; os.makedirs(outdir, exist_ok=True)
        for f in Path(outdir).glob("_tmp_*"):
            try: f.unlink()
            except Exception: pass
        with state_lock:
            running = True; current_idx = 0; completed = 0
        progress_bar.value = 0; progress_text.value = "处理中..."; safe_update()
        process_queue()

    def stop_processing(e):
        nonlocal running
        with state_lock:
            running = False
        progress_text.value = "已停止"; safe_update()
        try:
            for f in Path(output_dir).glob("_tmp_*"):
                try: f.unlink()
                except Exception: pass
        except Exception: pass

    def finish_batch():
        nonlocal running
        with state_lock:
            running = False
        progress_bar.value = 1; progress_text.value = f"✓ 完成 {len(files)} 条"
        try:
            for f in Path(output_dir).glob("_tmp_*"):
                try: f.unlink()
                except Exception: pass
        except Exception: pass
        safe_update()

    def export_report(e):
        with state_lock:
            fc = list(files)
        lines = [f"千川视频去重报告 - {len(fc)} 条", "=" * 50, ""]
        for f in fc:
            lines.append(f"📹 {f['name']}")
            lines.append(f"   时长: {f['dur']}  大小: {f['size']}")
            lines.append(f"   状态: {f.get('status','')}  操作: {f.get('ops','')}")
            lines.append("")
        path = os.path.join(output_dir, "去重报告.txt")
        with open(path, 'w', encoding='utf-8') as fh: fh.write('\n'.join(lines))
        page.snack_bar = ft.SnackBar(ft.Text(f"报告已保存: {path}")); page.snack_bar.open = True; safe_update()

    # ═══════════════════════════════════════════════
    # Tab 2: 视频下载 — callbacks (yt-dlp)
    # ═══════════════════════════════════════════════

    dl_running = [False]
    dl_current_proc = [None]  # 当前子进程引用，用于停止时 kill

    def download_videos(e):
        urls = [u.strip() for u in url_input.value.split('\n') if u.strip()]
        # 基础 URL 验证
        valid_urls = [u for u in urls if u.startswith(('http://', 'https://'))]
        if not valid_urls:
            page.snack_bar = ft.SnackBar(ft.Text("请输入有效的视频链接")); page.snack_bar.open = True; safe_update(); return
        if dl_running[0]:
            page.snack_bar = ft.SnackBar(ft.Text("下载正在进行中")); page.snack_bar.open = True; safe_update(); return

        dl_dir = dl_output_field.value
        os.makedirs(dl_dir, exist_ok=True)
        dl_list.controls.clear()
        dl_running[0] = True

        # Build item widgets
        item_rows = []
        item_status = []
        for i, url in enumerate(valid_urls):
            status_text = ft.Text("排队中", size=12, color=TEXT_MUTED)
            item_rows.append(ft.Row([
                ft.Icon(ft.Icons.VIDEO_FILE, size=18, color=TEXT_MUTED),
                ft.Text(url[:55] + "..." if len(url) > 55 else url, size=13, color=TEXT_PRIMARY),
                status_text,
            ], spacing=10))
            item_status.append(status_text)
            dl_list.controls.append(ft.Container(
                content=item_rows[-1],
                bgcolor=BG_SURFACE, border_radius=8, padding=12,
                border=_bd(),
            ))
        dl_status.value = f"下载中 0/{len(valid_urls)}"
        safe_update()

        def worker():
            success = 0
            for i, url in enumerate(valid_urls):
                if not dl_running[0]: break
                item_status[i].value = "下载中..."
                item_status[i].color = ACCENT
                dl_status.value = f"下载中 {success}/{len(urls)}"
                safe_update()

                try:
                    cmd = [
                        YTDLP,
                        "-o", os.path.join(dl_dir, "%(title)s.%(ext)s"),
                        "--no-playlist",
                        "--no-warnings",
                        "--print", "filename",
                        url
                    ]
                    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                    dl_current_proc[0] = proc  # 保存引用用于停止
                    out, _ = proc.communicate(timeout=600)
                    dl_current_proc[0] = None

                    if proc.returncode == 0 and out:
                        # yt-dlp --print filename 输出最后一行为下载文件路径
                        lines = [ln.strip() for ln in out.strip().split('\n') if ln.strip()]
                        filename = lines[-1] if lines else "已下载"
                        item_status[i].value = f"✓ {Path(filename).name if os.path.exists(filename) else filename}"
                        item_status[i].color = GREEN
                        success += 1
                    else:
                        last_err = ""
                        if out and out.strip():
                            err_lines = [ln for ln in out.strip().split('\n') if ln.strip()]
                            last_err = err_lines[-1][:40] if err_lines else ""
                        item_status[i].value = f"✕ {last_err}" if last_err else "✕ 下载失败"
                        item_status[i].color = RED
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()  # 防止僵尸进程
                    item_status[i].value = "✕ 超时"
                    item_status[i].color = RED
                except Exception as ex:
                    item_status[i].value = f"✕ {str(ex)[:40]}"
                    item_status[i].color = RED

                dl_status.value = f"下载中 {success}/{len(valid_urls)}"
                safe_update()

            dl_running[0] = False
            dl_status.value = f"✓ 完成 {success}/{len(valid_urls)} 条"
            safe_update()

        threading.Thread(target=worker).start()

    def stop_download(e):
        dl_running[0] = False
        # 真正终止正在运行的子进程
        if dl_current_proc[0] and dl_current_proc[0].poll() is None:
            dl_current_proc[0].terminate()
            try: dl_current_proc[0].wait(timeout=5)
            except Exception: dl_current_proc[0].kill()
        dl_status.value = "已停止"
        safe_update()

    def pick_dl_dir_result(e: ft.FilePickerResultEvent):
        if e.path: dl_output_field.value = e.path; safe_update()

    dl_dir_picker = ft.FilePicker()
    dl_dir_picker.on_result = pick_dl_dir_result
    page.overlay.append(dl_dir_picker)

    # ═══════════════════════════════════════════════
    # Tab 3: 语音转文字 — callbacks (Whisper)
    # ═══════════════════════════════════════════════

    def pick_extract_result(e: ft.FilePickerResultEvent):
        if e.files:
            extract_video_path[0] = e.files[0].path
            extract_file_text.value = e.files[0].name
            safe_update()

    extract_picker = ft.FilePicker()
    extract_picker.on_result = pick_extract_result
    page.overlay.append(extract_picker)

    # Tab 3 state
    extract_results_text = None  # 闭包引用，供export使用

    def extract_audio_and_transcribe(e):
        nonlocal extract_results_text
        vid_path = extract_video_path[0]
        if not vid_path or not os.path.exists(vid_path):
            page.snack_bar = ft.SnackBar(ft.Text("请先选择视频文件")); page.snack_bar.open = True; safe_update(); return

        model_name = whisper_model_dropdown.value
        extract_status.value = "提取音频中..."

        # 预创建结果控件（主线程安全），worker 只更新 .value
        result_text = ft.Text("", size=13, color=TEXT_PRIMARY, selectable=True)
        result_header = ft.Text(Path(vid_path).name, size=14, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY)
        result_model = ft.Text(f"模型: {model_name}", size=11, color=TEXT_MUTED)
        result_container = ft.Container(
            content=ft.Column([
                ft.Row([ft.Icon(ft.Icons.TRANSCRIBE, size=18, color=ACCENT), result_header]),
                result_model, ft.Divider(height=1, color=BORDER), result_text,
            ], spacing=4),
            bgcolor=BG_SURFACE, border_radius=8, padding=14,
            border=_bd(),
        )
        extract_results.controls.clear()
        extract_results.controls.append(result_container)
        extract_results_text = result_text  # 存储引用供导出
        safe_update()

        def worker():
            try:
                # Step 1: Extract audio
                audio_path = os.path.join(os.path.dirname(vid_path), f"_whisper_audio_{int(time.time())}.wav")
                try:
                    run_ffmpeg([FFMPEG, "-y", "-i", vid_path, "-vn", "-acodec", "pcm_s16le",
                                "-ar", "16000", "-ac", "1", audio_path], timeout=180)

                    extract_status.value = f"识别中... (模型: {model_name})"
                    safe_update()

                    # Step 2: Whisper (模型缓存，避免重复加载)
                    import whisper
                    cache_attr = f"_whisper_{model_name}"
                    if not hasattr(extract_audio_and_transcribe, cache_attr):
                        model = whisper.load_model(model_name)
                        setattr(extract_audio_and_transcribe, cache_attr, model)
                        extract_status.value = f"模型 {model_name} 加载完成，识别中..."
                        safe_update()
                    model = getattr(extract_audio_and_transcribe, cache_attr)
                    result_data = model.transcribe(audio_path, language="zh", fp16=False)
                    text = result_data["text"].strip()
                    result_text.value = text
                    extract_status.value = f"✓ 完成 — {len(text)} 字"
                finally:
                    try: os.remove(audio_path)
                    except Exception: pass

            except Exception as ex:
                result_text.value = f"✕ 错误: {str(ex)}"
                extract_status.value = "失败"
                try:
                    for af in Path(os.path.dirname(vid_path)).glob("_whisper_audio_*.wav"):
                        try: af.unlink()
                        except Exception: pass
                except Exception: pass

            safe_update()

        threading.Thread(target=worker).start()

    def export_extract_txt(e):
        # 使用闭包引用，不再遍历控件树
        text = extract_results_text.value if extract_results_text else ''
        if not text.strip():
            for ctrl in extract_results.controls:
                if hasattr(ctrl, 'content') and hasattr(ctrl.content, 'controls'):
                    for child in ctrl.content.controls:
                        if isinstance(child, ft.Text) and child.selectable:
                            text = child.value if child.value else ''; break
        if not text.strip():
            page.snack_bar = ft.SnackBar(ft.Text("没有可导出的文案")); page.snack_bar.open = True; safe_update(); return

        # Save to same dir as video
        vid_path = extract_video_path[0]
        if vid_path and os.path.exists(vid_path):
            save_path = os.path.join(os.path.dirname(vid_path),
                                     f"{Path(vid_path).stem}_文案.txt")
        else:
            save_path = os.path.join(os.path.expanduser("~"), "Desktop", "文案导出.txt")

        with open(save_path, 'w', encoding='utf-8') as fh: fh.write(text)
        page.snack_bar = ft.SnackBar(ft.Text(f"已保存: {save_path}")); page.snack_bar.open = True; safe_update()


    # ═══════════════════════════════════════════════
    # Layout
    # ═══════════════════════════════════════════════

    tab1 = ft.Column([
        ft.Text("素材去重", size=18, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
        ft.Text("拖拽视频文件，自动随机组合去重操作", size=13, color=TEXT_MUTED),
        ft.Divider(height=1, color=BORDER),
        ft.Row([
            ft.ElevatedButton("添加文件", icon=ft.Icons.ADD,
                              on_click=lambda e: file_picker.pick_files(
                                  allow_multiple=True,
                                  file_type=ft.FilePickerFileType.VIDEO)),
            ft.ElevatedButton("添加文件夹", icon=ft.Icons.FOLDER_OPEN,
                              on_click=lambda e: folder_picker.get_directory_path()),
            ft.ElevatedButton("清空", icon=ft.Icons.DELETE_OUTLINE, on_click=clear_files_click),
        ], spacing=8),
        ft.Container(
            content=ft.Column([file_table], scroll=ft.ScrollMode.AUTO, expand=True),
            expand=True, border_radius=8,
        ),
        ft.Divider(height=1, color=BORDER),
        ft.Row([
            ft.Text("输出:", size=13, color=TEXT_MUTED), output_field,
            ft.ElevatedButton("选择", icon=ft.Icons.FOLDER_OUTLINED,
                              on_click=lambda e: output_picker.get_directory_path()),
            ft.Text("强度:", size=13, color=TEXT_MUTED), intensity_dropdown,
        ], spacing=8, wrap=True),
        ft.Row([progress_bar], expand=True),
        ft.Row([
            progress_text,
            ft.Row([
                ft.ElevatedButton("导出报告", icon=ft.Icons.FILE_DOWNLOAD, on_click=export_report),
                ft.ElevatedButton("开始去重", icon=ft.Icons.PLAY_ARROW,
                                  bgcolor=ACCENT, color="white", on_click=start_processing),
                ft.ElevatedButton("停止", icon=ft.Icons.STOP, on_click=stop_processing),
            ], spacing=8),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
    ], spacing=8, expand=True)

    tab2 = ft.Column([
        ft.Text("视频下载", size=18, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
        ft.Text("粘贴短视频分享链接，自动去水印下载高清视频 · 抖音/TikTok/快手/B站", size=13, color=TEXT_MUTED),
        ft.Divider(height=1, color=BORDER),
        url_input,
        ft.Row([
            ft.Text("保存到:", size=13, color=TEXT_MUTED), dl_output_field,
            ft.ElevatedButton("选择", icon=ft.Icons.FOLDER_OUTLINED,
                              on_click=lambda e: dl_dir_picker.get_directory_path()),
            ft.ElevatedButton("开始下载", icon=ft.Icons.DOWNLOAD,
                              bgcolor=ACCENT, color="white", on_click=download_videos),
            ft.ElevatedButton("停止", icon=ft.Icons.STOP, on_click=stop_download),
        ], spacing=8, wrap=True),
        ft.Container(content=dl_list, expand=True, border_radius=8),
        dl_status,
    ], spacing=8, expand=True)

    tab3 = ft.Column([
        ft.Text("语音转文案", size=18, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
        ft.Text("提取视频音频 → Whisper 语音识别 → 输出文案", size=13, color=TEXT_MUTED),
        ft.Divider(height=1, color=BORDER),
        ft.Container(
            content=ft.Column([
                ft.Icon(ft.Icons.UPLOAD_FILE, size=32, color=TEXT_MUTED),
                extract_file_text,
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
            bgcolor=BG_SURFACE, border_radius=8, padding=40,
            border=_bd(),
            ink=True, on_click=lambda e: extract_picker.pick_files(
                allow_multiple=False, file_type=ft.FilePickerFileType.VIDEO),
        ),
        ft.Row([
            ft.Text("Whisper 模型:", size=13, color=TEXT_MUTED),
            whisper_model_dropdown,
            ft.ElevatedButton("开始识别", icon=ft.Icons.AUTO_AWESOME,
                              bgcolor=ACCENT, color="white", on_click=extract_audio_and_transcribe),
        ], spacing=12),
        extract_status,
        ft.Container(content=extract_results, expand=True, border_radius=8),
        ft.Row([
            ft.ElevatedButton("导出 TXT", icon=ft.Icons.TEXT_SNIPPET, on_click=export_extract_txt),
        ], spacing=8),
    ], spacing=8, expand=True)

    # ═══════════════════════════════════════════════
    # Tab 4: AI 生图 — MiniMax image-01
    # ═══════════════════════════════════════════════

    img_prompt = ft.TextField(
        hint_text="描述要生成的图片... 例如：年轻妈妈温柔给宝宝按摩腹部，暖光温馨，9:16竖屏",
        multiline=True, min_lines=6, max_lines=6,
        bgcolor=BG_SURFACE, color=TEXT_PRIMARY,
        border_color=BORDER, border_radius=8,
        text_size=13, content_padding=ft.Padding(left=12, top=12, right=12, bottom=12),
        hint_style=ft.TextStyle(color="#62666D"),
    )
    img_ratio = ft.Dropdown(
        value="9:16",
        options=[ft.dropdown.Option(k, v) for k, v in [
            ("1:1","1:1 正方"),("16:9","16:9 横版"),("9:16","9:16 竖版"),("4:3","4:3 标准"),("3:4","3:4 竖标")
        ]],
        width=140, bgcolor=BG_SURFACE, color=TEXT_PRIMARY,
        border_color=BORDER, border_radius=6, text_size=12,
    )
    img_count = ft.Dropdown(
        value="1",
        options=[ft.dropdown.Option(str(n), f"{n}张") for n in range(1,5)],
        width=90, bgcolor=BG_SURFACE, color=TEXT_PRIMARY,
        border_color=BORDER, border_radius=6, text_size=12,
    )
    img_optimize = ft.Switch(value=True, active_color=ACCENT)
    img_status = ft.Text("", size=12, color=TEXT_MUTED)
    img_grid = ft.Row([], wrap=True, spacing=8, scroll=ft.ScrollMode.AUTO)
    img_generating = [False]

    # API Key 配置（持久化到本地文件）
    _cfg_dir = os.path.join(os.path.expanduser("~"), ".电商工具箱")
    os.makedirs(_cfg_dir, exist_ok=True)
    _cfg_file = os.path.join(_cfg_dir, "config.json")
    _saved_key = ""
    try:
        if os.path.exists(_cfg_file):
            with open(_cfg_file) as f:
                _saved_key = json.load(f).get("minimax_api_key", "")
    except: pass

    api_key_field = ft.TextField(
        value=_saved_key,
        hint_text="输入 MiniMax API Key（sk-...）",
        password=True, can_reveal_password=True,
        width=320, bgcolor=BG_SURFACE, color=TEXT_PRIMARY,
        border_color=BORDER, border_radius=6, text_size=12,
        content_padding=ft.Padding(left=12, right=12, top=8, bottom=8),
        hint_style=ft.TextStyle(color="#62666D"),
    )
    api_saved_hint = ft.Text("已保存" if _saved_key else "未配置", size=11, color=GREEN if _saved_key else RED)

    def save_api_key(e):
        cfg = {}
        if os.path.exists(_cfg_file):
            try:
                with open(_cfg_file) as f:
                    cfg = json.load(f)
            except: pass
        cfg["minimax_api_key"] = api_key_field.value
        with open(_cfg_file, "w") as f:
            json.dump(cfg, f)
        api_saved_hint.value = "已保存 ✓"
        api_saved_hint.color = GREEN
        safe_update()

    # 保存路径
    img_out_dir = [os.path.join(os.path.expanduser("~"), "Desktop", "AI生图")]  # list for closure
    try:
        if os.path.exists(_cfg_file):
            with open(_cfg_file) as f:
                saved = json.load(f).get("img_save_path", "")
                if saved and os.path.isdir(saved):
                    img_out_dir[0] = saved
    except: pass

    img_path_field = ft.TextField(
        value=img_out_dir[0],
        width=300, bgcolor=BG_SURFACE, color=TEXT_PRIMARY,
        border_color=BORDER, border_radius=6, text_size=12,
        content_padding=ft.Padding(left=12, right=12, top=8, bottom=8),
    )

    def pick_img_dir_result(e: ft.FilePickerResultEvent):
        if e.path:
            img_out_dir[0] = e.path
            img_path_field.value = e.path
            # persist
            cfg = {}
            if os.path.exists(_cfg_file):
                try:
                    with open(_cfg_file) as f:
                        cfg = json.load(f)
                except: pass
            cfg["img_save_path"] = e.path
            with open(_cfg_file, "w") as f:
                json.dump(cfg, f)
            safe_update()

    img_dir_picker = ft.FilePicker()
    img_dir_picker.on_result = pick_img_dir_result
    page.overlay.append(img_dir_picker)

    # 图片放大预览
    def show_full_image(path):
        dlg = ft.AlertDialog(
            content=ft.Container(
                content=ft.Image(src=path, fit="contain"),
                width=700, height=500,
            ),
            actions=[ft.TextButton("关闭", on_click=lambda e: close_dlg(dlg))],
        )
        page.dialog = dlg
        dlg.open = True
        safe_update()

    def close_dlg(dlg):
        dlg.open = False
        safe_update()

    # 提示词优化
    optimized_prompt = [""]  # list for closure
    prompt_compare = ft.Column(visible=False, spacing=8)
    optimized_text = ft.Text("", size=12, color=TEXT_PRIMARY, selectable=True)
    use_optimized = [False]

    # 优化结果占位文本（与输入框同高：12行）
    opt_result_text = ft.TextField(
        value="",
        hint_text="点击下方[AI优化]按钮优化提示词",
        multiline=True, min_lines=6, max_lines=6,
        bgcolor=BG_SURFACE, color=TEXT_PRIMARY,
        border_color=BORDER, border_radius=8,
        text_size=13, content_padding=ft.Padding(left=12, top=12, right=12, bottom=12),
        hint_style=ft.TextStyle(color="#62666D"),
    )

    def optimize_prompt(e):
        original = img_prompt.value.strip()
        if not original:
            page.snack_bar = ft.SnackBar(ft.Text("请先输入提示词")); page.snack_bar.open = True; safe_update(); return
        api_key = api_key_field.value.strip() or _saved_key
        if not api_key:
            page.snack_bar = ft.SnackBar(ft.Text("请先配置 API Key")); page.snack_bar.open = True; safe_update(); return

        img_status.value = "🤖 AI 优化提示词中..."
        img_status.color = ACCENT
        safe_update()

        def worker():
            try:
                import ssl as _ssl
                import urllib.request
                _ctx = _ssl._create_unverified_context()
                body = json.dumps({
                    "model": "MiniMax-M2.7",
                    "messages": [{"role": "user", "content": f"你是图片提示词优化专家。请将以下提示词优化得更详细、更专业，用于AI生图。添加光线、构图、风格细节。必须用中文输出优化结果，不要英文。只输出优化后的提示词，不要解释。\n\n原文：{original}"}],
                    "temperature": 0.7, "max_tokens": 1024,
                })
                req = urllib.request.Request("https://api.minimax.chat/v1/text/chatcompletion_v2",
                    data=body.encode(), headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, method="POST")
                resp = urllib.request.urlopen(req, timeout=60, context=_ctx)
                data = json.loads(resp.read().decode())
                opt = data["choices"][0]["message"]["content"].strip()
                optimized_prompt[0] = opt
                opt_result_text.value = opt
                use_optimized[0] = True
                select_optimized(None)
                img_status.value = "✅ 优化完成 — 选择版本后点击生成"
                img_status.color = GREEN
            except Exception as ex:
                img_status.value = f"✕ 优化失败: {str(ex)[:50]}"
                img_status.color = RED
            finally:
                safe_update()

        threading.Thread(target=worker).start()

    def select_original(e):
        use_optimized[0] = False
        btn_original.bgcolor = ACCENT
        btn_original.color = "white"
        btn_optimized.bgcolor = BG_SURFACE
        btn_optimized.color = None
        img_status.value = "已选：原始版本"
        safe_update()

    def select_optimized(e):
        use_optimized[0] = True
        btn_optimized.bgcolor = GREEN
        btn_optimized.color = "white"
        btn_original.bgcolor = BG_SURFACE
        btn_original.color = None
        img_status.value = "已选：优化版本"
        safe_update()

    # 按钮引用，用于高亮切换
    btn_original = ft.ElevatedButton("用原始", on_click=select_original, height=34, bgcolor=ACCENT, color="white")
    btn_optimized = ft.ElevatedButton("用优化", on_click=select_optimized, height=34, bgcolor=BG_SURFACE)

    # 对比面板（左右布局）
    prompt_original_text = ft.Text("", size=12, color=TEXT_MUTED, italic=True)
    prompt_compare.controls = [
        ft.Divider(height=1, color=BORDER),
        ft.Row([
            # 左：原始
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Container(width=3, height=14, bgcolor=ACCENT, border_radius=2),
                        ft.Text("原始", size=12, weight="bold", color=ACCENT),
                    ], spacing=6),
                    ft.Container(
                        content=prompt_original_text,
                        bgcolor=BG_SURFACE, border_radius=8, padding=12,
                        expand=True,
                    ),
                    ft.ElevatedButton("用原始 →", on_click=select_original, height=30, bgcolor=ACCENT, color="white"),
                ], spacing=8),
                bgcolor=BG_PANEL, border_radius=10, padding=12,
                expand=True,
            ),
            ft.Container(width=1, bgcolor=BORDER),
            # 右：优化
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Container(width=3, height=14, bgcolor=GREEN, border_radius=2),
                        ft.Text("AI 优化", size=12, weight="bold", color=GREEN),
                    ], spacing=6),
                    ft.Container(
                        content=optimized_text,
                        bgcolor=BG_SURFACE, border_radius=8, padding=12,
                        expand=True,
                    ),
                    ft.ElevatedButton("用优化 →", on_click=select_optimized, height=30, bgcolor=GREEN, color="white"),
                ], spacing=8),
                bgcolor=BG_PANEL, border_radius=10, padding=12,
                expand=True,
            ),
        ], spacing=12, expand=True),
    ]

    def generate_image(e):
        original = img_prompt.value.strip()
        prompt = opt_result_text.value.strip() if use_optimized[0] and opt_result_text.value.strip() else original
        if not prompt:
            page.snack_bar = ft.SnackBar(ft.Text("请输入图片描述")); page.snack_bar.open = True; safe_update(); return
        api_key = api_key_field.value.strip() or _saved_key
        if not api_key:
            page.snack_bar = ft.SnackBar(ft.Text("请先配置 MiniMax API Key")); page.snack_bar.open = True; safe_update(); return
        if img_generating[0]: return
        img_generating[0] = True
        img_grid.controls.clear()
        img_status.value = "🎨 生成中..."
        img_status.color = ACCENT
        safe_update()

        def worker():
            try:
                import ssl as _ssl
                import urllib.request
                _ctx = _ssl._create_unverified_context()

                body = json.dumps({
                    "model": "image-01", "prompt": prompt,
                    "aspect_ratio": img_ratio.value, "n": int(img_count.value),
                    "prompt_optimizer": img_optimize.value,
                })
                req = urllib.request.Request("https://api.minimax.chat/v1/image_generation",
                    data=body.encode(), headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, method="POST")
                resp = urllib.request.urlopen(req, timeout=300, context=_ctx)
                data = json.loads(resp.read().decode())

                out_dir = img_out_dir[0]
                os.makedirs(out_dir, exist_ok=True)
                urls = data.get("data", {}).get("image_urls", [])
                for i, url in enumerate(urls):
                    local = os.path.join(out_dir, f"ai_{int(time.time())}_{i}.png")
                    urllib.request.urlretrieve(url, local)
                    img_grid.controls.append(
                        ft.GestureDetector(
                            on_tap=lambda e, p=local: show_full_image(p),
                            content=ft.Container(
                                content=ft.Image(src=local, width=180, height=240, fit="contain", border_radius=8),
                                bgcolor=BG_SURFACE, border_radius=10, padding=6,
                                border=_bd(),
                            )
                        )
                    )
                    safe_update()
                img_status.value = f"✅ {len(urls)}张 → {img_out_dir[0]}"
                img_status.color = GREEN
            except Exception as ex:
                img_status.value = f"✕ {str(ex)[:50]}"
                img_status.color = RED
            finally:
                img_generating[0] = False
                safe_update()

        threading.Thread(target=worker).start()

    tab4 = ft.Column([
        ft.Text("AI 生图", size=18, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
        ft.Text("MiniMax image-01 · 输入描述自动生成投流素材", size=13, color=TEXT_MUTED),
        ft.Divider(height=1, color=BORDER),
        # API Key + 保存路径（同一行）
        ft.Container(
            content=ft.Row([
                ft.Text("🔑 Key:", size=12, color=TEXT_MUTED),
                api_key_field,
                ft.ElevatedButton("保存", icon=ft.Icons.SAVE, on_click=save_api_key, height=34),
                api_saved_hint,
                ft.Text("📁 保存到:", size=12, color=TEXT_MUTED),
                img_path_field,
                ft.ElevatedButton("选择", icon=ft.Icons.FOLDER_OPEN,
                    on_click=lambda e: img_dir_picker.get_directory_path(), height=34),
            ], spacing=6, wrap=True),
            bgcolor=BG_PANEL, border_radius=8, padding=10,
        ),
        # 左右分栏：原始 | 优化
        ft.Row([
            # 左栏：原始输入
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Container(width=3, height=14, bgcolor=ACCENT, border_radius=2),
                        ft.Text("✏️ 你的提示词", size=13, weight="bold", color=ACCENT),
                    ], spacing=6),
                    img_prompt,
                ], spacing=8),
                bgcolor=BG_PANEL, border_radius=10, padding=12,
                expand=True,
            ),
            ft.Container(width=1, bgcolor=BORDER),
            # 右栏：AI优化
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Container(width=3, height=14, bgcolor=GREEN, border_radius=2),
                        ft.Text("🤖 AI 优化结果", size=13, weight="bold", color=GREEN),
                    ], spacing=6),
                    opt_result_text,
                ], spacing=8),
                bgcolor=BG_PANEL, border_radius=10, padding=12,
                expand=True,
            ),
        ], spacing=12),
        # 统一工具栏
        ft.Container(
            content=ft.Row([
                ft.ElevatedButton("🤖 AI优化", icon=ft.Icons.AUTO_AWESOME, on_click=optimize_prompt, height=34),
                btn_original,
                btn_optimized,
                ft.Container(width=1, height=24, bgcolor=BORDER),
                ft.Text("比例:", size=13, color=TEXT_MUTED), img_ratio,
                ft.Text("张数:", size=13, color=TEXT_MUTED), img_count,
                ft.Text("优化:", size=13, color=TEXT_MUTED), img_optimize,
                ft.Container(expand=True),
                ft.ElevatedButton("🎨 生成图片", icon=ft.Icons.AUTO_AWESOME, bgcolor=ACCENT, color="white", on_click=generate_image, height=38),
            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=BG_PANEL, border_radius=10, padding=ft.Padding(left=14, top=10, right=14, bottom=10),
        ),
        img_status,
        ft.Container(content=img_grid, expand=True, border_radius=8),
    ], spacing=8, expand=True)

    # ═══════════════════════════════════════════════
    # 左侧导航栏（替代 Tabs）
    # ═══════════════════════════════════════════════

    content_area = ft.Container(tab1, padding=20, expand=True)

    def on_nav_change(e):
        idx = e.control.selected_index
        content_area.content = [tab1, tab2, tab3, tab4][idx]
        safe_update()

    nav = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        on_change=on_nav_change,
        bgcolor=BG_PANEL,
        indicator_color=ACCENT,
        min_width=100,
        leading=ft.Container(height=12),
        destinations=[
            ft.NavigationRailDestination(icon=ft.Icons.VIDEO_FILE, label="视频去重"),
            ft.NavigationRailDestination(icon=ft.Icons.DOWNLOAD, label="视频下载"),
            ft.NavigationRailDestination(icon=ft.Icons.TRANSCRIBE, label="文案提取"),
            ft.NavigationRailDestination(icon=ft.Icons.AUTO_AWESOME, label="AI生图"),
        ],
    )

    page.add(
        ft.Row([
            nav,
            ft.VerticalDivider(width=1, color=BORDER),
            ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Row([
                            ft.Container(width=6, height=6, bgcolor=ACCENT, border_radius=3),
                            ft.Text("电商工具箱", size=14, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
                            ft.Container(expand=True),
                            ft.Container(
                                content=ft.Text("v3.2", size=11, color=TEXT_MUTED),
                                bgcolor=BG_SURFACE, border_radius=6,
                                padding=ft.Padding(left=8, top=3, right=8, bottom=3),
                            ),
                        ]),
                        padding=ft.Padding(left=16, top=10, right=16, bottom=10),
                        bgcolor="#08090A",
                    ),
                    content_area,
                ]),
                expand=True,
            ),
        ], expand=True)
    )


if __name__ == "__main__":
    ft.app(target=main)
