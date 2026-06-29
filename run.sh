#!/bin/bash
# 电商工具箱 v4 启动器
# 自动检测 Python 3.11 + Flet，缺失则提示安装

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

PYTHON=""

# 1. 检查 python3.11
for py in /opt/homebrew/bin/python3.11 /usr/local/bin/python3.11 /usr/bin/python3; do
    if [ -x "$py" ]; then
        PYTHON="$py"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    osascript -e 'display dialog "需要安装 Python 3.11\nbrew install python@3.11" with title "电商工具箱" buttons {"OK"} default button "OK" with icon caution'
    exit 1
fi

# 2. 检查 Flet
if ! $PYTHON -c "import flet" 2>/dev/null; then
    osascript -e 'display dialog "需要安装 Flet\npip3.11 install flet" with title "电商工具箱" buttons {"OK"} default button "OK" with icon caution'
    exit 1
fi

# 3. 查找 ffmpeg（brew 安装路径优先）
for ff_dir in /opt/homebrew/bin /usr/local/bin /usr/bin; do
    if [ -x "$ff_dir/ffmpeg" ]; then
        export PATH="$ff_dir:$PATH"
        break
    fi
done

# 4. 启动
exec $PYTHON main.py
