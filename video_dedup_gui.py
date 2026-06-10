"""
千川视频批量去重 v2.1 — 拖拽/表格/进度/导出
"""
import os, sys, random, subprocess, json, threading, re, time
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# === FFmpeg 路径 ===
if getattr(sys, 'frozen', False):
    FFMPEG = os.path.join(sys._MEIPASS, "ffmpeg.exe")
else:
    FFMPEG = "ffmpeg"

# === FFmpeg 安全调用（带超时） ===
def run_ffmpeg(cmd, timeout=120):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"FFmpeg错误: {r.stderr.strip()[-100:]}")

# === 6项去重操作 ===
def op_speed(inp, out, cb):
    factor = round(random.uniform(0.96, 1.04), 2)
    cb(f"变速 ×{factor}")
    run_ffmpeg([FFMPEG,"-y","-i",inp,"-filter_complex",f"[0:v]setpts={1/factor}*PTS[v];[0:a]atempo={factor}[a]","-map","[v]","-map","[a]","-c:v","libx264","-preset","ultrafast","-crf","23","-c:a","aac","-b:a","128k",out])

def op_color(inp, out, cb):
    b, c, s = round(random.uniform(-0.05,0.05),2), round(random.uniform(0.95,1.05),2), round(random.uniform(0.95,1.05),2)
    cb(f"色彩 b{b} c{c} s{s}")
    run_ffmpeg([FFMPEG,"-y","-i",inp,"-vf",f"eq=brightness={b}:contrast={c}:saturation={s}","-c:v","libx264","-preset","ultrafast","-crf","23","-c:a","copy",out])

def op_scale(inp, out, cb):
    cb("微缩放 99%")
    run_ffmpeg([FFMPEG,"-y","-i",inp,"-vf","scale=iw*0.99:ih*0.99,scale=iw:ih:flags=lanczos","-c:v","libx264","-preset","ultrafast","-crf","23","-c:a","copy",out])

def op_audio(inp, out, cb):
    pitch = round(random.uniform(0.98,1.02),2)
    cb(f"音频变调 ×{pitch}")
    run_ffmpeg([FFMPEG,"-y","-i",inp,"-af",f"asetrate=44100*{pitch},aresample=44100","-c:v","libx264","-preset","ultrafast","-crf","23","-c:a","aac","-b:a","128k",out])

def op_crop(inp, out, cb):
    probe = subprocess.run([FFMPEG,"-i",inp], capture_output=True, text=True)
    m = re.search(r'(\d+)x(\d+)', probe.stderr)
    if m:
        w, h = int(m.group(1)), int(m.group(2))
        cw, ch = random.randint(1,4), random.randint(1,4)
        cb(f"边缘微裁 {cw}px")
        run_ffmpeg([FFMPEG,"-y","-i",inp,"-vf",f"crop={w-cw*2}:{h-ch*2}:{cw}:{ch},scale={w}:{h}","-c:v","libx264","-preset","ultrafast","-crf","23","-c:a","copy",out])
    else:
        import shutil; shutil.copy2(inp, out)

def op_black(inp, out, cb):
    cb("首尾黑帧")
    run_ffmpeg([FFMPEG,"-y","-f","lavfi","-i","color=black:s=1080x1920:d=0.05,r=24","-i",inp,"-f","lavfi","-i","color=black:s=1080x1920:d=0.05,r=24","-filter_complex","[0:v][1:v][1:a][2:v]concat=n=3:v=1:a=1[outv][outa]","-map","[outv]","-map","[outa]","-c:v","libx264","-preset","ultrafast","-crf","23","-c:a","aac","-b:a","128k","-shortest",out])

OPERATIONS = [
    ("变速", op_speed),
    ("色彩微调", op_color),
    ("微缩放", op_scale),
    ("音频变调", op_audio),
    ("边缘微裁", op_crop),
    ("首尾黑帧", op_black),
]

INTENSITY_MAP = {"轻度": 2, "标准": 4, "重度": 6}

# === 批量处理引擎 ===
def process_one(video_path, output_dir, intensity, progress_cb):
    name = Path(video_path).stem
    ext = Path(video_path).suffix or ".mp4"
    n = min(INTENSITY_MAP[intensity], len(OPERATIONS))
    ops = random.sample(OPERATIONS, n)
    
    tmp = video_path
    tmp_files = []
    ops_used = []
    
    for i, (op_name, op_func) in enumerate(ops):
        progress_cb(f"{op_name} ({i+1}/{n})")
        tmp_out = os.path.join(output_dir, f"_tmp_{name}_{i}{ext}")
        try:
            op_func(tmp, tmp_out, lambda msg: progress_cb(f"{op_name} {msg}"))
            tmp_files.append(tmp_out)
            tmp = tmp_out
            ops_used.append(op_name)
        except Exception as e:
            progress_cb(f"❌ {op_name}: {str(e)[:50]}")
            ops_used.append(f"⚠{op_name}")
    
    final = os.path.join(output_dir, f"{name}_去重{ext}")
    if tmp != video_path:
        os.replace(tmp, final)
    for tf in tmp_files:
        if os.path.exists(tf) and tf != final:
            os.remove(tf)
    
    return {"status": "done", "ops": ops_used}

# === GUI ===
class DedupApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("千川视频批量去重 v2.1")
        self.root.geometry("820x620")
        self.root.minsize(700, 500)
        
        self.output_dir = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Desktop", "去重输出"))
        self.intensity = tk.StringVar(value="标准")
        self.running = False
        self.files = []          # [(path, name, dur, size)]
        self.file_items = {}     # path → tree item ID
        self.completed = 0
        self.times = []          # processing times
        
        self.build_ui()
    
    def build_ui(self):
        # === 顶部: 拖拽区域 ===
        drop_frame = ttk.LabelFrame(self.root, text="视频来源", padding=5)
        drop_frame.pack(fill="x", padx=10, pady=(10,5))
        
        btn_bar = ttk.Frame(drop_frame)
        btn_bar.pack(fill="x", pady=5)
        ttk.Button(btn_bar, text="➕ 添加文件", command=self.add_files).pack(side="left", padx=3)
        ttk.Button(btn_bar, text="📂 添加文件夹", command=self.add_folder).pack(side="left", padx=3)
        ttk.Button(btn_bar, text="✕ 清空列表", command=self.clear_files).pack(side="left", padx=3)
        self.count_label = ttk.Label(btn_bar, text="未添加视频")
        self.count_label.pack(side="right", padx=5)
        
        # === 中间: 文件列表表格 ===
        list_frame = ttk.LabelFrame(self.root, text="文件列表", padding=5)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        columns = ("name", "dur", "size", "status", "ops")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=12)
        self.tree.heading("name", text="文件名")
        self.tree.heading("dur", text="时长")
        self.tree.heading("size", text="大小")
        self.tree.heading("status", text="状态")
        self.tree.heading("ops", text="操作明细")
        self.tree.column("name", width=220)
        self.tree.column("dur", width=60, anchor="center")
        self.tree.column("size", width=70, anchor="center")
        self.tree.column("status", width=80, anchor="center")
        self.tree.column("ops", width=280)
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # === 底部控制区（固定，始终可见）===
        bottom = ttk.Frame(self.root, padding=10)
        bottom.pack(side="bottom", fill="x")
        
        # 输出+强度
        ctrl = ttk.Frame(bottom)
        ctrl.pack(fill="x", pady=3)
        ttk.Label(ctrl, text="输出:").pack(side="left")
        ttk.Entry(ctrl, textvariable=self.output_dir, width=40).pack(side="left", padx=5)
        ttk.Button(ctrl, text="选择", command=self.select_output).pack(side="left")
        ttk.Separator(ctrl, orient="vertical").pack(side="left", padx=10, fill="y")
        ttk.Label(ctrl, text="强度:").pack(side="left")
        for v in ["轻度","标准","重度"]:
            ttk.Radiobutton(ctrl, text=v, variable=self.intensity, value=v).pack(side="left", padx=3)
        
        # 进度条
        prog = ttk.Frame(bottom)
        prog.pack(fill="x", pady=5)
        self.progress_bar = ttk.Progressbar(prog, mode="determinate")
        self.progress_bar.pack(side="left", fill="x", expand=True)
        self.progress_label = ttk.Label(prog, text="就绪", width=20, anchor="e")
        self.progress_label.pack(side="right", padx=5)
        
        # 按钮
        btn_row = ttk.Frame(bottom)
        btn_row.pack(fill="x")
        self.start_btn = ttk.Button(btn_row, text="▶ 开始处理", command=self.start_processing)
        self.start_btn.pack(side="left", padx=3)
        self.stop_btn = ttk.Button(btn_row, text="■ 停止", command=self.stop_processing, state="disabled")
        self.stop_btn.pack(side="left", padx=3)
        self.export_btn = ttk.Button(btn_row, text="📊 导出报告", command=self.export_report)
        self.export_btn.pack(side="left", padx=3)
    
    def add_files(self):
        paths = filedialog.askopenfilenames(
            title="选择视频文件",
            filetypes=[("视频文件","*.mp4 *.MP4 *.mov *.MOV *.avi *.AVI *.mkv *.MKV")]
        )
        for p in paths:
            self._add_file(p)
    
    def add_folder(self):
        d = filedialog.askdirectory(title="选择视频文件夹")
        if not d:
            return
        exts = {'.mp4','.MP4','.mov','.MOV','.avi','.AVI','.mkv','.MKV'}
        for p in sorted(Path(d).iterdir()):
            if p.suffix in exts:
                self._add_file(str(p))
    
    def _add_file(self, path):
        if path in self.file_items:
            return
        name = Path(path).name
        dur = self._get_dur(path)
        size = f"{Path(path).stat().st_size/1024/1024:.1f}MB"
        item = self.tree.insert("", "end", values=(name, dur, size, "⏳ 等待", ""))
        self.file_items[path] = item
        self.files.append(path)
        self.count_label.config(text=f"已添加 {len(self.files)} 个视频")
    
    def clear_files(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.files.clear()
        self.file_items.clear()
        self.count_label.config(text="未添加视频")
        self.progress_bar["value"] = 0
        self.progress_bar["maximum"] = 1
        self.progress_label.config(text="就绪")
    
    def select_output(self):
        d = filedialog.askdirectory(title="选择输出文件夹")
        if d:
            self.output_dir.set(d)
    
    def _get_dur(self, path):
        try:
            r = subprocess.run([FFMPEG,"-i",path], capture_output=True, text=True, timeout=5)
            m = re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)', r.stderr)
            if m:
                return f"{int(m.group(1))*3600+int(m.group(2))*60+float(m.group(3)):.1f}s"
        except:
            pass
        return "?"
    
    def update_status(self, path, status, ops=""):
        if path in self.file_items:
            item = self.file_items[path]
            # Update the tree row - get current values, modify status and ops
            vals = list(self.tree.item(item, "values"))
            vals[3] = status
            vals[4] = ops
            self.tree.item(item, values=tuple(vals))
    
    def process_queue(self):
        if not self.running or self.current_idx >= len(self.files):
            self.finish()
            return
        
        path = self.files[self.current_idx]
        outdir = self.output_dir.get()
        os.makedirs(outdir, exist_ok=True)
        
        self.update_status(path, "🔄 准备中", "")
        start_time = time.time()
        last_op = [""]
        
        def cb(msg):
            last_op[0] = msg
            self.root.after(0, lambda: self.update_status(path, "🔄 处理中", msg))
        
        def done_wrapper():
            elapsed = time.time() - start_time
            self.times.append(elapsed)
            return process_one(path, outdir, self.intensity.get(), cb)
        
        t = threading.Thread(target=lambda: self._handle_result(path, done_wrapper()))
        t.daemon = True
        t.start()
    
    def _handle_result(self, path, result):
        self.root.after(0, lambda: self._on_result(path, result))
    
    def _on_result(self, path, result):
        ops = result["ops"]
        if result["status"] == "done":
            self.update_status(path, "✅ 完成", ", ".join(ops))
        self.completed += 1
        self.current_idx += 1
        self.progress_bar["value"] = self.completed
        
        # Estimate remaining
        if self.times:
            avg = sum(self.times) / len(self.times)
            remaining = int(avg * (len(self.files) - self.completed))
            mins, secs = divmod(remaining, 60)
            self.progress_label.config(text=f"已完成 {self.completed}/{len(self.files)}  剩余约 {mins}分{secs}秒")
        
        self.process_queue()
    
    def start_processing(self):
        if not self.files:
            messagebox.showwarning("提示", "请先添加视频文件")
            return
        
        self.running = True
        self.completed = 0
        self.current_idx = 0
        self.times.clear()
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.progress_bar["maximum"] = len(self.files)
        self.progress_bar["value"] = 0
        self.progress_label.config(text="处理中...")
        self.process_queue()
    
    def stop_processing(self):
        self.running = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.progress_label.config(text="已停止")
    
    def finish(self):
        self.running = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.progress_bar["value"] = len(self.files)
        self.progress_label.config(text=f"✅ 完成 {len(self.files)} 条")
        # Auto export
        self.export_report(silent=True)
    
    def export_report(self, silent=False):
        outdir = self.output_dir.get()
        report = []
        for path in self.files:
            name = Path(path).name
            if path in self.file_items:
                vals = self.tree.item(self.file_items[path], "values")
                report.append({
                    "file": name,
                    "duration": vals[1],
                    "size": vals[2],
                    "status": vals[3],
                    "operations": vals[4].split(", ") if vals[4] else []
                })
        
        path = os.path.join(outdir, "去重报告.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        if not silent:
            messagebox.showinfo("导出完成", f"报告已保存:\n{path}")
    
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    DedupApp().run()
