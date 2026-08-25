# -*- coding: utf-8 -*-
"""
06 · RFM 用户价值分层（手册 D11–D12）

结论摘要
--------
- R = 距窗口末天数（越小越近）、F = 购买次数、M = 累计 GMV。
- 五分位打分 1–5（R 反向），均值二分（≥3 为高）→ 8 组人群。
- 输出各组人数 / GMV 占比 / 人均指标 + 运营建议；覆盖购买用户（UV 的 11.9%）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from loaders import load_orders, load_events
from viz import CAT, INK2, setup, save

import matplotlib.pyplot as plt

SEGMENTS = {
    "高,高,高": "重要价值客户",
    "高,高,低": "一般价值客户",
    "高,低,高": "重要保持客户",
    "高,低,低": "新客户",
    "低,高,高": "重要挽留客户",
    "低,高,低": "一般保持客户",
    "低,低,高": "重要发展客户",
    "低,低,低": "流失客户",
}

ADVICE = {
    "重要价值客户": "重点维系：会员权益/专属客服，防流失",
    "一般价值客户": "提升客单：捆绑销售/满减券刺激消费金额",
    "重要保持客户": "唤醒频次：订阅/复购提醒，提升购买频率",
    "新客户": "首单后 7 天促二次转化（新客券/引导）",
    "重要挽留客户": "优先挽回：大额召回券/专属折扣，防止流失",
    "一般保持客户": "低成本触达：权益召回，控制营销预算",
    "重要发展客户": "提高粘性：近期促活，推动再购",
    "流失客户": "弱触达或放弃，控制成本",
}


def score_quintile(s: pd.Series, reverse: bool = False) -> pd.Series:
    if reverse:
        s = -s
    r = s.rank(method="first", pct=True)
    return pd.cut(r, bins=[0, 0.2, 0.4, 0.6, 0.8, 1.0], labels=[1, 2, 3, 4, 5], include_lowest=True).astype(int)


def build_rfm(orders: pd.DataFrame) -> pd.DataFrame:
    o = orders[orders["price_valid"]].copy()
    ref = orders["event_date"].max()
    g = o.groupby("user_id")
    rfm = pd.DataFrame({
        "R": (ref - g["event_date"].max()).dt.days,
        "F": g.size(),
        "M": g["price"].sum(),
    }).reset_index()
    rfm["R_score"] = score_quintile(rfm["R"], reverse=True)
    rfm["F_score"] = score_quintile(rfm["F"], reverse=False)
    rfm["M_score"] = score_quintile(rfm["M"], reverse=False)

    def hi(s):
        return np.where(s >= 3, "高", "低")

    rfm["seg_key"] = list(zip(hi(rfm["R_score"]), hi(rfm["F_score"]), hi(rfm["M_score"])))
    rfm["segment"] = rfm["seg_key"].map(lambda k: SEGMENTS[",".join(k)])
    return rfm


def segment_summary(rfm: pd.DataFrame) -> pd.DataFrame:
    total_gmv = rfm["M"].sum()
    total_users = len(rfm)
    rows = []
    for seg, grp in rfm.groupby("segment"):
        rows.append({
            "segment": seg,
            "人数": len(grp),
            "人数占比": len(grp) / total_users,
            "GMV": grp["M"].sum(),
            "GMV占比": grp["M"].sum() / total_gmv,
            "人均GMV": grp["M"].mean(),
            "人均购买次数": grp["F"].mean(),
        })
    s = pd.DataFrame(rows).sort_values("GMV占比", ascending=False).reset_index(drop=True)
    return s


def plot_segments(s: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)
    s = s.sort_values("GMV占比")
    y = range(len(s))
    axes[0].barh(list(y), s["人数占比"] * 100, color=CAT[0], height=0.6)
    axes[0].set_yticks(list(y))
    axes[0].set_yticklabels(s["segment"])
    axes[0].set_xlabel("人数占比 %")
    axes[0].set_title("RFM 八组人数占比")
    axes[1].barh(list(y), s["GMV占比"] * 100, color=CAT[1], height=0.6)
    axes[1].set_xlabel("GMV 占比 %")
    axes[1].set_title("RFM 八组 GMV 占比")
    for yi, v in zip(y, s["GMV占比"] * 100):
        axes[1].text(v + 0.3, yi, f"{v:.1f}%", va="center", color=INK2, fontsize=8)
    save(fig, "fig_rfm_segments.png")


def main() -> None:
    setup()
    orders = load_orders()
    events = load_events()

    rfm = build_rfm(orders)
    s = segment_summary(rfm)

    print("=" * 64)
    print("06 · RFM 用户价值分层")
    print("=" * 64)
    uv = events["user_id"].nunique()
    buying_users = orders["user_id"].nunique()
    print(f"\n[口径] RFM 覆盖购买用户 {len(rfm):,}（占 UV {buying_users / uv:.1%}），窗口末 = {orders['event_date'].max().date()}")

    print("\n[原始值分布] R(距末天数) / F(购买次数) / M(GMV)")
    for c in ["R", "F", "M"]:
        print(f"  {c}: 中位 {rfm[c].median():.1f} | 均值 {rfm[c].mean():.1f} | P90 {rfm[c].quantile(0.9):.1f}")

    print("\n[八组人群]")
    print(f"  {'人群':<12}{'人数':>8}{'人数占比':>9}{'GMV':>12}{'GMV占比':>9}{'人均GMV':>10}{'人均次数':>9}")
    for _, r in s.iterrows():
        print(
            f"  {r['segment']:<12}{r['人数']:>8,}{r['人数占比']:>8.1%}{r['GMV']:>12,.0f}"
            f"{r['GMV占比']:>8.1%}{r['人均GMV']:>10,.0f}{r['人均购买次数']:>9.2f}"
        )

    print("\n[运营建议]")
    for _, r in s.iterrows():
        print(f"  {r['segment']:<12} {ADVICE[r['segment']]}")

    print("\n[图表]")
    plot_segments(s)


if __name__ == "__main__":
    main()
