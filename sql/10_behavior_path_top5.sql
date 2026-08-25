-- =====================================================================
-- 题 10 · 用户行为路径 Top5（会话内连续三个事件的序列）
-- 考点：窗口函数 LEAD 取下一事件 + 字符串拼接 + GROUP BY 计数
-- =====================================================================
WITH seq AS (
    SELECT
        user_id,
        user_session,
        event_type,
        LEAD(event_type, 1) OVER (
            PARTITION BY user_id, user_session
            ORDER BY event_time, rowid
        ) AS e2,
        LEAD(event_type, 2) OVER (
            PARTITION BY user_id, user_session
            ORDER BY event_time, rowid
        ) AS e3
    FROM events
)
SELECT
    event_type || '->' || e2 || '->' || e3 AS path,
    COUNT(*)                                AS cnt
FROM seq
WHERE e2 IS NOT NULL AND e3 IS NOT NULL
GROUP BY path
ORDER BY cnt DESC
LIMIT 5;
