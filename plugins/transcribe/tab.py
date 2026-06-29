"""语音转文案插件"""

import os
import threading
import flet as ft
from pathlib import Path

from core.base_plugin import BasePlugin
from config.theme import *
from ui.components import (
    section_header, primary_btn, secondary_btn, divider_y, spacer,
)
from engine import transcribe as whisper_engine
from config.app_config import config as app_config

class TranscribePlugin(BasePlugin):
    name = "语音转文案"
    icon = "🎙"
    description = "Whisper 识别"
    version = "4.0"

    def __init__(self, page):
        super().__init__(page)
        self._fp = ft.FilePicker()
        self._export_fp = ft.FilePicker()
        self.page.services.append(self._fp)
        self.page.services.append(self._export_fp)
        self.video_path = ""
        self._result_text = ""
        self._model_name = app_config.get("transcribe.model", "base")
        self._stop_event = threading.Event()
        self._transcribing = False

    def on_deactivate(self):
        """切后台时取消正在进行的转写任务"""
        self._stop_event.set()

    def _pick_video(self, e):
        self.page.run_task(self._do_pick_video)

    async def _do_pick_video(self):
        result = await self._fp.pick_files(
            allowed_extensions=["mp4", "mov", "mkv", "avi", "wav", "mp3"]
        )
        if result:
            self.video_path = result[0].path
            self._file_info.value = f"已选: {Path(self.video_path).name}"
            self._file_info.color = TEXT_PRIMARY
            self._file_info.update()

    def _transcribe(self, e):
        if self._transcribing:
            return
        self.page.run_task(self._do_transcribe)

    async def _do_transcribe(self):
        import asyncio
        if not self.video_path or self._transcribing:
            return
        self._transcribing = True
        self._stop_event.clear()
        self._result.value = "提取音频中..."
        self._result.color = ACCENT
        self._result.update()
        self._transcribe_btn.disabled = True
        self._transcribe_btn.update()

        await asyncio.sleep(0.01)
        loop = asyncio.get_event_loop()

        # 1. 提取音频（ffmpeg 阻塞，放线程池）
        try:
            audio_path = await loop.run_in_executor(
                None, whisper_engine.extract_audio,
                self.video_path, self.output_dir
            )
        except Exception as e:
            self._result.value = f"提取音频失败: {str(e)[:50]}"
            self._result.color = RED
            self._result.update()
            self._transcribe_btn.disabled = False
            self._transcribe_btn.update()
            return

        if self._stop_event.is_set():
            self._result.value = "已取消"
            self._result.color = TEXT_MUTED
            self._result.update()
            self._transcribe_btn.disabled = False
            self._transcribe_btn.update()
            return

        self._result.value = f"识别中... (model={self._model_name})"
        self._result.update()
        await asyncio.sleep(0.01)

        # 2. Whisper 识别（也阻塞，放线程池）
        try:
            result = await loop.run_in_executor(
                None, whisper_engine.transcribe_audio,
                audio_path, self._model_name
            )
            self._result_text = result["text"]
            self._result.value = self._result_text
            self._result.color = TEXT_PRIMARY
        except Exception as e:
            self._result.value = f"识别失败: {str(e)[:50]}"
            self._result.color = RED
        finally:
            self._transcribing = False
            self._transcribe_btn.disabled = False
            self._transcribe_btn.update()
            self._result.update()
            if os.path.exists(audio_path):
                os.remove(audio_path)

    def _export_txt(self, e):
        """弹出保存对话框"""
        text = self._result_text or self._result.value or ""
        if not text or "在这里显示" in text or not text.strip():
            self.page.snack_bar = ft.SnackBar(content=ft.Text("请先识别"), open=True)
            self.page.update()
            return
        self._export_text = text
        self.page.run_task(self._do_export_save)

    def _copy_text(self, e):
        if not self._result_text:
            return
        try:
            import pyperclip
            pyperclip.copy(self._result_text)
        except ImportError:
            import subprocess as _sp
            import sys as _sys
            if _sys.platform == "darwin":
                _sp.run(["pbcopy"], input=self._result_text, text=True)
            elif _sys.platform == "win32":
                _sp.run(["clip"], input=self._result_text, text=True)
        # 用 SnackBar 提示
        self.page.snack_bar = ft.SnackBar(content=ft.Text("已复制到剪贴板"), open=True,
                                          duration=2000, bgcolor=GREEN)
        self.page.update()

    def _clear(self, e):
        self._result_text = ""
        self._result.value = "识别结果将在这里显示"
        self._result.color = TEXT_MUTED
        self._result.update()

    @property
    def output_dir(self):
        from engine.paths import user_data_dir
        d = user_data_dir() / "temp" / "whisper"
        d.mkdir(parents=True, exist_ok=True)
        return str(d)

    async def _do_export_save(self):
        path = await self._export_fp.save_file(
            allowed_extensions=["txt"],
            dialog_title="保存文案",
            file_name="文案输出.txt"
        )
        if path and hasattr(self, '_export_text'):
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self._export_text)
                self.page.snack_bar = ft.SnackBar(content=ft.Text("已保存"), open=True)
            except Exception as ex:
                self.page.snack_bar = ft.SnackBar(content=ft.Text(f"保存失败: {str(ex)[:50]}"), open=True)
            self.page.update()

    def build(self) -> ft.Control:
        os.makedirs(self.output_dir, exist_ok=True)
        # 文件信息文本
        self._file_info = ft.Text("未选择视频", size=13, color=TEXT_MUTED)
        # 模型下拉
        self._model_dd = ft.Dropdown(
            value=self._model_name,
            options=[
                ft.dropdown.Option("tiny", "tiny · 极速"),
                ft.dropdown.Option("base", "base · 平衡"),
                ft.dropdown.Option("small", "small · 较准"),
                ft.dropdown.Option("medium", "medium · 精准"),
            ],
            width=180, bgcolor=CARD, color=TEXT, border_color=BORDER,
            border_radius=8, text_size=13,
        )
        self._model_dd.on_change = lambda e: (
            setattr(self, "_model_name", e.control.value),
            app_config.set("transcribe.model", e.control.value)
        )
        # 识别按钮
        self._transcribe_btn = primary_btn("开始识别", ft.Icons.AUTO_AWESOME, self._transcribe)
        # 结果区文本
        self._result = ft.Text(
            "识别结果将在这里显示\n\n选择视频 → 选择模型 → 点击开始识别",
            size=13, color=TEXT_MUTED,
            selectable=True,
        )

        return ft.Container(ft.Column([
            section_header("语音转文案", "提取视频音频 → Whisper 语音识别 → 输出文案"),
            divider_y(16),
            # 工具栏 1: 文件选择
            ft.Row([
                primary_btn("选择视频", ft.Icons.UPLOAD_FILE, self._pick_video),
                self._file_info,
            ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            divider_y(12),
            # 工具栏 2: 模型 + 操作（跟 dedup 工具栏完全一样的 pattern）
            ft.Row([
                ft.Text("模型", size=12, color=TEXT_MUTED),
                self._model_dd,
                spacer(),
                self._transcribe_btn,
                secondary_btn("复制", ft.Icons.COPY, self._copy_text),
                secondary_btn("清空", ft.Icons.CLEAR, self._clear),
                secondary_btn("导出 TXT", ft.Icons.TEXT_SNIPPET,
                              lambda e: (setattr(self, '_export_flag', True),
                                         self._export_txt(e))),
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER,
               scroll=ft.ScrollMode.AUTO),
            divider_y(12),
            # 结果区 — ListView 撑满
            ft.Container(
                content=ft.ListView([self._result], expand=True, spacing=0),
                expand=True, border_radius=8,
                border=bd(), bgcolor=CARD, padding=P(14, 12, 14, 12),
            ),
        ], spacing=0), padding=P(24, 20, 24, 20), expand=True, bgcolor=CONTENT)