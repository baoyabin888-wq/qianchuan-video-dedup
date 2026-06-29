"""电商工具箱 v4 — 严格对齐 Linear.app DESIGN.md (HU-UH/awesome-design-md)"""
# 参考：https://github.com/HU-UH/awesome-design-md/blob/main/design-md/linear.app/DESIGN.md

from flet import (
    Theme, ColorScheme,
    ButtonStyle, RoundedRectangleBorder, Padding, BorderSide, Border,
    FontWeight,
)

# ═══ 背景层（luminance stacking）═══
MARKETING_BLACK = "#08090A"   # Linear 营销页背景（最暗）
PANEL_DARK      = "#0F1011"   # 侧边栏/面板（+1 级）
LEVEL3_SURFACE  = "#191A1B"   # 卡片/提升表面（+2 级）
SECONDARY_SURFACE = "#28282C"  # hover/次级（+3 级，最亮暗色）

# 主别名（兼容旧代码）
BG       = MARKETING_BLACK
SIDEBAR  = PANEL_DARK
CONTENT  = MARKETING_BLACK  # Linear 用同一色作内容区
CARD     = LEVEL3_SURFACE

# ═══ 文字色（4 级灰阶）═══
TEXT_PRIMARY    = "#F7F8F8"   # 主文字 — 不是纯白
TEXT            = "#D0D6E0"   # body 文字 — 冷银灰
TEXT_MUTED      = "#8A8F98"   # 次要文字
TEXT_QUATERNARY = "#62666D"   # 最弱文字（时间戳/disabled）

# 按钮文字
BUTTON_TEXT_LIGHT  = "#E2E4E7"   # ghost button
BUTTON_TEXT_SILVER = "#D0D6E0"   # subtle button
BUTTON_TEXT_WHITE  = "#FFFFFF"   # primary

# ═══ 品牌强调色（唯一彩色）═══
ACCENT         = "#5E6AD2"   # Brand Indigo
ACCENT_VIOLET  = "#7170FF"   # 链接/active
ACCENT_HOVER   = "#828FFF"   # hover 态
SECURITY_LAVENDER = "#7A7FAD"  # 安全相关 UI

# Alpha variants（标准rgba格式，全版本兼容）
ACCENT_10  = "rgba(94, 106, 210, 0.1)"
ACCENT_20  = "rgba(94, 106, 210, 0.2)"
ACCENT_60  = "rgba(94, 106, 210, 0.6)"

# ═══ 状态色（仅用于 status indicator）═══
GREEN       = "#27A644"   # Linear 主成功色（不是 emerald）
GREEN_PILL  = "#10B981"   # 次成功（pill 用）
RED         = "#EF4444"   # destructive
ORANGE      = "#FCD34D"   # accent

# ═══ 边框（Linear 风格 — Flet 0.85 不完全支持 8 位 hex，用 Linear 风的实色但保持暗）═══
BORDER         = "#2A2D33"  # 接近 rgba(255,255,255,0.08) 在深背景上的视觉效果
BORDER_SUBTLE  = "#22252B"  # 微妙
BORDER_SOLID   = "#23252A"
BORDER_SOLID_LIGHT = "#34343A"
BORDER_SOLID_LIGHTER = "#3E3E44"
LINE_TINT      = "#141516"
LINE_TERTIARY  = "#18191A"

# 半透明按钮背景（用 Linear 同色但用 Flet 支持的格式）
BTN_GHOST_BG       = "#1F2127"  # ghost button 背景（暗）
BTN_SUBTLE_BG      = "#22252B"  # subtle button
BTN_ICON_BG        = "#252830"  # icon button
BTN_HOVER_BG       = "#2A2D33"  # hover

# ═══ 间距（8px 基础网格）═══
SPACE_XS  = 4
SPACE_SM  = 8
SPACE_MD  = 12
SPACE_LG  = 16
SPACE_XL  = 24
SPACE_2XL = 32
SPACE_3XL = 48

# 主别名（兼容旧代码）
P = Padding
GAP_SM = SPACE_SM
GAP_DEFAULT = SPACE_MD
GAP_SECTION = SPACE_LG
PAD_OUTER = SPACE_XL

# ═══ 字体（Mac 本地化）═══
# Linear 用 Inter Variable + Berkeley Mono + cv01/ss03
# Mac 没有 Inter，用 SF Pro Display 替代
FONT = "SF Pro Display, Inter, -apple-system, PingFang SC"
FONT_MONO = "SF Mono, Menlo, Berkeley Mono"

# Linear 三级字重系统
WEIGHT_READ = FontWeight.W_400       # 阅读
WEIGHT_EMPHASIS = FontWeight.W_500   # 强调（Linear 用 510 但 Flet 不支持）
WEIGHT_STRONG = FontWeight.W_600     # 强强调（Linear 用 590）

# 字号（按 Linear 比例）
SIZE_DISPLAY    = 36
SIZE_H1         = 24
SIZE_H2         = 20
SIZE_H3         = 18
SIZE_BODY       = 13   # Linear body = 14-16，但 app 紧凑用 13
SIZE_SMALL      = 12
SIZE_CAPTION    = 11
SIZE_TINY       = 10

# 主别名
SIZE_TITLE     = SIZE_H1
SIZE_SUBTITLE  = SIZE_BODY
SIZE_SECTION   = SIZE_H2

# ═══ 圆角（Linear 8 级）═══
RADIUS_MICRO    = 2
RADIUS_STANDARD = 4
RADIUS_COMFORT  = 6
RADIUS_CARD     = 8
RADIUS_PANEL    = 12
RADIUS_LARGE    = 22
RADIUS_PILL     = 9999

# ═══ 阴影（Linear 多层）═══
SHADOW_LEVEL1 = "rgba(0,0,0,0.03) 0px 1.2px 0px 0px"
SHADOW_LEVEL2 = "rgba(255,255,255,0.05) bg + 1px solid rgba(255,255,255,0.08)"
SHADOW_FOCUS  = "rgba(0,0,0,0.1) 0px 4px 12px"

# ═══ 按钮样式（Linear 三级）═══
# Primary: 品牌色背景
BTN_PRIMARY = ButtonStyle(
    shape=RoundedRectangleBorder(radius=RADIUS_COMFORT),
    padding=P(SPACE_LG, SPACE_MD - 2, SPACE_LG, SPACE_MD - 2),
    bgcolor=ACCENT, color="white",
)
# Secondary: subtle（半透明背景）
BTN_SECONDARY = ButtonStyle(
    shape=RoundedRectangleBorder(radius=RADIUS_COMFORT),
    padding=P(SPACE_LG, SPACE_MD - 2, SPACE_LG, SPACE_MD - 2),
    bgcolor=LEVEL3_SURFACE, color=TEXT,
)


def get_theme() -> Theme:
    return Theme(
        color_scheme=ColorScheme(
            primary=ACCENT, secondary=ACCENT_VIOLET,
            surface=LEVEL3_SURFACE, on_primary="white",
            on_surface=TEXT, outline=BORDER,
            error=RED,
        ),
        use_material3=True,
    )


# ═══ UI helper ═══
def h1(text):
    from flet import Text
    return Text(text, size=SIZE_H1, weight=WEIGHT_EMPHASIS, color=TEXT_PRIMARY)

def h2(text):
    from flet import Text
    return Text(text, size=SIZE_H2, weight=WEIGHT_EMPHASIS, color=TEXT_PRIMARY)

def subtitle(text):
    from flet import Text
    return Text(text, size=SIZE_BODY, color=TEXT_MUTED)

def divider(height=SPACE_LG):
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