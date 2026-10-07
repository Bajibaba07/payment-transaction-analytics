USE payment_analytics;

SELECT 'customers' AS table_name, COUNT(*) AS row_count FROM customers
UNION ALL
SELECT 'cards_public', COUNT(*) FROM cards_public
UNION ALL
SELECT 'merchants', COUNT(*) FROM merchants
UNION ALL
SELECT 'transactions_clean', COUNT(*) FROM transactions_clean;

SELECT COUNT(*) AS invalid_transaction_card_links
FROM transactions_clean t
LEFT JOIN cards_public c ON c.card_id = t.card_id
WHERE c.card_id IS NULL;

SELECT COUNT(*) AS invalid_transaction_customer_links
FROM transactions_clean t
LEFT JOIN customers c ON c.customer_id = t.customer_id
WHERE c.customer_id IS NULL;

SELECT COUNT(*) AS transaction_card_customer_mismatches
FROM transactions_clean t
JOIN cards_public c ON c.card_id = t.card_id
WHERE c.customer_id <> t.customer_id;

SELECT COUNT(*) AS invalid_transaction_merchant_links
FROM transactions_clean t
LEFT JOIN merchants m ON m.merchant_id = t.merchant_id
WHERE m.merchant_id IS NULL;

SELECT COUNT(*) AS transactions_with_sensitive_columns
FROM information_schema.columns
WHERE table_schema = DATABASE()
  AND table_name IN ('cards_public', 'transactions_clean')
  AND column_name IN ('card_number', 'cvv');