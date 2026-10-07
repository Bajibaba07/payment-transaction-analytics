USE payment_analytics;

-- Replaces all rows in the dedicated synthetic payment_analytics database.
-- Run only after confirming that this database contains no user-owned data.
START TRANSACTION;
DELETE FROM transactions_clean;
DELETE FROM cards_public;
DELETE FROM customers;
DELETE FROM merchants;

LOAD DATA LOCAL INFILE 'data/processed/customers_clean.csv'
INTO TABLE customers
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(
    customer_id,
    first_name,
    last_name,
    gender,
    age,
    email,
    phone,
    city,
    state,
    occupation,
    annual_income,
    @registration_date
)
SET registration_date = STR_TO_DATE(TRIM(@registration_date), '%Y-%m-%d');

LOAD DATA LOCAL INFILE 'data/processed/merchants_clean.csv'
INTO TABLE merchants
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(
    merchant_id,
    merchant_name,
    merchant_category,
    city,
    state,
    @contact_person,
    @email,
    @phone,
    @registration_date,
    @merchant_status
)
SET
    registration_date = STR_TO_DATE(TRIM(@registration_date), '%Y-%m-%d'),
    merchant_status = TRIM(@merchant_status);

LOAD DATA LOCAL INFILE 'data/processed/cards_public.csv'
INTO TABLE cards_public
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(
    card_id,
    customer_id,
    card_type,
    bank_name,
    card_network,
    issue_date,
    expiry_date,
    @card_status
)
SET card_status = TRIM(@card_status);

LOAD DATA LOCAL INFILE 'data/processed/transactions_clean.csv'
INTO TABLE transactions_clean
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(
    transaction_id,
    card_id,
    customer_id,
    merchant_id,
    merchant_name,
    merchant_category,
    transaction_date,
    amount,
    currency,
    transaction_type,
    transaction_status,
    payment_method,
    merchant_city,
    merchant_state,
    bank_name,
    card_type,
    customer_city,
    customer_state,
    description,
    transaction_month,
    @is_successful,
    @is_failure
)
SET
    is_successful = (TRIM(@is_successful) = 'True'),
    is_failure = (TRIM(@is_failure) = 'True');

COMMIT;