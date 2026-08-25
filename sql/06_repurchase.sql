-- =====================================================================
-- 题 6 · 复购用户占比与平均购买间隔
-- 考点：两层聚合 + HAVING COUNT ≥ 2；间隔用窗口函数 LAG
-- =====================================================================

-- 复购用户占比（复购 = 购买次数 ≥ 2）
WITH order_cnt AS (
    SELECT user_id, COUNT(*) AS n
    FROM orders
    WHERE price_valid = 1
    GROUP BY user_id
)
SELECT
    SUM(CASE WHEN n >= 2 THEN 1 ELSE 0 END)            AS repurchase_users,
    COUNT(*)                                            AS total_buyers,
    ROUND(SUM(CASE WHEN n >= 2 THEN 1 ELSE 0 END) * 1.0 / COUNT(*), 4) AS repurchase_rate
FROM order_cnt;

-- 平均购买间隔（相邻两笔订单间隔天数）
WITH with_prev AS (
    SELECT
        user_id,
        event_date,
        LAG(event_date) OVER (PARTITION BY user_id ORDER BY event_date) AS prev_date
    FROM orders
    WHERE price_valid = 1
)
SELECT
    ROUND(AVG(julianday(event_date) - julianday(prev_date)), 2) AS avg_purchase_interval_days
FROM with_prev
WHERE prev_date IS NOT NULL;
