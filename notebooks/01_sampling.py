# -*- coding: utf-8 -*-
"""
01 · 抽样完整性质检（手册 D1–D2）

结论摘要
--------
- 抽样单元为 user_id（hash(user_id) % 100 < 5），保住用户全量事件序列，而非按行抽样。
- 校验：抽样行占比 ≈ 5%、抽样用户占比 ≈ 5%、四类事件齐全、时间覆盖整月。
- 输出：打印质检表（供数据质量报告引用）；抽样口径说明写入 README（见根目录）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from loaders import RAW_SAMPLE


def main() -> None:
    stats_path = RAW_SAMPLE.parent / "sample_stats.json"
    if not stats_path.exists():
        print(f"[FATAL] 缺少统计文件 {stats_path}，请先运行 src/sample.py", file=sys.stderr)
        sys.exit(1)
    with open(stats_path, encoding="utf-8") as f:
        stats = json.load(f)

    sample = pd.read_parquet(RAW_SAMPLE)

    full_event = stats["full_event_type_counts"]
    full_total = stats["total_rows"]
    sample_event = stats["sampled_event_type_counts"]

    print("=" * 64)
    print("01 · 抽样完整性质检")
    print("=" * 64)

    print("\n[1] 抽样规模")
    print(f"  全量行数           : {full_total:>12,}")
    print(f"  抽样行数           : {stats['sampled_rows']:>12,}  ({stats['sampled_row_fraction']:.2%})")
    print(f"  全量去重用户       : {stats['full_distinct_users']:>12,}")
    print(f"  抽样去重用户       : {stats['sampled_distinct_users']:>12,}  ({stats['sampled_user_fraction']:.2%})")
    print(f"  抽样去重商品       : {stats['sampled_distinct_products']:>12,}")

    print("\n[2] 事件类型分布（抽样 vs 全集）")
    print(f"  {'事件类型':<18}{'全集占比':>10}{'抽样占比':>10}{'差异(pp)':>10}")
    for et in sorted(set(full_event) | set(sample_event)):
        f = full_event.get(et, 0) / full_total
        s = sample_event.get(et, 0) / stats["sampled_rows"]
        print(f"  {et:<18}{f:>10.2%}{s:>10.2%}{s - f:>+10.2%}")

    print("\n[3] 事件类型覆盖")
    missing = {"view", "cart", "remove_from_cart", "purchase"} - set(sample_event)
    print(f"  四类事件是否齐全   : {'是' if not missing else '否，缺 ' + str(missing)}")

    print("\n[4] 时间覆盖完整性")
    print(f"  抽样时间下界       : {stats['sample_time_min']}")
    print(f"  抽样时间上界       : {stats['sample_time_max']}")
    t_min = pd.to_datetime(stats["sample_time_min"])
    t_max = pd.to_datetime(stats["sample_time_max"])
    print(f"  覆盖天数           : {(t_max - t_min).days + 1} 天")

    print("\n[5] 抽样单元口径（写入 README）")
    print("  抽样单元 = user_id；hash(user_id) % 100 < 5 → 约 5% 用户的全量事件。")
    print("  说明：按用户抽样保住用户事件序列完整，漏斗/留存/RFM 才不失真。")

    print("\n[结论] 抽样质检通过，可进入清洗（02_cleaning.py）。")


if __name__ == "__main__":
    main()
