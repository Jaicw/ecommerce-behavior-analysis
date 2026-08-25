-- =====================================================================
-- 题 2 · 漏斗各环节人数与转化率（双口径各一版）
-- 考点：条件聚合 + CASE WHEN；严格时序用子查询取各事件首次时间
-- =====================================================================

-- 【口径 A · 独立转化率】各环节独立计数，不要求先后顺序
SELECT
    COUNT(DISTINCT CASE WHEN event_type = 'view'     THEN user_id END) AS view_users,
    COUNT(DISTINCT CASE WHEN event_type = 'cart'     THEN user_id END) AS cart_users,
    COUNT(DISTINCT CASE WHEN event_type = 'purchase' THEN user_id END) AS purchase_users,
    ROUND(COUNT(DISTINCT CASE WHEN event_type = 'cart'     THEN user_id END) * 1.0
        / COUNT(DISTINCT CASE WHEN event_type = 'view'     THEN user_id END), 4) AS cart_rate,
    ROUND(COUNT(DISTINCT CASE WHEN event_type = 'purchase' THEN user_id END) * 1.0
        / COUNT(DISTINCT CASE WHEN event_type = 'view'     THEN user_id END), 4) AS purchase_rate
FROM events;

-- 【口径 B · 严格时序漏斗】view → cart → purchase，要求事件按时间先后
WITH t AS (
    SELECT user_id,
        MIN(CASE WHEN event_type = 'view'     THEN event_time END) AS v,
        MIN(CASE WHEN event_type = 'cart'     THEN event_time END) AS c,
        MIN(CASE WHEN event_type = 'purchase' THEN event_time END) AS p
    FROM events
    GROUP BY user_id
)
SELECT
    COUNT(v)                                                      AS view_users,
    COUNT(CASE WHEN c IS NOT NULL AND c >= v THEN 1 END)          AS cart_strict,
    COUNT(CASE WHEN p IS NOT NULL AND c IS NOT NULL
                AND c >= v AND p >= c THEN 1 END)                 AS purchase_strict,
    ROUND(COUNT(CASE WHEN p IS NOT NULL AND c IS NOT NULL AND c >= v AND p >= c THEN 1 END) * 1.0
        / COUNT(v), 4)                                            AS strict_purchase_rate
FROM t;
