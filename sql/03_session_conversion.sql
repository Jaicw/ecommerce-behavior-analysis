-- =====================================================================
-- 题 3 · session 粒度转化率（含购买事件的会话占比）
-- 考点：GROUP BY 会话 + 条件聚合（HAVING 可用于过滤多事件会话）
-- =====================================================================
SELECT
    COUNT(*)                                              AS total_sessions,
    SUM(has_purchase)                                     AS purchase_sessions,
    ROUND(SUM(has_purchase) * 1.0 / COUNT(*), 4)          AS session_conversion
FROM (
    SELECT
        user_session,
        MAX(CASE WHEN event_type = 'purchase' THEN 1 ELSE 0 END) AS has_purchase
    FROM events
    GROUP BY user_session
);

-- 变体：只看「≥2 个事件」的会话（HAVING 过滤单事件会话，降低噪声）
SELECT
    COUNT(*)                                              AS multi_event_sessions,
    SUM(has_purchase)                                     AS purchase_sessions,
    ROUND(SUM(has_purchase) * 1.0 / COUNT(*), 4)          AS session_conversion
FROM (
    SELECT
        user_session,
        MAX(CASE WHEN event_type = 'purchase' THEN 1 ELSE 0 END) AS has_purchase
    FROM events
    GROUP BY user_session
    HAVING COUNT(*) >= 2
);
