"""无水印下载插件 — 线程安全：子线程写数据，主线程轮询刷新"""
import os
import threading
import re
import time
import flet as ft
from pathlib import Path
from core.base_plugin import BasePlugin
from config.theme import *
from ui.components import (
    section_header, primary_btn, secondary_btn, divider_y, spacer,
    status_text, progress_bar,
)
from engine import downloader
from config.app_config import config as app_config


class DownloadPlugin(BasePlugin):
    name = "无水印下载"
    icon = "📥"
    description = "多平台视频下载"
    version = "4.0"

    def __init__(self, page):
        super().__init__(page)
        self._fp = ft.FilePicker()
        self.page.services.append(self._fp)

        self.output_dir = app_config.get("output.download",
                                         str(Path.home() / "Desktop" / "素材下载"))
        self._running = False
        self._stop_flag = threading.Event()
        self._row_widgets = []
        self._refresh_thread = None
        self._task_id = 0  # 任务标识，防止旧线程误杀新任务

        # 线程安全数据区 —— 子线程只改这里，不碰 UI
        self._state = {
            "total": 0,
            "done": 0,
            "global_pct": 0.0,
            "status_msg": "就绪",
            "status_color": TEXT_MUTED,
            "rows": [],
        }
        self._state_lock = threading.Lock()

        VD = lambda: ft.VerticalDivider(width=1, color=BORDER_SUBTLE)
        self._table_header = ft.Row([
            ft.Text("文件", size=12, color=TEXT_MUTED, expand=4), VD(),
            ft.Text("状态", size=12, color=TEXT_MUTED, expand=2), VD(),
            ft.Text("大小", size=12, color=TEXT_MUTED, expand=2), VD(),
            ft.Text("进度", size=12, color=TEXT_MUTED, expand=1),
        ])
        self._row_column = ft.Column([], spacing=0)
        self._progress = progress_bar()
        self._status = status_text("就绪")

    # ─── 状态读写（线程安全） ───
    def _set_state(self, **kwargs):
        with self._state_lock:
            self._state.update(kwargs)

    def _get_state(self):
        with self._state_lock:
            return self._state.copy()

    def _set_row_state(self, idx, **kwargs):
        with self._state_lock:
            if 0 <= idx < len(self._state["rows"]):
                self._state["rows"][idx].update(kwargs)

    # ─── 主线程轮询刷新 UI ───
    async def _async_sync(self):
        """async 包装 _sync_ui，供 page.run_task 使用"""
        self._sync_ui()

    def _start_refresh(self):
        if self._refresh_thread and self._refresh_thread.is_alive():
            return

        def _tick():
            while self._running:
                time.sleep(0.5)
                if not self._running:
                    break
                self.page.run_task(self._async_sync)

        self._refresh_thread = threading.Thread(target=_tick, daemon=True)
        self._refresh_thread.start()

    def _sync_ui(self):
        """主线程调用：把状态数据同步到 UI 控件，包括每行进度条和文件名"""
        state = self._get_state()
        self._status.value = state["status_msg"]
        self._status.color = state["status_color"]
        self._progress.value = state["global_pct"]
        self._status.update()
        self._progress.update()

        rows_data = state["rows"]
        for i, row_data in enumerate(rows_data):
            if i < len(self._row_widgets):
                name_w, st, sz, bar = self._row_widgets[i]
                # 同步文件名
                if name_w.value != row_data.get("name", name_w.value):
                    name_w.value = row_data.get("name", name_w.value)
                    name_w.update()
                if st.value != row_data.get("status", st.value):
                    st.value = row_data.get("status", st.value)
                    st.color = row_data.get("status_color", st.color)
                    st.update()
                if sz.value != row_data.get("size", sz.value):
                    sz.value = row_data.get("size", sz.value)
                    sz.update()
                # 同步进度条
                row_pct = row_data.get("pct", 0)
                if bar.value != row_pct:
                    bar.value = row_pct
                    bar.update()

    # ─── 业务逻辑 ───
    def _extract_urls(self, text):
        urls = re.findall(r'https?://\S+', text)
        return urls if urls else [l.strip() for l in text.split('\n') if l.strip()]

    def _download(self, e):
        raw = self._link_input.value.strip()
        if not raw or self._running:
            return

        self._running = True
        self._task_id += 1
        self._stop_flag.clear()
        self._row_column.controls.clear()
        self._row_widgets.clear()

        self._set_state(
            total=0, done=0, global_pct=0,
            status_msg="准备中...", status_color=ACCENT,
            rows=[]
        )
        self.page.update()
        os.makedirs(self.output_dir, exist_ok=True)

        self._start_refresh()
        task_id = self._task_id
        threading.Thread(target=self._do_download, args=(raw, task_id), daemon=True).start()

    def _do_download(self, raw, task_id):
        """子线程执行：只改状态，不碰 UI"""
        urls = self._extract_urls(raw)
        total = len(urls)
        success = 0

        rows_data = [
            {"name": u[:50], "status": "排队", "size": "—", "status_color": TEXT_MUTED, "pct": 0}
            for u in urls
        ]
        self._set_state(total=total, rows=rows_data)

        # 先在主线程建好 UI 行
        async def _build_rows():
            VD = lambda: ft.VerticalDivider(width=1, color=BORDER_SUBTLE)
            for url in urls:
                name = ft.Text(url[:50], size=12, color=TEXT, expand=4,
                               no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS)
                st = ft.Text("排队", size=12, color=TEXT_MUTED, expand=2)
                sz = ft.Text("—", size=12, color=TEXT_MUTED, expand=2)
                bar = ft.ProgressBar(value=0, bgcolor="#23252A", color=ACCENT, height=3, expand=1)
                row = ft.Row([name, VD(), st, VD(), sz, VD(), bar])
                self._row_column.controls.append(row)
                self._row_widgets.append((name, st, sz, bar))
            self.page.update()
        self.page.run_task(_build_rows)
        # 等待 UI 行构建完成（防止进度回调先于控件创建触发）
        import asyncio as _asyncio
        _rows_ready = threading.Event()

        async def _mark_ready():
            _rows_ready.set()
        self.page.run_task(_mark_ready)
        _rows_ready.wait(timeout=5)

        for i, url in enumerate(urls):
            if self._stop_flag.is_set():
                self._set_row_state(i, status="已停止", status_color=TEXT_MUTED)
                break

            self._set_row_state(i, status="解析中", status_color=ACCENT)
            self._set_state(status_msg=f"下载中 {i+1}/{total}", status_color=ACCENT)

            def _on_progress(pct, dl, total_bytes, task_idx=i):
                if self._stop_flag.is_set() or self._task_id != task_id:
                    return
                if total_bytes > 0:
                    status_msg = f"下载中 {pct*100:.0f}%"
                    size_msg = f"{total_bytes/1048576:.1f}MB"
                    overall = (task_idx + pct) / total
                else:
                    status_msg = f"下载中 {dl/1048576:.1f}MB"
                    size_msg = "—"
                    overall = (task_idx + 0.5) / total
                self._set_row_state(task_idx, status=status_msg, size=size_msg, status_color=ACCENT, pct=pct)
                self._set_state(global_pct=overall)
                # 实时推送整行到 UI（状态+大小+进度条）
                async def _push_row(idx=task_idx, smsg=status_msg, ssz=size_msg, spct=pct):
                    if idx < len(self._row_widgets):
                        name_w, st, sz, bar = self._row_widgets[idx]
                        st.value = smsg
                        st.color = ACCENT
                        st.update()
                        sz.value = ssz
                        sz.update()
                        bar.value = spct if 0 <= spct <= 1 else 0
                        bar.update()
                self.page.run_task(_push_row)

            try:
                result = downloader.download_video(url, self.output_dir, _on_progress, self._stop_flag)
                if self._stop_flag.is_set():
                    self._set_row_state(i, status="已停止", status_color=TEXT_MUTED)
                    break

                if result["status"] == "done":
                    success += 1
                    fsize = result.get("size", 0)
                    size_str = "—"
                    if fsize:
                        for u in ["B", "KB", "MB", "GB"]:
                            if fsize < 1024:
                                size_str = f"{fsize:.1f} {u}"
                                break
                            fsize /= 1024
                    title = result.get('title', '')[:50] or urls[i][:50]
                    self._set_row_state(i, name=title, status="完成",
                                        size=size_str, status_color=GREEN)
                else:
                    err = result.get('error', '')[:20]
                    self._set_row_state(i, status=f"失败: {err}", status_color=RED)
            except Exception as ex:
                self._set_row_state(i, status=f"失败: {str(ex)[:20]}", status_color=RED)

        # 仅最新任务更新状态，旧任务静默退出
        if self._task_id == task_id:
            self._running = False
            self._set_state(
                global_pct=1.0,
                status_msg=f"完成 {success}/{total}",
                status_color=GREEN
            )
            self.page.run_task(self._async_sync)

    # ─── 登录 ───
    def _login_douyin(self, e): self._do_platform_login("douyin")
    def _login_kuaishou(self, e): self._do_platform_login("kuaishou")
    def _login_bilibili(self, e): self._do_platform_login("bilibili")
    def _login_tiktok(self, e): self._do_platform_login("tiktok")

    def _do_platform_login(self, platform):
        name = downloader.PLATFORMS.get(platform, {}).get('name', platform)
        self._set_state(status_msg=f"🔐 正在打开浏览器登录 {name}...", status_color=ACCENT)
        self.page.run_task(self._async_sync)
        threading.Thread(target=self._do_login_thread, args=(platform, name), daemon=True).start()

    def _do_login_thread(self, platform, name):
        ok = downloader.login_platform(platform)
        self._set_state(
            status_msg=f"✅ {name}登录成功" if ok else f"❌ {name}登录失败",
            status_color=GREEN if ok else RED
        )
        self.page.run_task(self._async_sync)

    # ─── 控制按钮 ───
    def on_deactivate(self):
        """切后台时停止下载 + 清理刷新线程"""
        self._stop_flag.set()
        self._running = False

    def _stop(self, e):
        self._stop_flag.set()
        self._set_state(status_msg="正在停止...", status_color=TEXT_MUTED)
        self.page.run_task(self._async_sync)

    def _clear(self, e):
        if self._running:
            self._stop(e)  # 先停止再清空
            return
        self._link_input.value = ""
        self._row_column.controls.clear()
        self._row_widgets.clear()
        self._set_state(
            status_msg="就绪", status_color=TEXT_MUTED,
            global_pct=0, rows=[]
        )
        self._link_input.update()
        self._row_column.update()
        self._status.update()
        self._progress.update()

    def _pick_output(self, e):
        self.page.run_task(self._do_pick_output)

    async def _do_pick_output(self):
        path = await self._fp.get_directory_path()
        if path:
            self.output_dir = path
            self._output_field.value = path
            app_config.set("output.download", path)
            self._output_field.update()

    # ─── 构建 UI ───
    def build(self) -> ft.Control:
        self._link_input = ft.TextField(
            hint_text="每行一条视频链接\n支持抖音 / TikTok / 快手 / B站",
            hint_style=ft.TextStyle(color=TEXT_MUTED),
            multiline=True, min_lines=8, max_lines=10,
            expand=1, bgcolor=CARD, color=TEXT, border_color=BORDER,
            border_radius=8, text_size=13,
            content_padding=P(14, 12, 14, 12),
        )
        self._output_field = ft.TextField(
            value=self.output_dir, expand=True, bgcolor=CARD, color=TEXT,
            border_color=BORDER, border_radius=8, text_size=13,
            content_padding=P(14, 12, 14, 12),
        )
        return ft.Container(ft.Column([
            section_header("无水印下载", "抖音 / TikTok / 快手 / B站"),
            divider_y(16), self._link_input, divider_y(16),
            ft.Row([
                primary_btn("开始下载", ft.Icons.DOWNLOAD, self._download),
                secondary_btn("停止", ft.Icons.STOP, self._stop),
                secondary_btn("清空", ft.Icons.CLEAR, self._clear),
                secondary_btn("抖音登录", ft.Icons.MUSIC_NOTE, self._login_douyin),
                secondary_btn("快手登录", ft.Icons.VIDEO_CAMERA_FRONT, self._login_kuaishou),
                secondary_btn("B站登录", ft.Icons.TV, self._login_bilibili),
                secondary_btn("TK登录", ft.Icons.MUSIC_VIDEO, self._login_tiktok),
                spacer(),
                ft.Text("保存至", size=12, color=TEXT_MUTED),
                ft.Container(self._output_field, width=300),
                secondary_btn("选择", ft.Icons.FOLDER_OUTLINED, self._pick_output),
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            divider_y(12),
            ft.Container(ft.Column([
                ft.Container(self._table_header, bgcolor=CARD,
                             padding=P(12, 8, 12, 8),
                             border_radius=ft.BorderRadius(6, 6, 0, 0)),
                ft.Divider(height=1, color=BORDER_SUBTLE),
                ft.Container(self._row_column, bgcolor=CARD,
                             padding=P(12, 4, 12, 4), expand=True),
            ], expand=True, spacing=0), expand=3, border_radius=8,
                         border=bd(), bgcolor=CARD),
            divider_y(12), self._progress, self._status,
        ], spacing=0), padding=P(24, 20, 24, 20), expand=True, bgcolor=CONTENT)
