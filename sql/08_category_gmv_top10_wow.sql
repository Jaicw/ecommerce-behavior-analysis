-- =====================================================================
-- 题 8 · 品类 GMV Top10 及其周环比
-- 考点：RANK/LIMIT 取 Top、周环比自连接（窗口函数 LAG）
-- =====================================================================
WITH cat_daily AS (
    SELECT
        event_date,
        CASE WHEN instr(category_code, '.') > 0
             THEN substr(category_code, 1, instr(category_code, '.') - 1)
             ELSE category_code END AS cat,
        SUM(price) AS gmv
    FROM orders
    WHERE price_valid = 1
    GROUP BY event_date, cat
),
cat_week AS (
    SELECT
        cat,
        strftime('%Y-%W', event_date) AS wk,
        SUM(gmv) AS gmv
    FROM cat_daily
    GROUP BY cat, wk
),
top10 AS (
    SELECT cat
    FROM cat_week
    GROUP BY cat
    ORDER BY SUM(gmv) DESC
    LIMIT 10
)
SELECT
    cw.cat,
    cw.wk,
    ROUND(cw.gmv, 0)                                              AS weekly_gmv,
    LAG(cw.gmv) OVER (PARTITION BY cw.cat ORDER BY cw.wk)         AS prev_week_gmv,
    ROUND((cw.gmv - LAG(cw.gmv) OVER (PARTITION BY cw.cat ORDER BY cw.wk)) * 1.0
        / LAG(cw.gmv) OVER (PARTITION BY cw.cat ORDER BY cw.wk), 4) AS wow_change
FROM cat_week cw
WHERE cw.cat IN (SELECT cat FROM top10)
ORDER BY cw.cat, cw.wk;
