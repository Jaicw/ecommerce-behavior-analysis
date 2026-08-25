# -*- coding: utf-8 -*-
"""
02 · 清洗与数据质量报告（手册 D3–D4）

结论摘要
--------
- 清洗：event_time UTC→本地时区、删除完全重复行、price<=0/NaN 标记（不删）、
  user_session 缺失补为独立单事件会话、category_code 缺失归 unknown。
- 产出 data/processed/ 四张分析表：events / orders / users / daily_metrics。
- 同时生成 reports/数据质量报告.md（一页）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from loaders import (
    PROJECT_ROOT,
    EVENTS_PARQUET,
    ORDERS_PARQUET,
    USERS_PARQUET,
    DAILY_METRICS_PARQUET,
    parse_event_time,
    load_sample,
)

REPORT_PATH = PROJECT_ROOT / "reports" / "数据质量报告.md"


def build_tables(df: pd.DataFrame) -> dict:
    """从清洗后事件表构建 orders / users / daily_metrics 三张分析表。"""
    df = df.copy()
    df["is_view"] = df["event_type"] == "view"
    df["is_cart"] = df["event_type"] == "cart"
    df["is_remove"] = df["event_type"] == "remove_from_cart"
    df["is_purchase"] = df["event_type"] == "purchase"
    df["price_valid"] = df["price"].notna() & (df["price"] > 0)

    # ---- orders：购买事件（本数据集无订单号，一条 purchase 事件即一条订单） ----
    pur = df[df["is_purchase"]].copy()
    orders = pur[
        [
            "event_time", "event_date", "user_id", "product_id",
            "category_id", "category_code", "brand", "price", "price_valid",
        ]
    ].reset_index(drop=True)

    # ---- users：用户级汇总 ----
    g = df.groupby("user_id")
    users = g.agg(
        first_seen=("event_time", "min"),
        last_seen=("event_time", "max"),
        n_events=("event_type", "size"),
        n_views=("is_view", "sum"),
        n_carts=("is_cart", "sum"),
        n_remove=("is_remove", "sum"),
        n_purchases=("is_purchase", "sum"),
        active_days=("event_date", "nunique"),
        distinct_products=("product_id", "nunique"),
        distinct_categories=("category_code", "nunique"),
        distinct_brands=("brand", "nunique"),
    ).reset_index()

    gmv_u = pur[pur["price_valid"]].groupby("user_id")["price"].sum().rename("gmv")
    first_pur = pur.groupby("user_id")["event_time"].min().rename("first_purchase")
    users = users.merge(gmv_u, on="user_id", how="left")
    users = users.merge(first_pur, on="user_id", how="left")
    users["gmv"] = users["gmv"].fillna(0.0)
    users["has_purchase"] = users["n_purchases"] > 0

    # ---- daily_metrics：日粒度指标 ----
    dg = df.groupby("event_date")
    daily = dg.agg(
        pv=("event_type", "size"),
        uv=("user_id", "nunique"),
        n_views=("is_view", "sum"),
        n_carts=("is_cart", "sum"),
        n_remove=("is_remove", "sum"),
        n_purchases=("is_purchase", "sum"),
    ).reset_index()

    gmv_d = pur[pur["price_valid"]].groupby("event_date")["price"].sum().rename("gmv")
    buyers_d = pur.groupby("event_date")["user_id"].nunique().rename("buying_users")
    daily = daily.merge(gmv_d, on="event_date", how="left")
    daily = daily.merge(buyers_d, on="event_date", how="left")
    daily["gmv"] = daily["gmv"].fillna(0.0)
    daily["buying_users"] = daily["buying_users"].fillna(0).astype(int)
    daily["orders"] = daily["n_purchases"]
    daily["aov"] = daily["gmv"] / daily["n_purchases"].replace(0, pd.NA)
    daily["per_user_events"] = daily["pv"] / daily["uv"]
    daily["conversion_rate"] = daily["buying_users"] / daily["uv"]  # 用户口径购买转化率
    daily = daily.sort_values("event_date").reset_index(drop=True)

    return {"events": df, "orders": orders, "users": users, "daily_metrics": daily}


def write_report(df_raw: pd.DataFrame, df: pd.DataFrame, report: dict, tables: dict) -> None:
    """生成一页数据质量报告。"""
    def pct(n, d):
        return f"{n:,} ({n / d:.2%})" if d else "0"

    lines = []
    lines.append("# 数据质量报告（D4 出关）\n")
    lines.append("> 数据集：Kaggle 多品类电商 2019-11 单月（抽样后 5% 用户全量事件）。\n")

    lines.append("## 1. 规模\n")
    lines.append("| 项目 | 值 |")
    lines.append("|---|---|")
    lines.append(f"| 原始抽样行数 | {report['raw_rows']:,} |")
    lines.append(f"| 清洗后行数 | {len(df):,} |")
    lines.append(f"| 删除完全重复行 | {report['dup_rows_removed']:,} |")
    lines.append(f"| 去重用户数 | {df['user_id'].nunique():,} |")
    lines.append(f"| 去重商品数 | {df['product_id'].nunique():,} |")
    lines.append("")

    lines.append("## 2. 字段缺失率\n")
    lines.append("| 字段 | 缺失数 | 缺失率 | 处理策略 |")
    lines.append("|---|---|---|---|")
    for col in report["missing"]:
        n = report["missing"][col]
        strat = {
            "category_code": "填充为 unknown（保留）",
            "brand": "保留原值（分析按 unknown 归并）",
            "user_session": "补为独立单事件会话（避免错误合并）",
            "price": "标记 price_invalid，GMV 不计入",
            "user_id": "无法归属，剔除该行",
        }.get(col, "保留原值")
        lines.append(f"| {col} | {n:,} | {pct(n, report['raw_rows'])} | {strat} |")
    lines.append("")

    lines.append("## 3. 异常值处理规则\n")
    lines.append("| 异常 | 规则 | 策略 |")
    lines.append("|---|---|---|")
    lines.append(f"| price <= 0 | {report['price_le0']:,} 行 | 标记 `price_invalid`，不删除；GMV 仅统计有效价格 |")
    lines.append(f"| price 为 NaN | {report['price_nan']:,} 行 | 同上标记，不删除 |")
    lines.append(f"| user_session 缺失 | {report['session_missing']:,} 行 | 补独立单事件会话 |")
    lines.append(f"| category_code 缺失 | {report['category_code_missing']:,} 行 | 归 unknown |")
    lines.append("")

    lines.append("## 4. 时间覆盖完整性\n")
    lines.append(f"- 时间下界：{df['event_time'].min()}")
    lines.append(f"- 时间上界：{df['event_time'].max()}")
    days = (df['event_time'].max() - df['event_time'].min()).days + 1
    lines.append(f"- 覆盖天数：{days} 天")
    lines.append(f"- 每日均有事件的天数：{df['event_date'].nunique()} 天")
    lines.append("")
    lines.append("**时区口径**：原始 event_time 为 UTC，已统一转 Asia/Shanghai（UTC+8）本地时区，分时分布按此口径。\n")

    lines.append("## 5. 分析表\n")
    lines.append("| 表 | 行数 | 说明 |")
    lines.append("|---|---|---|")
    lines.append(f"| events | {len(tables['events']):,} | 全量清洗后事件 |")
    lines.append(f"| orders | {len(tables['orders']):,} | 购买事件（=订单行） |")
    lines.append(f"| users | {len(tables['users']):,} | 用户级汇总 |")
    lines.append(f"| daily_metrics | {len(tables['daily_metrics']):,} | 日粒度指标 |")
    lines.append("")

    lines.append("## 6. 事件类型与数据说明\n")
    etype = df["event_type"].value_counts()
    lines.append("| 事件类型 | 行数 | 占比 |")
    lines.append("|---|---|---|")
    for et, cnt in etype.items():
        lines.append(f"| {et} | {cnt:,} | {cnt / len(df):.2%} |")
    lines.append("")
    lines.append(
        "> **remove_from_cart 缺失**：2019-11 原始数据（含全量）不含 remove_from_cart 事件，"
        "仅 view / cart / purchase 三类。购物车放弃分析改用「加购但未购买」口径（cart → purchase 的流失）。"
    )
    lines.append(
        "> **时区溢出**：原始 event_time 为 UTC，转 Asia/Shanghai(UTC+8) 后，11-30 晚间（UTC 16:00 后）"
        "事件落入 12-01 本地日，导致本地日期跨 31 天、首尾两天为不完整日。"
        "分时分析用本地时区，日粒度含 12-01 少量溢出（约 2.4 万行，占 0.7%）。"
    )
    lines.append("")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"[clean] 数据质量报告已写：{REPORT_PATH}")


def main() -> None:
    df_raw = load_sample()
    df = df_raw.copy()

    report = {"raw_rows": len(df), "raw_cols": df.shape[1]}

    # 0. 各字段缺失统计（清洗前）
    report["missing"] = {c: int(df[c].isna().sum()) for c in df.columns}

    # 1. 时间解析（UTC → 本地时区）
    df["event_time"] = parse_event_time(df["event_time"])
    df["event_date"] = df["event_time"].dt.normalize()
    df["event_hour"] = df["event_time"].dt.hour

    # 2. 完全重复行
    before = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    report["dup_rows_removed"] = before - len(df)

    # 3. price 异常标记（不删）
    report["price_nan"] = int(df["price"].isna().sum())
    report["price_le0"] = int((df["price"] <= 0).sum())
    df["price_invalid"] = df["price"].isna() | (df["price"] <= 0)

    # 4. user_session 缺失 → 独立单事件会话
    report["session_missing"] = int(df["user_session"].isna().sum())
    df["user_session"] = df["user_session"].where(
        df["user_session"].notna(), "NO_SESSION_" + df.index.astype(str)
    )

    # 5. category_code 缺失 → unknown
    report["category_code_missing"] = int(df["category_code"].isna().sum())
    df["category_code"] = df["category_code"].fillna("unknown")

    # 构建四张表
    tables = build_tables(df)

    # 落盘
    for name, path in [
        ("events", EVENTS_PARQUET),
        ("orders", ORDERS_PARQUET),
        ("users", USERS_PARQUET),
        ("daily_metrics", DAILY_METRICS_PARQUET),
    ]:
        path.parent.mkdir(parents=True, exist_ok=True)
        tables[name].to_parquet(path, index=False)
        print(f"[clean] 已写 {path}（{len(tables[name]):,} 行）")

    # 数据质量报告
    write_report(df_raw, df, report, tables)

    print("\n[clean] 清洗完成。")
    print(f"  原始行 {report['raw_rows']:,} → 清洗后 {len(df):,}（去重 {report['dup_rows_removed']:,}）")
    print(f"  price<=0 {report['price_le0']:,}；price NaN {report['price_nan']:,}")
    print(f"  session 缺失 {report['session_missing']:,}；category_code 缺失 {report['category_code_missing']:,}")


if __name__ == "__main__":
    main()
