-- =====================================================================
-- 题 4 · 次日 / 7 日留存率（以首次出现日为 D0）
-- 考点：自连接 / 条件聚合（留存题是笔试之王）
-- =====================================================================
WITH first AS (
    SELECT user_id, MIN(event_date) AS d0
    FROM events
    GROUP BY user_id
),
active AS (
    SELECT DISTINCT user_id, event_date
    FROM events
),
max_d AS (
    SELECT MAX(event_date) AS m FROM events
)
SELECT
    ROUND(AVG(CASE WHEN a.user_id IS NOT NULL THEN 1.0 ELSE 0.0 END), 4) AS day1_retention
FROM first f
CROSS JOIN max_d
LEFT JOIN active a
    ON f.user_id = a.user_id
   AND a.event_date = date(f.d0, '+1 day')
WHERE f.d0 <= date(max_d.m, '-1 day');

-- 7 日留存：把上文的 '+1 day' 改为 '+7 day'，分母过滤改为 date(max_d.m, '-7 day')：
--   a.event_date = date(f.d0, '+7 day')   AND   f.d0 <= date(max_d.m, '-7 day')
