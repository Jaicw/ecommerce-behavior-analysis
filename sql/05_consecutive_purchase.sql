-- =====================================================================
-- 题 5 · 连续 2 天及以上有购买行为的用户
-- 考点：窗口函数 LAG + 日期差
-- =====================================================================
WITH buy AS (
    SELECT DISTINCT user_id, event_date
    FROM events
    WHERE event_type = 'purchase'
),
with_prev AS (
    SELECT
        user_id,
        event_date,
        LAG(event_date) OVER (PARTITION BY user_id ORDER BY event_date) AS prev_date
    FROM buy
)
SELECT
    COUNT(DISTINCT user_id) AS consecutive_buyers
FROM with_prev
WHERE prev_date IS NOT NULL
  AND julianday(event_date) - julianday(prev_date) = 1;
