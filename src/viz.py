# -*- coding: utf-8 -*-
"""
图表公共配置（matplotlib）。

调色板取自 dataviz skill 的默认校验实例（色盲安全、浅色面）。
所有分析脚本统一从这里取颜色与样式，保证图表成体系、可复现。
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 无 GUI 环境，仅落盘 PNG
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIG_DIR = PROJECT_ROOT / "dashboard" / "figures"

# 分类调色板（8 槽，按固定顺序使用，不循环）
CAT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
# 顺序单色（蓝，浅→深）
SEQ_BLUE = ["#cde2fb", "#86b6ef", "#3987e5", "#2a78d6", "#1c5cab", "#184f95", "#104281", "#0d366b"]

INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"
BASELINE = "#c3c2b7"


def setup() -> None:
    plt.rcParams.update(
        {
            "font.sans-serif": ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "axes.edgecolor": BASELINE,
            "axes.labelcolor": INK,
            "text.color": INK,
            "xtick.color": INK2,
            "ytick.color": INK2,
            "grid.color": GRID,
            "grid.linewidth": 0.7,
            "axes.grid": True,
            "axes.axisbelow": True,
            "axes.titlecolor": INK,
            "font.size": 10,
        }
    )


def save(fig, name: str) -> Path:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = FIG_DIR / name
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"[fig] 已保存 {path}")
    return path
