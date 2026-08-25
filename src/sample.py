# -*- coding: utf-8 -*-
"""
可复现抽样脚本（固定 seed=42）。

把数 GB 级原始 CSV 按「用户」抽样为 5% 用户的全量事件，落 parquet。
抽样单元必须是 user_id：保住同一用户的完整事件序列，漏斗/留存/RFM 才不会失真。
（按行抽样会随机截断用户路径，所有用户级指标都会坏掉——见手册第 08 章。）

单次遍历中同时采集「全集事件类型分布」等参考统计，供 01_sampling 的完整性质检
（避免为比对再次读取 9GB 原始 CSV）。

用法：
    python src/sample.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter

import numpy as np
import pandas as pd

from loaders import (
    RAW_CSV,
    RAW_SAMPLE,
    SEED,
    SAMPLE_MOD,
    SAMPLE_LT,
)

CHUNKSIZE = 1_000_000  # 分块遍历，避免把 GB 级 CSV 一次性 read_csv 进内存

# 只读需要的列，减少内存与 IO（列裁剪）
USECOLS = [
    "event_time",
    "event_type",
    "product_id",
    "category_id",
    "category_code",
    "brand",
    "price",
    "user_id",
    "user_session",
]

STATS_PATH = RAW_SAMPLE.parent / "sample_stats.json"


def sample_predicate(user_id: pd.Series) -> pd.Series:
    """hash(user_id) % 100 < 5。对 int 型 user_id 等价于 user_id % 100 < 5，可复现。"""
    uid = pd.to_numeric(user_id, errors="coerce")
    return (uid % SAMPLE_MOD) < SAMPLE_LT


def main() -> None:
    np.random.seed(SEED)  # 固定随机种子（抽样本身为确定性哈希）

    if not RAW_CSV.exists():
        print(f"[FATAL] 找不到原始数据：{RAW_CSV}", file=sys.stderr)
        sys.exit(1)

    RAW_SAMPLE.parent.mkdir(parents=True, exist_ok=True)

    sampled_chunks = []
    full_event_counts: Counter = Counter()
    full_users: set = set()
    total_rows = 0
    n_chunks = 0
    t_start = time.time()

    print(f"[sample] 读取 {RAW_CSV}（chunksize={CHUNKSIZE:,}）")
    for chunk in pd.read_csv(
        RAW_CSV,
        usecols=USECOLS,
        chunksize=CHUNKSIZE,
        dtype={
            "event_type": "category",
            "category_code": "string",
            "brand": "string",
            "user_session": "string",
        },
    ):
        n_chunks += 1
        total_rows += len(chunk)

        # 全集参考统计（用于后续完整性质检）
        full_event_counts.update(chunk["event_type"].value_counts().to_dict())
        full_users.update(chunk["user_id"].unique().tolist())

        mask = sample_predicate(chunk["user_id"])
        part = chunk[mask]
        if len(part):
            sampled_chunks.append(part)

        if n_chunks % 10 == 0:
            print(
                f"[sample]   chunk {n_chunks:>3d} | 累计行 {total_rows:>12,} "
                f"| 命中 {sum(len(c) for c in sampled_chunks):>10,} | 用时 {time.time() - t_start:6.1f}s"
            )

    sample = pd.concat(sampled_chunks, ignore_index=True)
    sample.to_parquet(RAW_SAMPLE, index=False)

    sample_event_counts = sample["event_type"].value_counts().to_dict()
    sampled_users = sample["user_id"].nunique()
    sampled_products = sample["product_id"].nunique()
    sampled_rows = len(sample)

    stats = {
        "total_rows": total_rows,
        "full_event_type_counts": dict(full_event_counts),
        "full_distinct_users": len(full_users),
        "sampled_rows": sampled_rows,
        "sampled_row_fraction": round(sampled_rows / total_rows, 6),
        "sampled_event_type_counts": sample_event_counts,
        "sampled_distinct_users": int(sampled_users),
        "sampled_user_fraction": round(sampled_users / len(full_users), 6) if full_users else None,
        "sampled_distinct_products": int(sampled_products),
        "sample_time_min": str(sample["event_time"].min()),
        "sample_time_max": str(sample["event_time"].max()),
    }
    with open(STATS_PATH, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print("\n[sample] 完成")
    print(f"  全量行数         : {total_rows:>12,}")
    print(f"  全量去重用户数   : {len(full_users):>12,}")
    print(f"  抽样行数         : {sampled_rows:>12,}  ({sampled_rows / total_rows:.2%})")
    print(f"  抽样用户数       : {sampled_users:>12,}  ({sampled_users / len(full_users):.2%})")
    print(f"  平均每用户事件   : {sampled_rows / sampled_users:,.2f}")
    print(f"  抽样商品数       : {sampled_products:>12,}")
    print(f"  事件类型分布(全量): {dict(full_event_counts)}")
    print(f"  事件类型分布(抽样): {sample_event_counts}")
    print(f"  输出文件         : {RAW_SAMPLE}")
    print(f"  统计文件         : {STATS_PATH}")
    print(f"  总用时           : {time.time() - t_start:.1f}s")


if __name__ == "__main__":
    main()
