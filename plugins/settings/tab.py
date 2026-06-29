"""设置插件 — 统一配置中心"""
import flet as ft
from core.base_plugin import BasePlugin
from config.theme import *
from ui.components import section_header, divider_y, status_text
from config.app_config import config

class SettingsPlugin(BasePlugin):
    name = "设置"
    icon = "⚙"
    description = "API Key · 路径配置"
    version = "4.0"

    def __init__(self, page):
        super().__init__(page)
        self._status = status_text("")
        self._save_timer = None

    def on_deactivate(self):
        """切后台时强制刷入待保存配置"""
        if self._save_timer:
            self._save_timer.cancel()
            self._save_timer = None
            config.set("minimax_api_key", self._minimax_key.value)
            config.set("tongyi_api_key", self._tongyi_key.value)
            config.set("zhipu_api_key", self._zhipu_key.value)
            config.set("output.ai_image", self._ai_output.value)

    def _on_key_change(self, e):
        import threading
        if self._save_timer:
            self._save_timer.cancel()
        tag = getattr(e.control, 'data', '')
        key_map = {
            'minimax_api_key': "minimax_api_key",
            'tongyi_api_key': "tongyi_api_key",
            'zhipu_api_key': "zhipu_api_key",
            'ai_model': "ai_model",
            'output.ai_image': "output.ai_image",
        }
        key = key_map.get(tag)
        if not key:
            return
        val = e.control.value if tag != 'ai_model' else e.control.value

        def _do_save():
            config.set(key, val)
            self.page.run_task(self._mark_saved)

        self._save_timer = threading.Timer(0.5, _do_save)
        self._save_timer.start()

    def _on_blur(self, e):
        """失焦时立即保存"""
        if self._save_timer:
            self._save_timer.cancel()
            self._save_timer = None
        self._on_key_change(e)

    async def _mark_saved(self):
        self._status.value = "已保存"
        self._status.color = GREEN
        self._status.update()

    def build(self) -> ft.Control:
        self._model_dd = ft.Dropdown(
            value=config.get("ai_model", "minimax"),
            options=[
                ft.dropdown.Option("minimax", "MiniMax image-01"),
                ft.dropdown.Option("tongyi", "通义万相 (阿里)"),
                ft.dropdown.Option("zhipu", "智谱 CogView-3"),
            ],
            width=300, bgcolor=CARD, color=TEXT, border_color=BORDER,
            border_radius=8, text_size=13,
            data='ai_model',
        )
        self._model_dd.on_change = self._on_key_change

        def _make_key_field(provider, hint, data_tag):
            tf = ft.TextField(
                value=config.get(data_tag, ""),
                password=True, can_reveal_password=True,
                hint_text=hint,
                hint_style=ft.TextStyle(color=TEXT_MUTED),
                bgcolor=CARD, color=TEXT, border_color=BORDER,
                border_radius=8, text_size=13,
                content_padding=P(14, 12, 14, 12),
                data=data_tag,
            )
            tf.on_change = self._on_key_change
            tf.on_blur = self._on_blur
            return tf

        self._minimax_key = _make_key_field("minimax", "MiniMax API Key（sk-cp-...）", "minimax_api_key")
        self._tongyi_key = _make_key_field("tongyi", "通义万相 API Key（sk-...）", "tongyi_api_key")
        self._zhipu_key = _make_key_field("zhipu", "智谱 API Key", "zhipu_api_key")

        self._ai_output = ft.TextField(
            value=config.get("output.ai_image", ""),
            hint_text="AI 生图保存路径",
            hint_style=ft.TextStyle(color=TEXT_MUTED),
            bgcolor=CARD, color=TEXT, border_color=BORDER,
            border_radius=8, text_size=13,
            content_padding=P(14, 12, 14, 12),
            data='output.ai_image',
        )
        self._ai_output.on_change = self._on_key_change
        self._ai_output.on_blur = self._on_blur

        return ft.Container(ft.Column([
            section_header("设置", "选择模型 → 填入 API Key → 开始生图"),
            divider_y(20),
            ft.Text("AI 生图模型", size=13, weight=ft.FontWeight.W_600, color=TEXT),
            ft.Text("切换模型后填入对应的 API Key 即可使用", size=12, color=TEXT_MUTED),
            divider_y(10),
            self._model_dd,
            divider_y(20),
            ft.Text("MiniMax API Key", size=13, weight=ft.FontWeight.W_600, color=TEXT),
            ft.Text("platform.minimaxi.com 获取", size=12, color=TEXT_MUTED),
            divider_y(10),
            ft.Row([self._minimax_key]),
            divider_y(16),
            ft.Text("通义万相 API Key", size=13, weight=ft.FontWeight.W_600, color=TEXT),
            ft.Text("dashscope.aliyun.com 获取", size=12, color=TEXT_MUTED),
            divider_y(10),
            ft.Row([self._tongyi_key]),
            divider_y(16),
            ft.Text("智谱 API Key", size=13, weight=ft.FontWeight.W_600, color=TEXT),
            ft.Text("open.bigmodel.cn 获取", size=12, color=TEXT_MUTED),
            divider_y(10),
            ft.Row([self._zhipu_key]),
            divider_y(16),
            self._status,
            divider_y(24),
            ft.Text("AI 生图保存路径", size=13, weight=ft.FontWeight.W_600, color=TEXT),
            divider_y(10),
            ft.Row([self._ai_output]),
            divider_y(32),
            ft.Text("其他设置", size=13, weight=ft.FontWeight.W_600, color=TEXT_MUTED),
            ft.Text("更多配置项即将推出", size=12, color=TEXT_MUTED),
            ft.Container(expand=True),
        ], spacing=0), padding=P(24, 20, 24, 20), expand=True, bgcolor=CONTENT)
