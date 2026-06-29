"""视频去重插件"""

import os
import random
import threading
from pathlib import Path
import flet as ft

from core.base_plugin import BasePlugin
from config.theme import *
from ui.components import (
    section_header, empty_state, progress_bar, status_text,
    primary_btn, secondary_btn, divider_y, spacer, status_footer,
)
from engine import ffmpeg_ops
from config.app_config import config as app_config

class DedupPlugin(BasePlugin):
    name = "视频去重"
    icon = "📹"
    description = "FFmpeg 批量处理"
    version = "4.0"

    def __init__(self, page):
        super().__init__(page)
        self._fp_files = ft.FilePicker()
        self._fp_folder = ft.FilePicker()
        self._fp_output = ft.FilePicker()
        self.page.services.append(self._fp_files)
        self.page.services.append(self._fp_folder)
        self.page.services.append(self._fp_output)
        self.files = []
        self.running = False
        self._stop_event = threading.Event()
        # 从配置中心读取持久化偏好
        self.mode = app_config.get("dedup.mode", "自动")
        self.intensity = app_config.get("dedup.intensity", "标准")
        self.output_dir = app_config.get("output.dedup", str(Path.home() / "Desktop" / "去重输出"))
        self._op_selected = app_config.get("dedup.selected_ops", [True] * 7)
        self._op_selected[0] = True  # 抽帧始终选中
        os.makedirs(self.output_dir, exist_ok=True)

        # 表格
        VD = lambda: ft.VerticalDivider(width=1, color=BORDER_SUBTLE)
        self._file_header = ft.Row([
            ft.Text("文件", size=12, color=TEXT_MUTED, expand=4), VD(),
            ft.Text("时长", size=12, color=TEXT_MUTED, expand=2), VD(),
            ft.Text("大小", size=12, color=TEXT_MUTED, expand=2), VD(),
            ft.Text("状态", size=12, color=TEXT_MUTED, expand=2), VD(),
            ft.Text("操作", size=12, color=TEXT_MUTED, expand=1, text_align=ft.TextAlign.RIGHT),
        ])
        self._file_rows = ft.Column([], spacing=0)
        self._row_statuses = []  # 每行状态 Text 引用
        self._dur_widgets = []   # 每行时长 Text 引用（异步更新）
        self._dur_cancel = threading.Event()  # 时长加载取消事件
        self._empty_hint = empty_state(
            ft.Icons.VIDEO_LIBRARY_OUTLINED,
            "未添加视频",
            "点击上方 添加视频 或 添加文件夹 导入素材",
            on_action=self._pick_files,
            action_text="添加视频",
        )
        self._table_body = ft.Column([self._file_rows], expand=True, spacing=0)
        self._file_table = ft.Column([
            ft.Container(self._file_header, bgcolor=CARD,
                         padding=P(12, 8, 12, 8),
                         border_radius=ft.BorderRadius(6, 6, 0, 0)),
            ft.Divider(height=1, color=BORDER_SUBTLE),
            ft.Container(self._table_body, bgcolor=CARD,
                         padding=P(12, 4, 12, 4), expand=True),
        ], expand=True, spacing=0)

        self._progress = progress_bar()
        self._status = status_text()

        # 模式按钮（根据配置初始化样式）
        is_auto = self.mode == "自动"
        self._mode_btn_auto = ft.Button(
            "自动", on_click=self._set_mode_auto,
            style=ft.ButtonStyle(
                bgcolor=ACCENT if is_auto else CARD,
                color="white" if is_auto else TEXT,
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=P(10, 4, 10, 4),
            ),
        )
        self._mode_btn_manual = ft.Button(
            "手动", on_click=self._set_mode_manual,
            style=ft.ButtonStyle(
                bgcolor=ACCENT if not is_auto else CARD,
                color="white" if not is_auto else TEXT,
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=P(10, 4, 10, 4),
            ),
        )

        # 强度
        self._intensity_dd = ft.Dropdown(
            value=self.intensity,
            options=[
                ft.dropdown.Option("标准", "标准 — 5 项"),
                ft.dropdown.Option("重度", "重度 — 7 项"),
            ],
            width=170, bgcolor=CARD, color=TEXT, border_color=BORDER,
            border_radius=6, text_size=13,
        )
        self._intensity_dd.on_change = lambda e: (
            setattr(self, "intensity", e.control.value),
            app_config.set("dedup.intensity", e.control.value)
        )

    def on_deactivate(self):
        """切后台时停止去重任务 + 时长加载"""
        self._stop_event.set()
        self._dur_cancel.set()
        self.running = False

    def _set_mode_auto(self, e):
        self.mode = "自动"
        app_config.set("dedup.mode", "自动")
        s = ft.ButtonStyle(bgcolor=ACCENT, color="white", shape=ft.RoundedRectangleBorder(radius=6), padding=P(10,4,10,4))
        self._mode_btn_auto.style = s; self._mode_btn_auto.update()
        s2 = ft.ButtonStyle(bgcolor=CARD, color=TEXT, shape=ft.RoundedRectangleBorder(radius=6), padding=P(10,4,10,4))
        self._mode_btn_manual.style = s2; self._mode_btn_manual.update()

    def _set_mode_manual(self, e):
        self.mode = "手动"
        app_config.set("dedup.mode", "手动")
        s = ft.ButtonStyle(bgcolor=ACCENT, color="white", shape=ft.RoundedRectangleBorder(radius=6), padding=P(10,4,10,4))
        self._mode_btn_manual.style = s; self._mode_btn_manual.update()
        s2 = ft.ButtonStyle(bgcolor=CARD, color=TEXT, shape=ft.RoundedRectangleBorder(radius=6), padding=P(10,4,10,4))
        self._mode_btn_auto.style = s2; self._mode_btn_auto.update()

    def _toggle_op(self, i):
        """点击卡片切换选中（抽帧不可取消）"""
        if i == 0: return
        self._op_selected[i] = not self._op_selected[i]
        app_config.set("dedup.selected_ops", self._op_selected)
        card = self._op_cards[i]
        sel = self._op_selected[i]
        card.bgcolor = ACCENT_10 if sel else CARD
        card.content.controls[0].color = ACCENT if sel else TEXT_PRIMARY
        card.content.controls[1].color = ACCENT if sel else TEXT_MUTED
        card.update()

    def _build_mask(self):
        if self.mode == "手动":
            return list(self._op_selected)
        else:
            n = ffmpeg_ops.INTENSITY_MAP[self.intensity]
            mask = [True] + [True] * n + [False] * (6 - n)
            random.shuffle(mask[1:])
            return mask

    def _add_files(self, paths):
        for p in paths:
            if p not in self.files:
                self.files.append(p)
        self._refresh_table()

    def _refresh_table(self):
        VD = lambda: ft.VerticalDivider(width=1, color=BORDER_SUBTLE)
        if not self.files:
            self._table_body.controls = [self._empty_hint]
        else:
            rows = []
            self._row_statuses = []
            self._dur_widgets = []
            for i, f in enumerate(self.files):
                fp = Path(f)
                st = ft.Text("等待", size=12, color=TEXT_MUTED, expand=2)
                dur_text = ft.Text("计算中", size=12, color=TEXT_MUTED, expand=2)
                self._row_statuses.append(st)
                self._dur_widgets.append(dur_text)
                rows.append(ft.Row([
                    ft.Text(fp.name, size=12, color=TEXT, expand=4, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS), VD(),
                    dur_text, VD(),
                    ft.Text(self._fmt_size(fp), size=12, color=TEXT_MUTED, expand=2), VD(),
                    st, VD(),
                    ft.Row([
                        ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_size=16,
                                      icon_color=TEXT_MUTED, data=i,
                                      on_click=self._remove_file),
                    ], expand=1, alignment=ft.MainAxisAlignment.END),
                ]))
            self._table_body.controls = [self._file_rows]
            self._file_rows.controls = rows
        self._table_body.update()
        # 取消旧的时长加载，启动新的
        self._dur_cancel.set()
        self._dur_cancel.clear()
        if self.files:
            threading.Thread(target=self._load_durations, daemon=True).start()

    def _load_durations(self):
        """后台线程：异步加载视频时长，逐个更新 UI，可被取消"""
        for i, f in enumerate(self.files):
            if self._dur_cancel.is_set():
                break
            dur = self._fmt_dur_sync(Path(f))
            async def _update_dur(idx=i, d=dur):
                if idx < len(self._dur_widgets):
                    self._dur_widgets[idx].value = d
                    self._dur_widgets[idx].update()
            self.page.run_task(_update_dur)

    def _fmt_dur_sync(self, p: Path):
        """获取视频时长（同步，供后台线程调用）"""
        try:
            from engine.video_probe import get_video_info
            info = get_video_info(str(p))
            secs = info.get("duration", 0)
            if secs:
                m, s = divmod(int(secs), 60)
                h, m = divmod(m, 60)
                return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
        except Exception:
            pass
        return "—"

    def _remove_file(self, e):
        if self.running:
            return  # 运行中禁止删除
        i = e.control.data
        if 0 <= i < len(self.files):
            self.files.pop(i)
            self._refresh_table()

    def _fmt_size(self, p: Path):
        try:
            s = p.stat().st_size
            for u in ["B", "KB", "MB", "GB"]:
                if s < 1024: return f"{s:.1f} {u}"
                s /= 1024
            return f"{s:.1f} GB"
        except Exception: return "—"

    def _export_report(self, e):
        """导出 TXT 报告"""
        out = os.path.join(self.output_dir, "去重报告.txt")
        lines = ["视频去重报告", "=" * 40, ""]
        for f in self.files:
            lines.append(f"📹 {Path(f).name}")
            if hasattr(self, '_row_statuses'):
                idx = self.files.index(f) if f in self.files else -1
                if 0 <= idx < len(self._row_statuses):
                    lines.append(f"   状态: {self._row_statuses[idx].value}")
            lines.append("")
        with open(out, "w", encoding="utf-8") as fh:
            fh.write('\n'.join(lines))
        self._status.value = f"报告已保存: {out}"
        self._status.color = GREEN
        self._status.update()

    def _pick_files(self, e): self.page.run_task(self._do_pick_files)
    async def _do_pick_files(self):
        result = await self._fp_files.pick_files(allow_multiple=True, allowed_extensions=["mp4", "mov", "mkv", "avi"])
        if result: self._add_files([f.path for f in result])

    def _pick_folder(self, e): self.page.run_task(self._do_pick_folder)
    async def _do_pick_folder(self):
        path = await self._fp_folder.get_directory_path()
        if path:
            files = []
            for ext in ["*.mp4", "*.mov", "*.mkv", "*.avi"]:
                files.extend(Path(path).glob(ext)); files.extend(Path(path).glob(ext.upper()))
            self._add_files([str(f) for f in files])

    def _pick_output(self, e): self.page.run_task(self._do_pick_output)
    async def _do_pick_output(self):
        path = await self._fp_output.get_directory_path()
        if path:
            self.output_dir = path
            app_config.set("output.dedup", path)
            self._output_field.value = path
            self._output_field.update()

    def _run_dedup(self, e):
        self.page.run_task(self._do_run_dedup)

    async def _do_run_dedup(self):
        if not self.files or self.running: return
        self.running = True
        self._stop_event.clear()
        import asyncio
        self._status.value = f"处理中 0/{len(self.files)}"
        self._status.color = ACCENT
        self._progress.value = 0
        self._status.update(); self._progress.update()
        await asyncio.sleep(0.05)
        completed = 0
        loop = asyncio.get_event_loop()

        async def process_one_file(idx, f):
            if not self.running:
                return idx, {"status": "error", "ops": ["已停止"]}
            # 每个视频独立生成 mask（自动模式随机差异化）
            file_mask = self._build_mask()
            if idx < len(self._row_statuses):
                self._row_statuses[idx].value = "处理中"
                self._row_statuses[idx].color = ACCENT
                self._row_statuses[idx].update()
            # 在线程池中跑同步 ffmpeg
            try:
                result = await loop.run_in_executor(
                    None,
                    lambda: ffmpeg_ops.process_one(f, self.output_dir, file_mask, None, self._stop_event)
                )
            except Exception as ex:
                result = {"status": "error", "ops": [str(ex)[:30]]}
            return idx, result

        # 并发调度：asyncio.gather 一次提交所有任务，信号量控制实际并发数
        tasks = [process_one_file(i, f) for i, f in enumerate(self.files)]
        completed = 0
        for coro in asyncio.as_completed(tasks):
            if not self.running:
                break
            idx, result = await coro
            self._progress.value = (idx + 1) / len(self.files)
            self._progress.update()
            if result["status"] == "done":
                completed += 1
                if idx < len(self._row_statuses):
                    self._row_statuses[idx].value = "完成"
                    self._row_statuses[idx].color = GREEN
                    self._row_statuses[idx].update()
            else:
                err = result.get("ops", ["未知"])[0]
                if idx < len(self._row_statuses):
                    self._row_statuses[idx].value = f"失败: {err}"
                    self._row_statuses[idx].color = RED
                    self._row_statuses[idx].update()
        self.running = False
        self._status.value = f"完成 {completed}/{len(self.files)}"
        self._status.color = GREEN
        self._progress.value = 1
        self._status.update(); self._progress.update()

    def _update_status(self, msg, color=ACCENT):
        self._status.value = msg
        self._status.color = color
        self._status.update()

    def build(self) -> ft.Control:
        self._output_field = ft.TextField(
            value=self.output_dir, expand=True, bgcolor=CARD, color=TEXT,
            border_color=BORDER, border_radius=8, text_size=13,
            content_padding=P(14, 12, 14, 12),
        )
        self._output_field.on_change = lambda e: (
            setattr(self, "output_dir", e.control.value),
            app_config.set("output.dedup", e.control.value)
        )

        # 7 张可点击操作卡片
        self._op_cards = []
        op_row_controls = []
        for i in range(7):
            sel = self._op_selected[i]
            card = ft.Container(
                ft.Column([
                    ft.Text(ffmpeg_ops.OPS[i][0], size=18,
                            color=ACCENT if sel else TEXT_PRIMARY),
                    ft.Text(ffmpeg_ops.OPS[i][1], size=11,
                            color=ACCENT if sel else TEXT_MUTED),
                ], spacing=4, alignment=ft.MainAxisAlignment.CENTER,
                   horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                width=92, height=56, padding=P(10, 8, 10, 8), border_radius=8,
                bgcolor=ACCENT_10 if sel else CARD,
                border=bd(),
                on_click=lambda e, idx=i: self._toggle_op(idx),
            )
            self._op_cards.append(card)
            op_row_controls.append(card)

        return ft.Container(ft.Column([
            section_header("视频去重", "7 种 FFmpeg 操作 · 抽帧必选",
                           show_actions=ft.Row([
                               self._mode_btn_auto, self._mode_btn_manual,
                               ft.Container(width=8), self._intensity_dd,
                           ], spacing=0)),
            divider_y(20),
            ft.Row(op_row_controls, spacing=8, wrap=True),
            divider_y(16),
            ft.Row([
                primary_btn("添加视频", ft.Icons.VIDEO_FILE, self._pick_files),
                secondary_btn("添加文件夹", ft.Icons.FOLDER_OPEN, self._pick_folder),
                secondary_btn("清空", ft.Icons.DELETE_OUTLINE,
                              lambda e: (None if self.running else (setattr(self, "files", []), self._refresh_table()))),
                spacer(),
                ft.Text("保存至", size=12, color=TEXT_MUTED),
                ft.Container(self._output_field, width=300),
                secondary_btn("选择", ft.Icons.FOLDER_OUTLINED, self._pick_output),
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            divider_y(12),
            ft.Container(self._file_table, expand=True, border_radius=8,
                         border=bd(), bgcolor=CARD),
            divider_y(12),
            status_footer(self._status, self._progress, [
                secondary_btn("导出报告", ft.Icons.FILE_DOWNLOAD, self._export_report),
                primary_btn("开始去重", ft.Icons.PLAY_ARROW, self._run_dedup),
                secondary_btn("停止", ft.Icons.STOP,
                              lambda e: (self._stop_event.set(), setattr(self, "running", False))),
            ]),
        ], spacing=0), padding=P(24, 20, 24, 20), expand=True, bgcolor=CONTENT)