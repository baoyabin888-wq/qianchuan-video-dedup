"""通用 UI 组件"""

import flet as ft
from config.theme import (
    ACCENT, TEXT_PRIMARY, TEXT_MUTED,
    CARD, BTN_PRIMARY, BTN_SECONDARY,
)


def section_header(title, subtitle_text, show_actions=None):
    """统一的 section 标题区域"""
    items = [
        ft.Text(title, size=15, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
        ft.Container(width=8),
        ft.Text(subtitle_text, size=12, color=TEXT_MUTED),
        ft.Container(expand=True),
    ]
    if show_actions:
        items.append(show_actions)
    return ft.Row(items, vertical_alignment=ft.CrossAxisAlignment.CENTER)


def empty_state(icon_name, title_text, hint_text, on_action=None, action_text=""):
    """空状态占位 — 极简扁平，无卡片边框"""
    content = ft.Column([
        ft.Icon(icon_name, size=32, color=TEXT_MUTED),
        ft.Container(height=12),
        ft.Text(title_text, size=13, weight=ft.FontWeight.W_600, color=TEXT_MUTED),
        ft.Container(height=2),
        ft.Text(hint_text, size=12, color=TEXT_MUTED),
        ft.Container(height=14),
    ] + ([
        ft.Button(action_text, icon=icon_name, style=BTN_PRIMARY,
                          on_click=on_action)
    ] if action_text and on_action else []),
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )
    return ft.Container(
        content, expand=True,
        bgcolor=CARD, border_radius=8,
    )


def progress_bar(value=0):
    """统一进度条"""
    return ft.ProgressBar(value=value, bgcolor="#23252A", color=ACCENT, height=3)


def status_text(msg="就绪", color=TEXT_MUTED):
    return ft.Text(msg, size=12, color=color)


def primary_btn(text, icon=None, on_click=None):
    return ft.Button(text, icon=icon, style=BTN_PRIMARY, on_click=on_click)


def secondary_btn(text, icon=None, on_click=None):
    return ft.Button(text, icon=icon, style=BTN_SECONDARY, on_click=on_click)


def divider_y(height=12):
    """纵向间距（用透明 Container 替代 Divider，更可控）"""
    return ft.Container(height=height)


def spacer(expand=True):
    """弹性空白 — 用于工具栏左/右对齐"""
    return ft.Container(expand=expand) if expand else ft.Container(width=8)


def status_footer(status_control, progress_control, right_actions: list):
    """统一底部状态行：左状态/进度 | 右操作按钮组"""
    return ft.Column([
        progress_control,
        ft.Row([
            status_control,
            spacer(),
            *right_actions,
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
    ], spacing=6)
