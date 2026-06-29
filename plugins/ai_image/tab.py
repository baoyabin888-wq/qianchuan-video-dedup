"""AI 生图插件"""

import os
import time
import threading
import flet as ft
from pathlib import Path

from core.base_plugin import BasePlugin
from config.theme import *
from ui.components import (
    section_header, empty_state, primary_btn, secondary_btn, progress_bar, status_text,
    divider_y,
)
from engine import ai_image as ai_engine
from config.app_config import config as app_config
from engine.paths import user_data_dir

class AIImagePlugin(BasePlugin):
    name = "AI 生图"
    icon = "🖼"
    description = "AI 图片生成"
    version = "4.0"

    def __init__(self, page):
        super().__init__(page)
        self._fp = ft.FilePicker()
        self.page.services.append(self._fp)
        # 统一从配置中心读取
        self._api_key = app_config.get("minimax_api_key", "")
        self._model = app_config.get("ai_model", "minimax")
        self._prompt = ""
        self._images = []
        self.output_dir = app_config.get("output.ai_image", str(Path.home() / "Desktop" / "AI生图"))
        self._cache_dir = str(user_data_dir() / "temp" / "ai_images")
        self._stop_event = threading.Event()
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self._cache_dir, exist_ok=True)

    def on_deactivate(self):
        """切后台时取消正在进行的生图/优化请求"""
        self._stop_event.set()

    def _get_key_and_model(self):
        """根据当前选中模型读取对应 API Key"""
        model = app_config.get("ai_model", "minimax")
        key_map = {"minimax": "minimax_api_key", "tongyi": "tongyi_api_key", "zhipu": "zhipu_api_key"}
        key = app_config.get(key_map.get(model, "minimax_api_key"), "")
        return key, model

    def _optimize(self, e):
        self.page.run_task(self._do_optimize)

    async def _do_optimize(self):
        import asyncio
        raw = self._prompt_input.value.strip()
        api_key, model = self._get_key_and_model()
        if not raw or not api_key:
            return
        self._optimized.value = "优化中..."
        self._optimized.update()
        await asyncio.sleep(0.01)
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(None, ai_engine.optimize_prompt, raw, api_key, model)
            if result and result != raw:
                self._optimized.value = result
            else:
                self._optimized.value = raw + "\n\n[优化API暂不可用]"
        except Exception as ex:
            self._optimized.value = f"优化失败: {str(ex)[:80]}"
        self._optimized.update()

    def _generate(self, e):
        self.page.run_task(self._do_generate)

    async def _do_generate(self):
        import asyncio
        self._stop_event.clear()
        # 每次生成都取最新 key 和模型，确保设置页修改后立即生效
        api_key, model = self._get_key_and_model()
        prompt = self._optimized.value.strip() or self._prompt_input.value.strip()
        if not prompt or not api_key:
            return
        self._status.value = "生成中..."
        self._status.color = ACCENT
        self._progress.value = None
        self._status.update(); self._progress.update()
        self._generate_btn.disabled = True
        self._generate_btn.update()

        await asyncio.sleep(0.01)
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None, ai_engine.generate_image,
                prompt, api_key, int(self._count_dd.value), self._res_dd.value, model
            )
            if self._stop_event.is_set():
                return
            if result["status"] == "done":
                saved = ai_engine.save_images(result, self._cache_dir)
                self._images = saved
                self._show_images(saved)
                self._status.value = f"完成 {len(saved)} 张"
                self._status.color = GREEN
            else:
                self._status.value = result.get("error", "未知错误")[:80]
                self._status.color = RED
        except Exception as ex:
            self._status.value = str(ex)[:80]
            self._status.color = RED
        self._progress.value = 0
        self._status.update()
        self._progress.update()
        self._generate_btn.disabled = False
        self._generate_btn.update()

    def _show_images(self, paths):
        self._preview.controls = []
        for p in paths:
            if os.path.exists(p):
                self._preview.controls.append(
                    ft.Container(
                        ft.Column([
                            ft.Container(
                                ft.Image(src=p, width=240, height=240,
                                         fit=ft.BoxFit.COVER,
                                         border_radius=ft.BorderRadius(8, 8, 0, 0)),
                                on_click=lambda e, p=p: self._open_image(p),
                            ),
                            ft.Container(
                                ft.Row([
                                    ft.Text(Path(p).name, size=10, color=TEXT_MUTED,
                                            no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS,
                                            expand=True),
                                    ft.IconButton(
                                        icon=ft.Icons.SAVE_ALT, icon_size=16,
                                        icon_color=ACCENT,
                                        on_click=lambda e, p=p: self._save_image(p),
                                    ),
                                ], spacing=2, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                                padding=P(6, 4, 6, 4),
                            ),
                        ], spacing=0),
                        border_radius=8, border=bd(),
                        bgcolor=CARD,
                        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                    )
                )
        self._preview_wrapper.controls = [self._preview]
        self._preview_wrapper.update()
        self.page.update()

    def _save_image(self, src_path):
        """保存图片到默认输出目录"""
        import shutil
        name = Path(src_path).name
        dest = os.path.join(self.output_dir, name)
        try:
            shutil.copy2(src_path, dest)
            self._status.value = f"已保存: {name}"
            self._status.color = GREEN
        except Exception as ex:
            self._status.value = f"保存失败: {str(ex)[:50]}"
            self._status.color = RED
        self._status.update()

    def _open_image(self, path):
        import subprocess
        import sys
        if sys.platform == "darwin":
            subprocess.run(["open", path])
        elif sys.platform == "win32":
            os.startfile(path)

    def _pick_output(self, e):
        self.page.run_task(self._do_pick_output)

    async def _do_pick_output(self):
        path = await self._fp.get_directory_path()
        if path:
            self.output_dir = path
            app_config.set("output.ai_image", path)
            self._output_field.value = path
            self._output_field.update()

    def build(self) -> ft.Control:
        # min_lines=6 加高，不用 expand（避免抢预览区空间）
        self._prompt_input = ft.TextField(
            hint_text="输入中文提示词...",
            hint_style=ft.TextStyle(color=TEXT_MUTED),
            multiline=True, min_lines=3, max_lines=3,
            bgcolor=CARD, color=TEXT, border_color=BORDER,
            border_radius=8, text_size=13,
            content_padding=P(14, 12, 14, 12),
        )
        self._prompt_input.on_change = lambda e: setattr(self, "_prompt", e.control.value)
        self._optimized = ft.TextField(
            hint_text="优化后可编辑...",
            hint_style=ft.TextStyle(color=TEXT_MUTED),
            multiline=True, min_lines=3, max_lines=3,
            bgcolor=CARD, color=TEXT, border_color=BORDER,
            border_radius=8, text_size=13,
            content_padding=P(14, 12, 14, 12),
        )
        self._output_field = ft.TextField(
            value=self.output_dir,
            width=280, bgcolor=CARD, color=TEXT, border_color=BORDER,
            border_radius=8, text_size=13, content_padding=P(14, 12, 14, 12),
        )
        self._status = status_text("就绪")
        self._progress = progress_bar()
        self._preview = ft.Row([], spacing=12, scroll=ft.ScrollMode.AUTO)
        self._img_state = empty_state(
            ft.Icons.IMAGE_OUTLINED,
            "尚无生成结果",
            "在上方输入提示词，点击 生成 开始",
        )
        self._preview_wrapper = ft.Column([self._img_state], expand=True)
        self._count_dd = ft.Dropdown(
            value="3",
            options=[ft.dropdown.Option(str(n), f"{n}张") for n in range(1, 6)],
            width=90, bgcolor=CARD, color=TEXT, border_color=BORDER,
            border_radius=6, text_size=13,
        )
        self._res_dd = ft.Dropdown(
            value="720x1280",
            options=[
                ft.dropdown.Option("720x1280", "720p (竖屏)"),
                ft.dropdown.Option("1080x1920", "1080p (竖屏)"),
                ft.dropdown.Option("2048x2048", "2K (方图)"),
                ft.dropdown.Option("4096x4096", "4K (方图)"),
            ],
            width=150, bgcolor=CARD, color=TEXT, border_color=BORDER,
            border_radius=6, text_size=13,
        )
        self._generate_btn = primary_btn("生成", ft.Icons.IMAGE, self._generate)

        return ft.Container(ft.Column([
            section_header("AI 生图", "文本描述 → 自动优化提示词 → 生成图片"),
            divider_y(16),
            divider_y(12),
            ft.Text("原始提示词", size=12, color=TEXT_MUTED),
            divider_y(6),
            self._prompt_input,
            divider_y(12),
            ft.Text("优化后", size=12, color=TEXT_MUTED),
            divider_y(6),
            self._optimized,
            divider_y(12),
            # 按钮全部放一排
            ft.Row([
                primary_btn("优化文案", ft.Icons.AUTO_AWESOME, self._optimize),
                ft.Container(width=8),
                self._generate_btn,
                ft.Text("生成数量", size=12, color=TEXT_MUTED),
                self._count_dd,
                ft.Text("分辨率", size=12, color=TEXT_MUTED),
                self._res_dd,
            ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            divider_y(12),
            self._progress,
            ft.Row([self._status], spacing=10),
            divider_y(12),
            # 预览 — 独占剩余空间
            ft.Container(
                content=self._preview_wrapper,
                expand=True, border_radius=8, border=bd(),
                bgcolor=CARD, padding=P(14, 12, 14, 12),
            ),
        ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.STRETCH), padding=P(24, 20, 24, 20), expand=True, bgcolor=CONTENT)