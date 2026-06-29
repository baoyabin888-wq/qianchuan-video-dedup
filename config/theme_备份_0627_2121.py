"""电商工具箱 v4 — Linear 暗黑主题设计系统"""

from flet import (
    Colors, Theme, ColorScheme,
    ButtonStyle, RoundedRectangleBorder, Padding, BorderSide, Border,
    FontWeight,
)

# ═══ 颜色 ═══
ACCENT = "#5E6AD2"
ACCENT_HOVER = "#828FFF"
BG = "#08090A"
SIDEBAR = "#0F1011"
CONTENT = "#0C0D10"
CARD = "#191A1B"
BORDER = "#1423252A"
BORDER_SUBTLE = "#0D23252A"
TEXT = "#D0D6E0"
TEXT_PRIMARY = "#F7F8F8"
TEXT_MUTED = "#8A8F98"
GREEN = "#34D399"
RED = "#F87171"

# Alpha variants
ACCENT_10 = "#105E6AD2"
ACCENT_20 = "#205E6AD2"
ACCENT_60 = "#605E6AD2"

# ═══ 间距 ═══
P = Padding
GAP_SM = 8
GAP_DEFAULT = 12
GAP_SECTION = 24
PAD_OUTER = 32

# ═══ 字体 ═══
FONT = "SF Pro Display, PingFang SC"
FONT_MONO = "Menlo, SF Mono"

# ═══ 按钮 ═══
BTN_PRIMARY = ButtonStyle(
    shape=RoundedRectangleBorder(radius=8),
    padding=P(18, 10, 18, 10),
    bgcolor=ACCENT, color="white",
)
BTN_SECONDARY = ButtonStyle(
    shape=RoundedRectangleBorder(radius=8),
    padding=P(18, 10, 18, 10),
    bgcolor=CARD, color=TEXT,
)


def get_theme() -> Theme:
    return Theme(
        color_scheme=ColorScheme(
            primary=ACCENT, secondary=ACCENT,
            surface=CARD, on_primary="white",
            on_surface=TEXT, outline=BORDER,
            error=RED,
        ),
        use_material3=True,
    )


# ═══ UI helper ═══
def h1(text):
    from flet import Text
    return Text(text, size=18, weight=FontWeight.W_700, color=TEXT_PRIMARY)

def h2(text):
    from flet import Text
    return Text(text, size=15, weight=FontWeight.W_600, color=TEXT_PRIMARY)

def subtitle(text):
    from flet import Text
    return Text(text, size=13, color=TEXT_MUTED)

def divider(height=24):
    from flet import Divider
    return Divider(height=height, color=BORDER)

def bd(width: int = 1, color: str = BORDER):
    """Border helper — Flet 0.85 兼容（ft.border.all 不存在）"""
    bs = BorderSide(width, color)
    return Border(top=bs, left=bs, right=bs, bottom=bs)

def cn_font():
    """跨平台中文字体"""
    import sys
    if sys.platform == "darwin":
        return "STHeiti Light"
    if sys.platform == "win32":
        return "Microsoft YaHei"
    return "Noto Sans CJK SC"
