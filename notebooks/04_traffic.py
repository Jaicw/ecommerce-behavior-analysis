# -*- coding: utf-8 -*-
"""
04 · 流量与转化（手册 D7–D8）

结论摘要
--------
- 流量：日 PV/UV 趋势、分时分布（本地时区）、session 粒度指标、流量异常日识别。
- 漏斗：view→cart→purchase 双口径（严格时序漏斗 vs 独立转化率），
  购物车放弃用「加购但未购买」口径（数据无 remove_from_cart）。
- 产出 3 张图到 dashboard/figures/。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from loaders import load_events, load_orders, load_daily_metrics
from viz import CAT, INK2, setup, save

import matplotlib.pyplot as plt


def traffic_anomaly(daily: pd.DataFrame) -> pd.DataFrame:
    """用 z-score 识别 PV 异常日（|z|>2）。"""
    d = daily.copy()
    d["pv_z"] = (d["pv"] - d["pv"].mean()) / d["pv"].std()
    d["uv_z"] = (d["uv"] - d["uv"].mean()) / d["uv"].std()
    return d


def session_metrics(events: pd.DataFrame) -> dict:
    n_sessions = events["user_session"].nunique()
    n_session_with_purchase = events[events["event_type"] == "purchase"]["user_session"].nunique()
    return {
        "会话数": int(n_sessions),
        "含购买会话数": int(n_session_with_purchase),
        "会话转化率(含购买会话占比)": float(n_session_with_purchase / n_sessions),
        "平均每会话事件数": float(len(events) / n_sessions),
    }


def funnel(events: pd.DataFrame) -> dict:
    """双口径漏斗（用户粒度，用首次事件时间做严格时序）。"""
    u = events.copy()
    g = u.groupby("user_id")["event_time"]
    ft = u.assign(
        v=u["event_time"].where(u["event_type"] == "view"),
        c=u["event_time"].where(u["event_type"] == "cart"),
        p=u["event_time"].where(u["event_type"] == "purchase"),
    ).groupby("user_id")[["v", "c", "p"]].min()

    n_view = ft["v"].notna().sum()
    n_cart_indep = ft["c"].notna().sum()
    n_purchase_indep = ft["p"].notna().sum()

    # 严格时序：cart 晚于 view，purchase 晚于 cart（含直接购买被排除）
    n_cart_strict = ((ft["c"].notna()) & (ft["v"].notna()) & (ft["c"] >= ft["v"])).sum()
    n_purchase_strict = (
        (ft["p"].notna()) & (ft["c"].notna()) & (ft["v"].notna())
        & (ft["c"] >= ft["v"]) & (ft["p"] >= ft["c"])
    ).sum()

    # 购物车放弃：加购但未购买（含时序要求 p>=c）
    n_cart_purchased = ((ft["c"].notna()) & (ft["p"].notna()) & (ft["p"] >= ft["c"])).sum()
    n_cart_abandoned = int(n_cart_indep - n_cart_purchased)

    return {
        "n_view": int(n_view),
        "n_cart_indep": int(n_cart_indep),
        "n_purchase_indep": int(n_purchase_indep),
        "n_cart_strict": int(n_cart_strict),
        "n_purchase_strict": int(n_purchase_strict),
        "n_cart_purchased": int(n_cart_purchased),
        "n_cart_abandoned": n_cart_abandoned,
        "cart_abandon_rate": float(n_cart_abandoned / n_cart_indep),
        "indep_cart_rate": float(n_cart_indep / n_view),
        "indep_purchase_rate": float(n_purchase_indep / n_view),
        "strict_cart_rate": float(n_cart_strict / n_view),
        "strict_purchase_rate": float(n_purchase_strict / n_view),
    }


def plot_daily_traffic(daily: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
    daily = daily.sort_values("event_date")
    x = range(len(daily))
    axes[0].plot(x, daily["pv"], color=CAT[0], linewidth=2)
    axes[0].set_ylabel("PV（事件数）")
    axes[0].set_title("日流量趋势（PV / UV）")
    axes[1].plot(x, daily["uv"], color=CAT[1], linewidth=2)
    axes[1].set_ylabel("UV（去重用户数）")
    axes[1].set_xticks(x[::3])
    axes[1].set_xticklabels([str(d)[5:] for d in daily["event_date"]][::3], rotation=0)
    save(fig, "fig_daily_traffic.png")


def plot_hourly(events: pd.DataFrame) -> None:
    ev = events.copy()
    view_h = ev[ev["event_type"] == "view"]["event_hour"].value_counts(normalize=True).sort_index()
    pur_h = ev[ev["event_type"] == "purchase"]["event_hour"].value_counts(normalize=True).sort_index()
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(view_h.index, view_h.values * 100, color=CAT[0], linewidth=2, marker="o", markersize=4, label="浏览 view")
    ax.plot(pur_h.index, pur_h.values * 100, color=CAT[1], linewidth=2, marker="o", markersize=4, label="购买 purchase")
    ax.set_xlabel("本地小时（Asia/Shanghai）")
    ax.set_ylabel("占比 %")
    ax.set_title("分时分布（本地时区，占各自事件总量）")
    ax.legend(frameon=False)
    save(fig, "fig_hourly_distribution.png")


def plot_funnel(f: dict) -> None:
    stages = ["浏览 view", "加购 cart", "购买 purchase"]
    strict = [f["n_view"], f["n_cart_strict"], f["n_purchase_strict"]]
    indep = [f["n_view"], f["n_cart_indep"], f["n_purchase_indep"]]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    for ax, data, title in [(axes[0], strict, "严格时序漏斗"), (axes[1], indep, "独立转化率")]:
        y = np.arange(len(stages))[::-1]
        widths = np.array(data) / max(data)
        ax.barh(y, widths, color=CAT[0], height=0.5, alpha=0.85)
        ax.set_yticks(y)
        ax.set_yticklabels(stages)
        ax.set_xlim(0, 1.05)
        ax.set_title(title)
        for yi, w, d in zip(y, widths, data):
            ax.text(w + 0.02, yi, f"{d:,}", va="center", color=INK2, fontsize=9)
    save(fig, "fig_funnel.png")


def main() -> None:
    setup()
    events = load_events()
    daily = load_daily_metrics()

    print("=" * 64)
    print("04 · 流量与转化")
    print("=" * 64)

    print("\n[流量] 日粒度概览")
    print(f"  日均 PV {daily['pv'].mean():,.0f} | 日均 UV {daily['uv'].mean():,.0f} | 日均 GMV {daily['gmv'].mean():,.0f}")
    anom = traffic_anomaly(daily)
    high = anom[anom["pv_z"] > 2].sort_values("event_date")
    print("  流量异常日（PV z>2）：")
    for _, r in high.iterrows():
        print(f"    {str(r['event_date'])[:10]}  PV={r['pv']:,} (z={r['pv_z']:.1f})  GMV={r['gmv']:,.0f}  购买={r['n_purchases']:,}")

    print("\n[分时] 本地时区峰值")
    view_h = events[events["event_type"] == "view"]["event_hour"]
    pur_h = events[events["event_type"] == "purchase"]["event_hour"]
    print(f"  浏览峰值小时（本地）: {view_h.mode().tolist()} 点")
    print(f"  购买峰值小时（本地）: {pur_h.mode().tolist()} 点")

    print("\n[session 粒度]")
    for k, v in session_metrics(events).items():
        print(f"  {k:<22}: {v:,.2f}" if isinstance(v, float) else f"  {k:<22}: {v:,}")

    print("\n[漏斗] view → cart → purchase 双口径（用户粒度）")
    f = funnel(events)
    print(f"  浏览用户        : {f['n_view']:,}")
    print(f"  加购用户        : 独立 {f['n_cart_indep']:,} | 严格 {f['n_cart_strict']:,}")
    print(f"  购买用户        : 独立 {f['n_purchase_indep']:,} | 严格 {f['n_purchase_strict']:,}")
    print(f"  独立口径 加购率 : {f['indep_cart_rate']:.2%} | 购买率(view→purchase) {f['indep_purchase_rate']:.2%}")
    print(f"  严格口径 加购率 : {f['strict_cart_rate']:.2%} | 购买率(view→purchase) {f['strict_purchase_rate']:.2%}")
    print(f"  直接购买用户(未加购) : {f['n_purchase_indep'] - f['n_purchase_strict']:,}")
    print(f"  购物车放弃      : 加购未购买 {f['n_cart_abandoned']:,} | 放弃率 {f['cart_abandon_rate']:.2%}")

    print("\n[图表]")
    plot_daily_traffic(daily)
    plot_hourly(events)
    plot_funnel(f)


if __name__ == "__main__":
    main()
