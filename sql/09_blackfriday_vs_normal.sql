-- =====================================================================
-- 题 9 · 黑五当日 vs 平日均值：UV / 转化率 / 客单价
-- 考点：CTE + 对比连接（纵向堆叠 UNION ALL）
-- =====================================================================
WITH daily AS (
    SELECT
        event_date,
        COUNT(DISTINCT user_id)                                      AS uv,
        COUNT(DISTINCT CASE WHEN event_type = 'purchase' THEN user_id END) AS buyers,
        SUM(CASE WHEN event_type = 'purchase' THEN 1 ELSE 0 END)      AS orders,
        SUM(CASE WHEN event_type = 'purchase' AND price > 0 THEN price ELSE 0 END) AS gmv
    FROM events
    GROUP BY event_date
),
bf AS (
    SELECT * FROM daily WHERE event_date = '2019-11-29'
),
normal AS (
    SELECT
        AVG(uv)     AS uv,
        AVG(gmv)    AS gmv,
        AVG(orders) AS orders,
        SUM(buyers) * 1.0 / SUM(uv) AS conv
    FROM daily
    WHERE event_date NOT IN ('2019-11-15', '2019-11-16', '2019-11-17',
                             '2019-11-18', '2019-11-29')
)
SELECT '黑五 11-29' AS type,
       uv,
       ROUND(buyers * 1.0 / uv, 4)  AS conv_rate,
       ROUND(gmv / orders, 2)       AS aov
FROM bf
UNION ALL
SELECT '平日均值' AS type,
       ROUND(uv, 0)                 AS uv,
       ROUND(conv, 4)               AS conv_rate,
       ROUND(gmv / orders, 2)       AS aov
FROM normal;
