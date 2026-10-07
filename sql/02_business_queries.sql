USE payment_analytics;

-- KPI card: completed revenue, transactions, customers, and success rate.
SELECT
    SUM(CASE WHEN is_successful THEN amount ELSE 0 END) AS completed_amount,
    COUNT(*) AS total_transactions,
    COUNT(DISTINCT customer_id) AS active_customers,
    ROUND(100 * AVG(is_successful), 2) AS success_rate_pct
FROM transactions_clean;

-- Monthly volume and completed amount trend.
SELECT transaction_month,
       COUNT(*) AS transaction_count,
       SUM(CASE WHEN is_successful THEN amount ELSE 0 END) AS completed_amount
FROM transactions_clean
GROUP BY transaction_month
ORDER BY transaction_month;

-- Category performance and failure rate.
SELECT merchant_category,
       COUNT(*) AS transaction_count,
       SUM(CASE WHEN is_successful THEN amount ELSE 0 END) AS completed_amount,
       ROUND(100 * AVG(is_failure), 2) AS failure_rate_pct
FROM transactions_clean
GROUP BY merchant_category
ORDER BY completed_amount DESC;

-- Top customers by completed spend.
SELECT customer_id,
       COUNT(*) AS completed_transactions,
       SUM(amount) AS completed_spend,
       AVG(amount) AS average_ticket
FROM transactions_clean
WHERE is_successful
GROUP BY customer_id
ORDER BY completed_spend DESC
LIMIT 10;

-- Merchant risk view: high volume with above-average failure rate.
SELECT merchant_id, merchant_name, merchant_category,
       COUNT(*) AS transaction_count,
       ROUND(100 * AVG(is_failure), 2) AS failure_rate_pct
FROM transactions_clean
GROUP BY merchant_id, merchant_name, merchant_category
HAVING COUNT(*) >= 5 AND AVG(is_failure) > (SELECT AVG(is_failure) FROM transactions_clean)
ORDER BY failure_rate_pct DESC, transaction_count DESC;

-- Bank and card-type comparison.
SELECT bank_name, card_type,
       COUNT(*) AS transaction_count,
       SUM(CASE WHEN is_successful THEN amount ELSE 0 END) AS completed_amount,
       ROUND(100 * AVG(is_successful), 2) AS success_rate_pct
FROM transactions_clean
GROUP BY bank_name, card_type
ORDER BY completed_amount DESC;