"""电商工具箱 v5 — 主入口（插件缓存 + 不重建）"""
import flet as ft
from config.theme import BG, SIDEBAR, BORDER, TEXT, P, get_theme
from config.logger import log
from core.plugin_loader import discover_plugins
from ui.layouts import build_sidebar, update_nav_active
# 子进程管理器在 engine/proc_manager.py，导入即注册 atexit 清理
import engine.proc_manager  # noqa: F401


def _check_deps():
    """启动时检查核心依赖，缺失输出日志警告"""
    import shutil
    deps = {
        "ffmpeg": "FFmpeg 未安装（视频处理需要）",
        "ffprobe": "ffprobe 未安装（视频探测需要）",
        "yt-dlp": "yt-dlp 未安装（B站/TikTok下载需要）",
    }
    for cmd, msg in deps.items():
        if not shutil.which(cmd):
            log.warning(msg)


def main(page: ft.Page):
    log.info("电商工具箱 v5 启动")
    # 依赖自检（缺失不阻塞，仅日志警告）
    _check_deps()
    page.title = "电商工具箱 v5"
    page.padding = 0
    page.bgcolor = BG
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = get_theme()
    page.dark_theme = page.theme
    page.window.width = 1280
    page.window.height = 840
    page.window.min_width = 1100
    page.window.min_height = 680

    plugins = discover_plugins(page)
    if not plugins:
        page.add(ft.Text("未发现插件，请检查 plugins/ 目录", color=TEXT))
        return
    log.info(f"加载 {len(plugins)} 个插件: {list(plugins.keys())}")

    # 缓存每个插件的 UI（只 build 一次）
    plugin_views = {}
    for key, plugin in plugins.items():
        plugin_views[key] = plugin.build()

    active_key = list(plugins.keys())[0]
    content_area = ft.Container(
        content=plugin_views[active_key],
        expand=True,
    )

    def switch_plugin(name: str):
        nonlocal active_key
        if name == active_key:
            return
        plugins[active_key].on_deactivate()
        active_key = name
        content_area.content = plugin_views[name]
        update_nav_active(sidebar.content, active_key)
        plugins[name].on_activate()
        page.update()

    sidebar = ft.Container(
        build_sidebar(
            plugins, active_key, switch_plugin,
            future_items=[
                ("🔥", "爆款分析", "AI 内容拆解"),
                ("🎬", "图生视频", "可灵 AI"),
                ("✂️", "智能剪辑", "视频编辑"),
            ]
        ),
        width=220, padding=P(20, 24, 20, 24), bgcolor=SIDEBAR,
    )

    main_app = ft.Container(
        ft.Row([
            sidebar,
            ft.VerticalDivider(width=1, color=BORDER),
            content_area,
        ], expand=True),
        expand=True,
    )
    page.add(main_app)
    page.update()
    # 手动触发首个插件的 on_activate（生命周期完整性）
    plugins[active_key].on_activate()


if __name__ == "__main__":
    ft.run(main)
