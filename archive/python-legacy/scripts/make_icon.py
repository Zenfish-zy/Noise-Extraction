"""生成应用图标（声波 + 向下指向，寓意"楼上传下的噪音"）。

运行:  uv run python scripts/make_icon.py
输出:  noise_evidence/assets/icon.ico  (多尺寸)
       noise_evidence/assets/icon.png  (256, 预览用)

设计语言与界面一致：深蓝灰底 + 青蓝强调色，圆角现代质感。
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

ASSETS = Path(__file__).resolve().parent.parent / "noise_evidence" / "assets"

# 配色（与 gui/style.py 呼应）
BG_TOP = (32, 38, 52)
BG_BOTTOM = (18, 22, 32)
ACCENT = (47, 125, 246)      # 主青蓝
ACCENT_HI = (90, 170, 255)   # 高亮
ARROW = (120, 200, 255)


def _rounded_mask(size: int, radius_ratio: float = 0.22) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    r = int(size * radius_ratio)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=255)
    return mask


def _vertical_gradient(size: int, top, bottom) -> Image.Image:
    grad = Image.new("RGB", (size, size), top)
    px = grad.load()
    for y in range(size):
        t = y / max(1, size - 1)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        for x in range(size):
            px[x, y] = (r, g, b)
    return grad


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def render(size: int = 512) -> Image.Image:
    base = _vertical_gradient(size, BG_TOP, BG_BOTTOM)
    draw = ImageDraw.Draw(base, "RGBA")

    cx = size / 2
    # --- 向下箭头（楼上传下的噪音）---
    aw = size * 0.26
    ay_top = size * 0.13
    ay_tip = size * 0.30
    draw.line([(cx, ay_top), (cx, ay_tip)], fill=ARROW, width=max(2, size // 64))
    draw.line(
        [(cx - aw / 2, ay_tip - aw / 2), (cx, ay_tip)],
        fill=ARROW, width=max(2, size // 64),
    )
    draw.line(
        [(cx + aw / 2, ay_tip - aw / 2), (cx, ay_tip)],
        fill=ARROW, width=max(2, size // 64),
    )

    # --- 声波柱（中部，高度按余弦包络，模拟噪音波形）---
    n_bars = 9
    bar_w = size * 0.052
    span = size * 0.62
    gap = (span - n_bars * bar_w) / (n_bars - 1)
    x0 = cx - span / 2
    mid_y = size * 0.60
    max_h = size * 0.30
    # 高度模式：中间高两边低，带点不规则（噪音感）
    pattern = [0.35, 0.6, 0.45, 0.9, 0.7, 1.0, 0.5, 0.75, 0.4]
    for i in range(n_bars):
        h = max_h * pattern[i]
        x = x0 + i * (bar_w + gap)
        col = _lerp(ACCENT, ACCENT_HI, pattern[i])
        draw.rounded_rectangle(
            [x, mid_y - h / 2, x + bar_w, mid_y + h / 2],
            radius=bar_w / 2,
            fill=col + (255,),
        )

    # 应用圆角遮罩
    mask = _rounded_mask(size)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(base, (0, 0), mask)
    return out


def render_check(size: int = 64, color=(255, 255, 255, 255)) -> Image.Image:
    """生成透明底的白色对勾，供复选框选中态使用。

    高分辨率绘制再缩放，边缘平滑（不依赖 QtSvg 插件，打包更稳）。
    """
    ss = size * 4  # 超采样
    img = Image.new("RGBA", (ss, ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    w = max(2, int(ss * 0.12))
    # 对勾三点（相对坐标），位置经过视觉微调使其居中偏上
    p1 = (ss * 0.22, ss * 0.52)
    p2 = (ss * 0.42, ss * 0.72)
    p3 = (ss * 0.78, ss * 0.30)
    d.line([p1, p2], fill=color, width=w, joint="curve")
    d.line([p2, p3], fill=color, width=w, joint="curve")
    # 圆角端点
    r = w / 2
    for cx, cy in (p1, p2, p3):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    return img.resize((size, size), Image.LANCZOS)


def render_arrow(
    size: int = 32, direction: str = "down", color=(110, 104, 91, 255)
) -> Image.Image:
    """生成透明底的小箭头（▲/▼），供 SpinBox/ComboBox 按钮使用。

    超采样后缩放，边缘平滑；不依赖 QtSvg，打包更稳（与 render_check 同思路）。
    """
    ss = size * 4
    img = Image.new("RGBA", (ss, ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 等腰三角，居中，留出四周边距
    m = ss * 0.30          # 上下边距
    w = ss * 0.22          # 左右边距
    if direction == "down":
        pts = [(w, m), (ss - w, m), (ss / 2, ss - m)]
    else:  # up
        pts = [(ss / 2, m), (ss - w, ss - m), (w, ss - m)]
    d.polygon(pts, fill=color)
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    master = render(512)
    png_path = ASSETS / "icon.png"
    master.resize((256, 256), Image.LANCZOS).save(png_path)

    ico_path = ASSETS / "icon.ico"
    sizes = [16, 24, 32, 48, 64, 128, 256]
    master.save(ico_path, sizes=[(s, s) for s in sizes])
    print("written:", png_path)
    print("written:", ico_path)

    # 复选框对勾（白色 + 半透明灰，供选中/悬停态）
    check_path = ASSETS / "check.png"
    render_check(64, (255, 255, 255, 255)).save(check_path)
    print("written:", check_path)

    # SpinBox / ComboBox 的上下与下拉箭头（黛色，与文字呼应）
    arrow_col = (110, 104, 91, 255)  # #6E685B 黛
    for name, direction in (("arrow_down", "down"), ("arrow_up", "up")):
        p = ASSETS / f"{name}.png"
        render_arrow(32, direction, arrow_col).save(p)
        print("written:", p)


if __name__ == "__main__":
    main()
