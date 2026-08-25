# -*- coding: utf-8 -*-
"""
公共读取函数与全局配置。

所有脚本统一从这里取路径，保证可复现。路径以项目根目录为基准：
    PROJECT_ROOT = <项目>/ecommerce-behavior-analysis
原始数据（只读，不原地改）：
    RAW_CSV      = ../dataone/2019-Nov.csv      （原始 GB 级 CSV，仅抽样阶段读取）
    RAW_SAMPLE   = data/raw/events_sample.parquet （抽样后 5% 用户全量事件）
清洗后分析表（全部落 data/processed/，绝不覆盖原始数据）：
    EVENTS / ORDERS / USERS / DAILY_METRICS
SQLite 库：data/ecommerce.db（SQL 与 pandas 双轨互验）
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_CSV = PROJECT_ROOT.parent / "dataone" / "2019-Nov.csv"
RAW_SAMPLE = PROJECT_ROOT / "data" / "raw" / "events_sample.parquet"

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
EVENTS_PARQUET = PROCESSED_DIR / "events.parquet"
ORDERS_PARQUET = PROCESSED_DIR / "orders.parquet"
USERS_PARQUET = PROCESSED_DIR / "users.parquet"
DAILY_METRICS_PARQUET = PROCESSED_DIR / "daily_metrics.parquet"

DB_PATH = PROJECT_ROOT / "data" / "ecommerce.db"

# ---------------------------------------------------------------------------
# 全局口径常量
# ---------------------------------------------------------------------------
SEED = 42
# event_time 在原始 CSV 中是 UTC 字符串（形如 "2019-11-01 00:00:00 UTC"）。
# 手册要求入库前统一转「本地时区」——该数据集为俄罗斯多品类电商店铺，
# 按店铺本地时区 Europe/Moscow（UTC+3）处理，分时分布符合「晚上浏览、午间购买」真实行为，
# 并在指标字典中注明该口径。
LOCAL_TZ = "Europe/Moscow"

# 事件类型全集（与数据集说明一致）
EVENT_TYPES = ["view", "cart", "remove_from_cart", "purchase"]

# 抽样口径：hash(user_id) % 100 < 5 → 约 5% 用户。
# user_id 为 64 位内整数，Python 对 int 的 hash() 无随机盐且 hash(x)==x（x < 2**61），
# 故等价于 user_id % 100 < 5，跨进程可复现（PYTHONHASHSEED 仅影响 str/bytes）。
SAMPLE_MOD = 100
SAMPLE_LT = 5


# ---------------------------------------------------------------------------
# 读取函数
# ---------------------------------------------------------------------------
def parse_event_time(series: pd.Series) -> pd.Series:
    """把原始 event_time 字符串解析为 UTC，再转本地时区（Europe/Moscow），返回无时区 datetime。"""
    # 去掉 " UTC" 后缀，按明确格式解析，避免 pandas 猜格式歧义
    cleaned = series.str.replace(" UTC", "", regex=False)
    dt_utc = pd.to_datetime(cleaned, format="%Y-%m-%d %H:%M:%S")
    return (
        dt_utc.dt.tz_localize("UTC")
        .dt.tz_convert(LOCAL_TZ)
        .dt.tz_localize(None)
    )


def load_events() -> pd.DataFrame:
    """读取清洗后的 events 分析表。"""
    return pd.read_parquet(EVENTS_PARQUET)


def load_orders() -> pd.DataFrame:
    """读取清洗后的 orders（购买事件）分析表。"""
    return pd.read_parquet(ORDERS_PARQUET)


def load_users() -> pd.DataFrame:
    """读取清洗后的 users 用户级汇总表。"""
    return pd.read_parquet(USERS_PARQUET)


def load_daily_metrics() -> pd.DataFrame:
    """读取清洗后的 daily_metrics 日粒度指标表。"""
    return pd.read_parquet(DAILY_METRICS_PARQUET)


def load_sample() -> pd.DataFrame:
    """读取抽样后的原始事件（未清洗，用于抽样质量检查）。"""
    return pd.read_parquet(RAW_SAMPLE)
