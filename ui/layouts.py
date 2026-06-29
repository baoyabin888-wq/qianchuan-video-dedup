"""侧边栏布局 — 增量更新激活态，不全量重建"""
import flet as ft
from config.theme import ACCENT, ACCENT_10, TEXT, TEXT_MUTED, BORDER


def nav_card(icon, title, sub, key, active=False, future=False, on_click=None):
    """单个导航卡片"""
    color = ACCENT if active else TEXT if not future else "#3A3D44"
    bg_hover = ACCENT_10 if active else "#1A1C1F"
    card = ft.Container(
        ft.Row([
            ft.Text(icon, size=16),
            ft.Column([
                ft.Text(title, size=13, weight=ft.FontWeight.W_600, color=color),
                ft.Text(sub, size=11, color=TEXT_MUTED),
            ], spacing=1, alignment=ft.MainAxisAlignment.CENTER),
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        height=48, padding=ft.Padding(12, 6, 12, 6), border_radius=8,
        bgcolor=ACCENT_10 if active else None,
        opacity=0.4 if future else 1,
        on_click=on_click if not future else None,
        data=key,
        animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
    )

    def _on_hover(e):
        e.control.bgcolor = bg_hover if e.data == "true" else (ACCENT_10 if active else None)
        e.control.update()

    card.on_hover = _on_hover
    return card


def update_nav_active(sidebar_column: ft.Column, active_key: str):
    """增量更新：只修改激活态，不重建整个侧边栏"""
    for ctrl in sidebar_column.controls:
        if isinstance(ctrl, ft.Container) and ctrl.data == active_key:
            ctrl.bgcolor = ACCENT_10
            ctrl.content.controls[1].controls[0].color = ACCENT
        elif isinstance(ctrl, ft.Container) and ctrl.data and ctrl.data != active_key:
            ctrl.bgcolor = None
            ctrl.content.controls[1].controls[0].color = TEXT
    sidebar_column.update()


def build_sidebar(plugins: dict, active_key: str, switch_fn,
                  future_items=None) -> ft.Column:
    """构建完整侧边栏（仅初始化调用一次）"""
    items = [
        ft.Row([
            ft.Container(width=4, height=24, bgcolor=ACCENT, border_radius=2),
            ft.Text("电商工具箱", size=18, weight=ft.FontWeight.W_700, color=TEXT),
        ], spacing=10),
        ft.Divider(height=32, color="transparent"),
    ]

    for name, p in plugins.items():
        def make_handler(k):
            return lambda e: switch_fn(k)
        items.append(nav_card(p.icon, p.name, p.description, name,
                              active=active_key == name,
                              on_click=make_handler(name)))

    if future_items:
        items.append(ft.Divider(height=28, color=BORDER))
        items.append(ft.Text("即将推出", size=10, weight=ft.FontWeight.W_600,
                             color=TEXT_MUTED))
        items.append(ft.Divider(height=10, color="transparent"))
        for icon, name, desc in future_items:
            items.append(nav_card(icon, name, desc, name, future=True))

    items.append(ft.Container(expand=True))
    items.append(ft.Divider(height=20, color=BORDER))
    items.append(ft.Row([
        ft.CircleAvatar(content=ft.Text("👤", size=18), radius=16,
                        bgcolor=ACCENT_10),
        ft.Column([
            ft.Text("管理员", size=13, weight=ft.FontWeight.W_600, color=TEXT),
            ft.Text("v5.0", size=11, color=ACCENT),
        ], spacing=0),
        ft.Container(expand=True),
    ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER))

    return ft.Column(items, spacing=6)
