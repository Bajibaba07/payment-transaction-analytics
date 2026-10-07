# Card Table Design

| Column Name | Data Type | Description |
|-------------|-----------|-------------|
| card_id | VARCHAR | Unique card identifier |
| customer_id | VARCHAR | Customer who owns the card |
| card_type | VARCHAR | Debit or Credit |
| bank_name | VARCHAR | Bank that issued the card |
| card_network | VARCHAR | Visa |
| issue_date | DATE | Card issue date |
| expiry_date | DATE | Card expiry date |
| card_status | VARCHAR | Active, Blocked, or Expired |