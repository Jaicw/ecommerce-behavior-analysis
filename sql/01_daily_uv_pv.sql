-- =====================================================================
-- 题 1 · 每日 UV / PV / 人均行为数
-- 考点：聚合 + COUNT(DISTINCT) + 日期分组
-- =====================================================================
SELECT
    event_date,
    COUNT(*)                                   AS pv,
    COUNT(DISTINCT user_id)                    AS uv,
    ROUND(COUNT(*) * 1.0 / COUNT(DISTINCT user_id), 2) AS per_user_events
FROM events
GROUP BY event_date
ORDER BY event_date;
