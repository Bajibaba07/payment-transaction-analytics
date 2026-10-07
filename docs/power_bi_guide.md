# Power BI Dashboard Guide

## Import model

Load the CSV files from `data/processed/`: `customers_clean`, `cards_public`, `merchants_clean`, and `transactions_clean`. Create one-to-many relationships on `customer_id`, `card_id`, and `merchant_id`. Use `transactions_clean` as the fact table. Do not import raw `cards.csv` into Power BI.

## Recommended pages

1. **Executive Overview:** completed amount, transaction count, active customers, success rate, monthly amount line chart, and status breakdown.
2. **Product and Bank:** amount by merchant category, bank/card-type matrix, and payment-method comparison.
3. **Customer and Merchant:** top customers by completed spend, top merchants, geography by state, and merchant failure-rate table.

## DAX measures

```DAX
Completed Amount =
CALCULATE(SUM(transactions_clean[amount]), transactions_clean[transaction_status] = "Completed")

Transaction Count = COUNTROWS(transactions_clean)

Active Customers = DISTINCTCOUNT(transactions_clean[customer_id])

Successful Transactions =
CALCULATE([Transaction Count], transactions_clean[transaction_status] = "Completed")

Success Rate = DIVIDE([Successful Transactions], [Transaction Count], 0)

Failed Transactions =
CALCULATE([Transaction Count], transactions_clean[transaction_status] = "Failed")

Failure Rate = DIVIDE([Failed Transactions], [Transaction Count], 0)

Average Completed Ticket = DIVIDE([Completed Amount], [Successful Transactions], 0)
```

Format amount measures as INR currency and rate measures as percentages. Add slicers for transaction month, merchant category, bank, card type, status, and state. Tooltips should show counts and rates rather than any sensitive-looking card fields.