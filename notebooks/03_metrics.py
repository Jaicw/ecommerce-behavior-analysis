# -*- coding: utf-8 -*-
"""
03 · 指标体系与 SQL 双轨互验（手册 D5–D6）

结论摘要
--------
- 计算月粒度 North Star（GMV）与二级指标（UV / 购买转化率 / 客单价 / 人均行为数 / 复购率）。
- SQLite 入库：执行 sql/schema.sql 建表 + to_sql 导入四张表。
- 用 SQL 重算日粒度 GMV / UV / 转化率，与 pandas 结果交叉验证（双工具互验）。
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from loaders import (
    PROJECT_ROOT,
    DB_PATH,
    load_events,
    load_orders,
    load_users,
    load_daily_metrics,
)

SCHEMA_PATH = PROJECT_ROOT / "sql" / "schema.sql"


def prep_for_sqlite(df: pd.DataFrame, date_cols, datetime_cols) -> pd.DataFrame:
    out = df.copy()
    for c in date_cols:
        if c in out.columns:
            out[c] = pd.to_datetime(out[c]).dt.strftime("%Y-%m-%d")
    for c in datetime_cols:
        if c in out.columns:
            mask = out[c].notna()
            out[c] = pd.to_datetime(out[c]).dt.strftime("%Y-%m-%d %H:%M:%S").where(mask, None)
    return out


def build_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    events = prep_for_sqlite(load_events(), ["event_date"], ["event_time"])
    orders = prep_for_sqlite(load_orders(), ["event_date"], ["event_time"])
    users = prep_for_sqlite(load_users(), [], ["first_seen", "last_seen", "first_purchase"])
    daily = prep_for_sqlite(load_daily_metrics(), ["event_date"], [])

    # 只入库 SQL 十题与分析需要的核心列
    events_cols = [
        "event_time", "event_date", "event_hour", "event_type", "product_id",
        "category_id", "category_code", "brand", "price", "user_id",
        "user_session", "price_invalid",
    ]
    orders_cols = [
        "event_time", "event_date", "user_id", "product_id", "category_id",
        "category_code", "brand", "price", "price_valid",
    ]

    events[events_cols].to_sql("events", conn, if_exists="append", index=False)
    orders[orders_cols].to_sql("orders", conn, if_exists="append", index=False)
    users.to_sql("users", conn, if_exists="append", index=False)
    daily.to_sql("daily_metrics", conn, if_exists="append", index=False)
    conn.commit()
    return conn


def headline_metrics(events: pd.DataFrame, orders: pd.DataFrame, users: pd.DataFrame) -> dict:
    uv = events["user_id"].nunique()
    pv = len(events)
    gmv = orders.loc[orders["price_valid"], "price"].sum()
    n_orders = len(orders)
    buying_users = orders["user_id"].nunique()
    repurchase_users = int((users["n_purchases"] >= 2).sum())
    return {
        "月GMV": float(gmv),
        "月UV": int(uv),
        "月PV": int(pv),
        "订单数": int(n_orders),
        "购买用户数": int(buying_users),
        "购买转化率(用户口径)": float(buying_users / uv),
        "客单价AOV(GMV/订单)": float(gmv / n_orders),
        "人均行为数(PV/UV)": float(pv / uv),
        "复购用户数(购买≥2次)": int(repurchase_users),
        "复购率(复购/购买用户)": float(repurchase_users / buying_users),
    }


def cross_validate(conn: sqlite3.Connection, pandas_daily: pd.DataFrame) -> pd.DataFrame:
    sql = """
    SELECT
        event_date,
        COUNT(DISTINCT user_id) AS uv,
        SUM(CASE WHEN event_type='purchase' AND price > 0 THEN price ELSE 0 END) AS gmv,
        COUNT(DISTINCT CASE WHEN event_type='purchase' THEN user_id END) AS buying_users
    FROM events
    GROUP BY event_date
    ORDER BY event_date
    """
    sql_daily = pd.read_sql_query(sql, conn)
    sql_daily["conversion_rate"] = sql_daily["buying_users"] / sql_daily["uv"]

    pd_side = pandas_daily[["event_date", "uv", "gmv", "conversion_rate"]].copy()
    pd_side["event_date"] = pd_side["event_date"].astype(str)
    cmp = pd_side.merge(
        sql_daily[["event_date", "uv", "gmv", "conversion_rate"]],
        on="event_date", suffixes=("_pandas", "_sql"),
    )
    cmp["gmv_diff"] = (cmp["gmv_pandas"] - cmp["gmv_sql"]).abs()
    cmp["uv_diff"] = (cmp["uv_pandas"] - cmp["uv_sql"]).abs()
    cmp["conv_diff"] = (cmp["conversion_rate_pandas"] - cmp["conversion_rate_sql"]).abs()
    return cmp


def main() -> None:
    events = load_events()
    orders = load_orders()
    users = load_users()
    daily = load_daily_metrics()

    print("=" * 64)
    print("03 · 指标体系（OSM + 拆解树）核心指标")
    print("=" * 64)
    hm = headline_metrics(events, orders, users)
    for k, v in hm.items():
        if isinstance(v, float) and v < 1 and "率" in k:
            print(f"  {k:<22}: {v:.4%}")
        elif isinstance(v, float):
            print(f"  {k:<22}: {v:,.2f}")
        else:
            print(f"  {k:<22}: {v:,}")

    print("\n[拆解树] GMV = 购买用户数 × 人均订单 × 客单价")
    per_user_orders = hm["订单数"] / hm["购买用户数"]
    check = hm["购买用户数"] * per_user_orders * hm["客单价AOV(GMV/订单)"]
    print(f"  购买用户数 {hm['购买用户数']:,} × 人均订单 {per_user_orders:.3f} × 客单价 {hm['客单价AOV(GMV/订单)']:,.2f} = {check:,.2f}")

    print("\n[SQLite 入库]")
    conn = build_db()
    print(f"  库文件：{DB_PATH}")
    for t in ["events", "orders", "users", "daily_metrics"]:
        n = pd.read_sql_query(f"SELECT COUNT(*) AS n FROM {t}", conn)["n"][0]
        print(f"    {t:<14} {n:>12,} 行")

    print("\n[SQL × pandas 交叉验证] 日粒度 GMV / UV / 转化率")
    cmp = cross_validate(conn, daily)
    print(f"  最大 GMV 绝对差异   : {cmp['gmv_diff'].max():,.4f}")
    print(f"  最大 UV 绝对差异    : {cmp['uv_diff'].max():.0f}")
    print(f"  最大转化率绝对差异  : {cmp['conv_diff'].max():.6f}")
    ok = cmp["gmv_diff"].max() < 0.01 and cmp["uv_diff"].max() == 0 and cmp["conv_diff"].max() < 1e-6
    print(f"  [结论] {'双工具互验通过' if ok else '存在差异，需排查'}")

    conn.close()


if __name__ == "__main__":
    main()
