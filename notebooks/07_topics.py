# -*- coding: utf-8 -*-
"""
07 · 黑五大促专题与异动归因（手册 D13–D14）

结论摘要
--------
- 黑五专题：11-29 vs 平日的转化率/客单价/品类结构/新客占比。
- 数据实况：本店真实大促在 11/16–11/17（GMV 峰值 271 万），黑五 11-29 仅温和上涨。
- 异动归因：以真实大促（11/16-17）vs 前一平周（11/13-14）做量价拆解（人数×频次×均价）
  + 构成拆解（品类 / 新老客 / 价格带），输出主因 + 贡献度 + 建议。
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

PROMO_START = pd.Timestamp("2019-11-15")
PROMO_END = pd.Timestamp("2019-11-18")
BF = pd.Timestamp("2019-11-29")


def period_metrics(orders: pd.DataFrame, events: pd.DataFrame, start, end, label) -> dict:
    o = orders[(orders["event_date"] >= start) & (orders["event_date"] <= end)]
    e = events[(events["event_date"] >= start) & (events["event_date"] <= end)]
    o_valid = o[o["price_valid"]]
    gmv = o_valid["price"].sum()
    uv = e["user_id"].nunique()
    buying_users = o["user_id"].nunique()
    n_orders = len(o)

    first_pur = orders[orders["price_valid"]].groupby("user_id")["event_date"].min()
    o2 = o_valid.copy()
    o2["first"] = o2["user_id"].map(first_pur)
    new_gmv = o2.loc[o2["event_date"] == o2["first"], "price"].sum()

    # 顶层品类 GMV
    cat = o_valid.copy()
    cat["top_cat"] = cat["category_code"].str.split(".").str[0]
    top_cat = cat.groupby("top_cat")["price"].sum().sort_values(ascending=False)

    return {
        "label": label,
        "天数": (end - start).days + 1,
        "GMV": float(gmv),
        "日均GMV": float(gmv / ((end - start).days + 1)),
        "UV": int(uv),
        "购买用户数": int(buying_users),
        "订单数": int(n_orders),
        "转化率": float(buying_users / uv) if uv else np.nan,
        "客单价": float(gmv / n_orders) if n_orders else np.nan,
        "新客GMV占比": float(new_gmv / gmv) if gmv else np.nan,
        "top_cat": top_cat,
    }


def decompose_gmv(orders: pd.DataFrame, promo_start, promo_end, base_start, base_end):
    """GMV 量价拆解：GMV = 购买用户数 × 人均订单 × 客单价。"""
    def agg(s, e):
        o = orders[(orders["event_date"] >= s) & (orders["event_date"] <= e) & orders["price_valid"]]
        days = (e - s).days + 1
        u = o["user_id"].nunique()
        n = len(o)
        g = o["price"].sum()
        return u / days, n / days, g / days, g  # 日均

    ua, na, ga, _ = agg(base_start, base_end)
    ub, nb, gb, _ = agg(promo_start, promo_end)
    freq_a, freq_b = na / ua, nb / ub
    aov_a, aov_b = ga / na, gb / nb

    dgmv = gb - ga
    c_user = (ub - ua) * freq_a * aov_a
    c_freq = ub * (freq_b - freq_a) * aov_a
    c_aov = ub * freq_b * (aov_b - aov_a)
    return {
        "baseline_daily_gmv": ga, "promo_daily_gmv": gb, "delta": dgmv,
        "ua": ua, "ub": ub, "freq_a": freq_a, "freq_b": freq_b,
        "aov_a": aov_a, "aov_b": aov_b,
        "c_user": c_user, "c_freq": c_freq, "c_aov": c_aov,
    }


def category_contribution(orders: pd.DataFrame, promo_start, promo_end, base_start, base_end) -> pd.DataFrame:
    def cat_gmv(s, e):
        o = orders[(orders["event_date"] >= s) & (orders["event_date"] <= e) & orders["price_valid"]].copy()
        o["top_cat"] = o["category_code"].str.split(".").str[0]
        return o.groupby("top_cat")["price"].sum()

    days_p = (promo_end - promo_start).days + 1
    days_b = (base_end - base_start).days + 1
    p = cat_gmv(promo_start, promo_end) / days_p
    b = cat_gmv(base_start, base_end) / days_b
    d = (p - b).to_frame("delta_daily").join(p.rename("promo_daily"), how="outer").join(b.rename("base_daily"), how="outer").fillna(0)
    d = d.sort_values("delta_daily", ascending=False)
    return d


def plot_comparison(rows: list[dict]) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.6))
    labels = [r["label"] for r in rows]
    x = np.arange(len(labels))
    for ax, key, title, fmt in [
        (axes[0], "转化率", "购买转化率", "{:.1%}"),
        (axes[1], "客单价", "客单价", "{:,.0f}"),
        (axes[2], "新客GMV占比", "新客 GMV 占比", "{:.1%}"),
    ]:
        vals = [r[key] for r in rows]
        ax.bar(x, vals, color=[CAT[0], CAT[1]][:len(vals)], width=0.5)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=0)
        ax.set_title(title)
        for xi, v in zip(x, vals):
            ax.text(xi, v, fmt.format(v), ha="center", va="bottom", fontsize=8, color=INK2)
    save(fig, "fig_promo_comparison.png")


def plot_attribution(d: dict, cat: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    # 量价拆解贡献
    parts = ["人数", "频次", "均价"]
    vals = [d["c_user"], d["c_freq"], d["c_aov"]]
    axes[0].bar(parts, vals, color=[CAT[0], CAT[2], CAT[1]], width=0.5)
    axes[0].axhline(0, color=INK2, linewidth=0.8)
    axes[0].set_title("量价拆解：日均 GMV 增量贡献（人数×频次×均价）")
    axes[0].set_ylabel("日均 GMV 增量")
    # 品类贡献
    top = cat.head(6)
    axes[1].barh(top.index[::-1], top["delta_daily"][::-1], color=CAT[0], height=0.6)
    axes[1].axvline(0, color=INK2, linewidth=0.8)
    axes[1].set_title("品类构成：日均 GMV 增量 Top6")
    axes[1].set_xlabel("日均 GMV 增量")
    save(fig, "fig_attribution.png")


def main() -> None:
    setup()
    events = load_events()
    orders = load_orders()
    daily = load_daily_metrics()

    print("=" * 64)
    print("07 · 黑五大促专题与异动归因")
    print("=" * 64)

    # ---- D13 黑五专题：11-29 vs 平日 ----
    normal_mask = ~daily["event_date"].isin([pd.Timestamp(d) for d in ["2019-11-15", "2019-11-16", "2019-11-17", "2019-11-18", "2019-11-29"]])
    normal_days = daily[normal_mask]
    bf = daily[daily["event_date"] == BF]

    print("\n[黑五专题] 11-29 当日 vs 平日均值（Moscow 时区）")
    print(f"  平日(剔除大促与黑五) 日均 GMV {normal_days['gmv'].mean():,.0f} | 转化率 {(normal_days['buying_users'].sum()/normal_days['uv'].sum()):.2%} | 客单价 {(normal_days['gmv'].sum()/normal_days['n_purchases'].sum()):,.0f}")
    print(f"  黑五 11-29           日均 GMV {bf['gmv'].iloc[0]:,.0f} | 转化率 {(bf['buying_users'].iloc[0]/bf['uv'].iloc[0]):.2%} | 客单价 {(bf['gmv'].iloc[0]/bf['n_purchases'].iloc[0]):,.0f}")

    # ---- 真实大促：11/15-18 vs 平日 ----
    print("\n[大促专题] 数据实况：本店真实大促为 11/15-18（黑五 11-29 仅温和上涨）")
    promo = period_metrics(orders, events, PROMO_START, PROMO_END, "大促 11/15-18")
    normal = period_metrics(orders, events, pd.Timestamp("2019-11-08"), pd.Timestamp("2019-11-14"), "平日 11/8-14")
    bf_m = period_metrics(orders, events, BF, BF, "黑五 11-29")
    for r in [normal, promo, bf_m]:
        print(
            f"  {r['label']:<14} 日均GMV {r['日均GMV']:>10,.0f} | 转化率 {r['转化率']:>7.2%} | "
            f"客单价 {r['客单价']:>7,.0f} | 新客占比 {r['新客GMV占比']:>6.1%}"
        )

    print("\n[品类结构] 大促期 GMV 前 5 品类 vs 平日")
    pn = pd.DataFrame({
        "大促": promo["top_cat"].head(5),
        "平日": normal["top_cat"].reindex(promo["top_cat"].head(5).index).fillna(0),
    })
    print(pn.round(0).to_string())

    # ---- D14 异动归因：真实大促 11/16-17 vs 11/13-14 ----
    print("\n[异动归因] 量价拆解：11/16-17（大促）vs 11/13-14（前平周）")
    d = decompose_gmv(orders, pd.Timestamp("2019-11-16"), pd.Timestamp("2019-11-17"),
                      pd.Timestamp("2019-11-13"), pd.Timestamp("2019-11-14"))
    total = abs(d["c_user"]) + abs(d["c_freq"]) + abs(d["c_aov"])
    print(f"  日均 GMV：{d['baseline_daily_gmv']:,.0f} → {d['promo_daily_gmv']:,.0f}（+{d['delta']:,.0f}）")
    print(f"  购买用户数/日  {d['ua']:,.0f} → {d['ub']:,.0f}")
    print(f"  人均订单       {d['freq_a']:.2f} → {d['freq_b']:.2f}")
    print(f"  客单价         {d['aov_a']:,.0f} → {d['aov_b']:,.0f}")
    print(f"  贡献：人数 {d['c_user']:+,.0f} ({d['c_user']/total:+.0%}) | 频次 {d['c_freq']:+,.0f} ({d['c_freq']/total:+.0%}) | 均价 {d['c_aov']:+,.0f} ({d['c_aov']/total:+.0%})")

    print("\n[构成拆解] 品类贡献（日均 GMV 增量 Top5）")
    cat = category_contribution(orders, pd.Timestamp("2019-11-16"), pd.Timestamp("2019-11-17"),
                                pd.Timestamp("2019-11-13"), pd.Timestamp("2019-11-14"))
    for cat_name, row in cat.head(5).iterrows():
        print(f"  {cat_name:<18} +{row['delta_daily']:,.0f}/日  (大促 {row['promo_daily']:,.0f} vs 平日 {row['base_daily']:,.0f})")

    print("\n[图表]")
    plot_comparison([normal, promo, bf_m])
    plot_attribution(d, cat)


if __name__ == "__main__":
    main()
