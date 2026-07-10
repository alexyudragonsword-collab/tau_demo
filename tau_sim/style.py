"""统一图表风格：基于经过 CVD 校验的参考调色板（光模式）。

规则：分类色按固定槽位顺序使用、不循环；单轴、不使用双 y 轴；
网格线退居背景；≥2 个系列时保留图例；文字一律用墨色而非系列色。
"""

import matplotlib as mpl
import matplotlib.pyplot as plt

# 分类色（固定顺序，light 模式，已通过 CVD 相邻色距校验）
SERIES = [
    "#2a78d6",  # 1 blue
    "#1baf7a",  # 2 aqua
    "#eda100",  # 3 yellow
    "#008300",  # 4 green
    "#4a3aa7",  # 5 violet
    "#e34948",  # 6 red
    "#e87ba4",  # 7 magenta
    "#eb6834",  # 8 orange
]

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"

# 顺序色阶（blue，用于表达同一变量的量级/层数）
SEQ = ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#0d366b"]


def apply_style() -> None:
    """应用全局 matplotlib 风格（调用一次）。"""
    mpl.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "axes.edgecolor": BASELINE,
        "axes.linewidth": 0.8,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "axes.axisbelow": True,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "axes.labelcolor": INK2,
        "text.color": INK,
        "axes.titlecolor": INK,
        "font.family": "sans-serif",
        "font.sans-serif": ["Noto Sans CJK SC", "WenQuanYi Zen Hei",
                            "DejaVu Sans", "sans-serif"],
        "axes.unicode_minus": False,
        "lines.linewidth": 2.0,
        "lines.markersize": 6,
        "legend.frameon": False,
        "legend.fontsize": 9,
        "axes.titlesize": 12,
        "axes.labelsize": 10,
        "figure.dpi": 110,
        "savefig.dpi": 160,
        "savefig.bbox": "tight",
        "axes.prop_cycle": mpl.cycler(color=SERIES),
    })


def new_fig(w: float = 7.0, h: float = 4.2):
    """标准尺寸画布。"""
    return plt.subplots(figsize=(w, h))
