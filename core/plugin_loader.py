"""插件加载器 — 自动发现 plugins/ 目录"""

import os
import sys
import inspect
import importlib
import traceback

import flet as ft
from core.base_plugin import BasePlugin

# 业务优先级排序（key=目录名，value=侧边栏位置权重）
_PLUGIN_ORDER = {
    "dedup": 10,
    "download": 20,
    "transcribe": 30,
    "ai_image": 40,
    "settings": 50,    # 设置置底
}


def discover_plugins(page: ft.Page) -> dict:
    """扫描 plugins/ 目录，自动发现所有插件"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)

    plugins_dir = os.path.join(root, "plugins")
    discovered = {}

    for entry in sorted(os.listdir(plugins_dir)):
        plugin_path = os.path.join(plugins_dir, entry)
        if not os.path.isdir(plugin_path) or entry.startswith("_"):
            continue
        if not os.path.exists(os.path.join(plugin_path, "__init__.py")):
            continue

        try:
            module = importlib.import_module(f"plugins.{entry}")
            for _name, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, BasePlugin) and obj is not BasePlugin:
                    discovered[entry] = obj(page)
                    break
        except Exception as e:
            print(f"[plugin_loader] 加载 {entry} 失败: {e}", file=sys.stderr)
            traceback.print_exc()

    # 按业务优先级排序返回
    plugins = dict(sorted(
        discovered.items(),
        key=lambda kv: (_PLUGIN_ORDER.get(kv[0], 999), kv[0])
    ))
    return plugins
