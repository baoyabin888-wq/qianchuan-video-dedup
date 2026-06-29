"""插件基类 — 所有功能 Tab 继承此基类"""

import flet as ft


class BasePlugin:
    """插件基类，所有功能模块继承此类"""
    
    name: str = "未命名"
    icon: str = "📦"
    description: str = ""
    version: str = "1.0"

    def __init__(self, page: ft.Page):
        self.page = page

    def build(self) -> ft.Control:
        """返回插件的 UI 控件 — 子类必须实现"""
        raise NotImplementedError

    def on_activate(self):
        """插件被切换到前台"""
        pass

    def on_deactivate(self):
        """插件被切换到后台"""
        pass
