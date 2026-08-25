# -*- coding: utf-8 -*-
"""
05 · 留存与复购（手册 D9–D10）

结论摘要
--------
- 留存：以窗口内首次出现日为 D0（活跃留存口径），次日/3日/7日留存 + 周 cohort 热力矩阵。
- 复购：购买≥2次用户占比、购买间隔分布、新客 GMV 占比趋势。
- 产出 2 张图到 dashboard/figures/。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from loaders import load_events, load_orders
from viz import CAT, INK2, SEQ_BLUE, setup, save

import matplotlib.pyplot as plt


def retention_headline(events: pd.DataFrame) -> dict:
    """次日/3日/7日活跃留存（D0=首次出现日，offset=1/3/7，按窗口内可观测用户计算）。"""
    ev = events[["user_id", "event_date"]].drop_duplicates()
    first = ev.groupby("user_id")["event_date"].min().rename("first_seen")
    active = ev.copy()
    active["_keep"] = True
    active_pivot = active.groupby(["user_id", "event_date"]).size().reset_index(name="_n")

    first_df = first.reset_index()
    max_date = ev["event_date"].max()
    out = {}
    for label, offset in [("次日", 1), ("3日", 3), ("7日", 7)]:
        eligible = first_df[first_df["first_seen"] <= max_date - pd.Timedelta(days=offset)]
        if eligible.empty:
            out[label] = np.nan
            continue
        target = eligible.copy()
        target["target_date"] = target["first_seen"] + pd.Timedelta(days=offset)
        merged = target.merge(active_pivot, left_on=["user_id", "target_date"], right_on=["user_id", "event_date"], how="left")
        out[label] = float(merged["_n"].notna().mean())
    return out


def weekly_cohort(events: pd.DataFrame) -> pd.DataFrame:
    """周 cohort 留存矩阵（cohort=首次出现所在周，周一为周起点）。"""
    ev = events[["user_id", "event_date"]].drop_duplicates()
    ev["week_start"] = ev["event_date"] - pd.to_timedelta(ev["event_date"].dt.weekday, unit="d")
    first = ev.groupby("user_id")["week_start"].min().rename("cohort")
    active_weeks = ev[["user_id", "week_start"]].drop_duplicates()
    m = first.reset_index().merge(active_weeks, on="user_id", suffixes=("", "_active"))
    m["offset_week"] = (m["week_start"] - m["cohort"]).dt.days // 7
    m = m[m["offset_week"] >= 0]
    cohorts = sorted(m["cohort"].unique())
    last_week = m["week_start"].max()
    matrix = pd.DataFrame(index=[pd.Timestamp(c).strftime("%m-%d") for c in cohorts])
    for c in cohorts:
        sub = m[m["cohort"] == c]
        size = sub["user_id"].nunique()
        for w in range(0, 5):
            if c + pd.Timedelta(days=7 * w) > last_week:
                matrix.loc[pd.Timestamp(c).strftime("%m-%d"), f"W{w}"] = np.nan  # 尚未可观测
                continue
            retained = sub[sub["offset_week"] == w]["user_id"].nunique()
            matrix.loc[pd.Timestamp(c).strftime("%m-%d"), f"W{w}"] = retained / size
    return matrix.astype(float)


def repurchase(orders: pd.DataFrame) -> dict:
    """复购指标。"""
    n_purchases = orders.groupby("user_id").size()
    buying_users = n_purchases.shape[0]
    repurchase_users = int((n_purchases >= 2).sum())

    # 购买间隔（天）：相邻两次购买的时间差
    o = orders.sort_values(["user_id", "event_time"])
    o["prev"] = o.groupby("user_id")["event_time"].shift(1)
    gaps = (o["event_time"] - o["prev"]).dt.total_seconds() / 86400.0
    gaps = gaps[gaps > 0].dropna()

    return {
        "购买用户数": int(buying_users),
        "复购用户数(≥2次)": repurchase_users,
        "复购率": float(repurchase_users / buying_users),
        "平均购买间隔(天)": float(gaps.mean()),
        "中位购买间隔(天)": float(gaps.median()),
        "gaps": gaps,
    }


def new_customer_gmv_trend(orders: pd.DataFrame) -> pd.DataFrame:
    """每日新客 GMV 占比趋势（新客=首次购买发生在当日）。"""
    o = orders[orders["price_valid"]].copy()
    first = o.groupby("user_id")["event_date"].min().rename("first_purchase_date")
    o = o.merge(first, on="user_id", how="left")
    o["is_new"] = o["event_date"] == o["first_purchase_date"]
    daily = o.groupby("event_date").agg(
        total_gmv=("price", "sum"),
        new_gmv=("price", lambda s: s[o.loc[s.index, "is_new"]].sum()),
    )
    daily["new_gmv_share"] = daily["new_gmv"] / daily["total_gmv"]
    return daily


def plot_cohort(matrix: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    data = matrix.values
    im = ax.imshow(data, cmap=plt.matplotlib.colors.LinearSegmentedColormap.from_list("seq", SEQ_BLUE[:7]), vmin=0, vmax=1)
    ax.set_xticks(range(matrix.shape[1]))
    ax.set_xticklabels([f"W{i}" for i in range(matrix.shape[1])])
    ax.set_yticks(range(matrix.shape[0]))
    ax.set_yticklabels(matrix.index)
    ax.set_xlabel("相对 cohort 周数")
    ax.set_ylabel("cohort（首次出现周）")
    ax.set_title("周 cohort 活跃留存热力")
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            v = data[i, j]
            ax.text(j, i, f"{v:.0%}", ha="center", va="center", color="white" if v > 0.6 else INK2, fontsize=8)
    fig.colorbar(im, ax=ax, label="留存率")
    save(fig, "fig_cohort_heatmap.png")


def plot_repurchase_interval(gaps: pd.Series) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(gaps[gaps <= 30], bins=30, color=CAT[0], edgecolor="white")
    ax.set_xlabel("购买间隔（天）")
    ax.set_ylabel("次数")
    ax.set_title("复购用户购买间隔分布（≤30 天）")
    save(fig, "fig_repurchase_interval.png")


def main() -> None:
    setup()
    events = load_events()
    orders = load_orders()

    print("=" * 64)
    print("05 · 留存与复购")
    print("=" * 64)

    print("\n[留存] 次日/3日/7日活跃留存（D0=首次出现日）")
    for k, v in retention_headline(events).items():
        print(f"  {k}留存 : {v:.2%}")

    print("\n[留存] 周 cohort 矩阵")
    matrix = weekly_cohort(events)
    print(matrix.round(3).to_string())

    print("\n[复购]")
    rp = repurchase(orders)
    print(f"  购买用户数 {rp['购买用户数']:,} | 复购用户数 {rp['复购用户数(≥2次)']:,} | 复购率 {rp['复购率']:.2%}")
    print(f"  平均购买间隔 {rp['平均购买间隔(天)']:.1f} 天 | 中位 {rp['中位购买间隔(天)']:.1f} 天")

    print("\n[新客 GMV 占比趋势]")
    nc = new_customer_gmv_trend(orders)
    print(f"  全月新客 GMV 占比 : {nc['new_gmv'].sum() / nc['total_gmv'].sum():.2%}")
    print(f"  首周新客占比均值 : {nc.iloc[:7]['new_gmv_share'].mean():.2%}")
    print(f"  大促周(11/15-17)新客占比 : {nc.loc[nc.index.astype(str).isin(['2019-11-15','2019-11-16','2019-11-17'])]['new_gmv_share'].mean():.2%}")

    print("\n[图表]")
    plot_cohort(matrix)
    plot_repurchase_interval(rp["gaps"])


if __name__ == "__main__":
    main()
