#!/usr/bin/env python3
"""
电商工具箱 — 推送前自动预检 v2
捕获所有已知 Flet 0.28+ / PyInstaller / Python 兼容性问题
历史教训清单，一个都不能漏
"""
import re, sys, os

code_path = sys.argv[1] if len(sys.argv) > 1 else "video_toolbox_flet.py"
with open(code_path, "r") as f:
    code = f.read()

errors = []

# ============================================================
# 🔴 致命 — PyInstaller 打包后必崩
# ============================================================
CHECKS = [
    # Flet API 废弃
    (r"FilePicker\s*\(\s*on_result\s*=",        "❌ FilePicker(on_result=...) → 改为属性赋值 fp.on_result = cb"),
    (r"ft\.padding\.only\(",                      "❌ ft.padding.only() → 改为 ft.Padding(left=,top=,right=,bottom=)"),
    (r"ft\.padding\.all\(",                       "❌ ft.padding.all() → 改为 ft.Padding()"),
    (r"ft\.padding\.symmetric\(",                 "❌ ft.padding.symmetric() → 改为 ft.Padding()"),
    (r"ft\.UserControl",                         "❌ ft.UserControl → 已删除，用普通函数返回 Container"),
    (r"ft\.ResponsiveRow",                       "❌ ft.ResponsiveRow → 改用 ft.Row(wrap=True)"),
    (r"letter_spacing",                          "❌ letter_spacing → Flet 0.28 不支持"),
    (r"ft\.icons\.",                             "❌ ft.icons → 改用 ft.Icons (大写I)"),
    (r"ft\.border\.all\(",                       "❌ ft.border.all() → PyInstaller 崩溃，改用 _bd()"),

    # from __future__ 崩溃 Python 3.9
    (r"from __future__ import annotations",      "❌ from __future__ import annotations → Python 3.9+Flet 崩溃"),

    # PyInstaller 跨平台
    (r"ffmpeg\.exe\"(?!\s*if\s+_IS_WIN)",        "❌ ffmpeg.exe 硬编码 → 用 _IS_WIN 平台判断"),
    (r"yt-dlp\.exe\"(?!\s*if\s+_IS_WIN)",         "❌ yt-dlp.exe 硬编码 → 用 _IS_WIN 平台判断"),

    # 线程
    (r"daemon\s*=\s*True",                       "❌ daemon=True → 主进程退出时任务丢失"),
    (r"except\s*:\s*$",                          "❌ 裸 except: → 改用 except Exception:"),

    # Flet 保留字冲突
    (r"\bdisabled\s*[=:]\s*",                    "⚠️ 变量名 disabled → Flet 回调保留字，可能冲突"),

    # 旧版 API
    (r"ft\.Dropdown\s*\(\s*options\s*=\s*\[",    "⚠️ Dropdown options → 确认 key/text 参数顺序 (key, text)"),
]

for pattern, msg in CHECKS:
    if re.search(pattern, code):
        errors.append(msg)

# 额外检查：有 threading 必须有 Lock
has_thread = "threading.Thread" in code
has_lock = "threading.Lock()" in code
if has_thread and not has_lock:
    errors.append("❌ 有 threading.Thread 但没有 threading.Lock()")

# ============================================================
# 输出
# ============================================================
print(f"🔍 预检: {code_path}")
print(f"  行数: {len(code.splitlines())}")
print()

if errors:
    print(f"❌ 发现 {len(errors)} 个问题:")
    for e in errors:
        print(f"  {e}")
    print()
    print("修复后再推送")
    sys.exit(1)
else:
    print("✅ 全部通过，可以推送")
    sys.exit(0)
