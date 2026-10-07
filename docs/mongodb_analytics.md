# MongoDB Analytics

MongoDB is optional in this project. MySQL is the system of record for relational joins and constraints. MongoDB adds value for a flexible transaction document used for merchant/category exploration and customer activity snapshots.

## Load a dashboard-safe collection

Export `data/processed/transactions_clean.csv` to JSON with pandas or MongoDB Compass. Use only processed datasets; raw customer and merchant contact fields are unnecessary for these aggregations.

```python
from pathlib import Path
import pandas as pd

df = pd.read_csv(Path("data/processed/transactions_clean.csv"))
df.to_json("data/processed/transactions_clean.json", orient="records", date_format="iso")
```

Collection: `payment_analytics.transactions`.

## Useful aggregation pipelines

```javascript
// Monthly completed amount
db.transactions.aggregate([
  { $match: { transaction_status: "Completed" } },
  { $group: {
      _id: "$transaction_month",
      completed_amount: { $sum: "$amount" },
      transaction_count: { $sum: 1 }
  } },
  { $sort: { _id: 1 } }
])

// Category status profile
db.transactions.aggregate([
  { $group: {
      _id: "$merchant_category",
      transactions: { $sum: 1 },
      failed: { $sum: { $cond: [{ $eq: ["$transaction_status", "Failed"] }, 1, 0] } },
      amount: { $sum: "$amount" }
  } },
  { $sort: { amount: -1 } }
])

// Customer activity profile
db.transactions.aggregate([
  { $match: { transaction_status: "Completed" } },
  { $group: {
      _id: "$customer_id",
      completed_spend: { $sum: "$amount" },
      transactions: { $sum: 1 },
      categories: { $addToSet: "$merchant_category" }
  } },
  { $sort: { completed_spend: -1 } },
  { $limit: 10 }
])
```