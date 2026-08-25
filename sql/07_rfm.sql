-- =====================================================================
-- 题 7 · 每个用户的 R / F / M 原始值
-- 考点：MAX(日期) 求最近购买、COUNT、SUM
-- =====================================================================
SELECT
    user_id,
    ROUND(julianday((SELECT MAX(event_date) FROM orders)) - julianday(MAX(event_date)), 0) AS R,
    COUNT(*)                                                                                AS F,
    ROUND(SUM(price), 2)                                                                    AS M
FROM orders
WHERE price_valid = 1
GROUP BY user_id
ORDER BY R ASC;
