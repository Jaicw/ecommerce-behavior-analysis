-- =====================================================================
-- schema.sql · SQLite 建表语句（手册 D6 入库）
-- 口径：日期一律存 TEXT（'YYYY-MM-DD' 或 'YYYY-MM-DD HH:MM:SS'），本地时区 Asia/Shanghai。
-- =====================================================================

DROP TABLE IF EXISTS events;
CREATE TABLE events (
    event_time     TEXT NOT NULL,   -- 事件时间（本地时区）
    event_date     TEXT NOT NULL,   -- 事件日期 YYYY-MM-DD
    event_hour     INTEGER,         -- 本地小时 0-23
    event_type     TEXT NOT NULL,   -- view / cart / purchase
    product_id     INTEGER,
    category_id    INTEGER,
    category_code  TEXT,            -- 缺失归 unknown
    brand          TEXT,
    price          REAL,
    user_id        INTEGER,
    user_session   TEXT,            -- 缺失补为独立单事件会话
    price_invalid  INTEGER          -- 1 = price 缺失或 <=0
);

DROP TABLE IF EXISTS orders;
CREATE TABLE orders (
    event_time    TEXT NOT NULL,
    event_date    TEXT NOT NULL,
    user_id       INTEGER,
    product_id    INTEGER,
    category_id   INTEGER,
    category_code TEXT,
    brand         TEXT,
    price         REAL,
    price_valid   INTEGER          -- 1 = 有效价格（计入 GMV）
);

DROP TABLE IF EXISTS users;
CREATE TABLE users (
    user_id             INTEGER PRIMARY KEY,
    first_seen          TEXT,
    last_seen           TEXT,
    n_events            INTEGER,
    n_views             INTEGER,
    n_carts             INTEGER,
    n_remove            INTEGER,
    n_purchases         INTEGER,
    active_days         INTEGER,
    distinct_products   INTEGER,
    distinct_categories INTEGER,
    distinct_brands     INTEGER,
    gmv                 REAL,
    first_purchase      TEXT,      -- 无购买为 NULL
    has_purchase        INTEGER
);

DROP TABLE IF EXISTS daily_metrics;
CREATE TABLE daily_metrics (
    event_date      TEXT PRIMARY KEY,
    pv              INTEGER,
    uv              INTEGER,
    n_views         INTEGER,
    n_carts         INTEGER,
    n_remove        INTEGER,
    n_purchases     INTEGER,
    gmv             REAL,
    buying_users    INTEGER,
    orders          INTEGER,
    aov             REAL,
    per_user_events REAL,
    conversion_rate REAL
);
