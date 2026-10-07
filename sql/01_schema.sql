CREATE DATABASE IF NOT EXISTS payment_analytics;
USE payment_analytics;

CREATE TABLE IF NOT EXISTS customers (
    customer_id VARCHAR(20) PRIMARY KEY,
    first_name VARCHAR(80) NOT NULL,
    last_name VARCHAR(80) NOT NULL,
    gender VARCHAR(20),
    age INT,
    email VARCHAR(160),
    phone VARCHAR(30),
    city VARCHAR(80),
    state VARCHAR(80),
    occupation VARCHAR(100),
    annual_income DECIMAL(12, 2),
    registration_date DATE
);

CREATE TABLE IF NOT EXISTS cards_public (
    card_id VARCHAR(20) PRIMARY KEY,
    customer_id VARCHAR(20) NOT NULL,
    card_type VARCHAR(20),
    bank_name VARCHAR(100),
    card_network VARCHAR(30),
    issue_date DATE,
    expiry_date DATE,
    card_status VARCHAR(20),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE IF NOT EXISTS merchants (
    merchant_id VARCHAR(20) PRIMARY KEY,
    merchant_name VARCHAR(160) NOT NULL,
    merchant_category VARCHAR(80),
    city VARCHAR(80),
    state VARCHAR(80),
    merchant_status VARCHAR(20),
    registration_date DATE
);

CREATE TABLE IF NOT EXISTS transactions_clean (
    transaction_id VARCHAR(30) PRIMARY KEY,
    card_id VARCHAR(20) NOT NULL,
    customer_id VARCHAR(20) NOT NULL,
    merchant_id VARCHAR(20) NOT NULL,
    merchant_name VARCHAR(160),
    transaction_date DATE,
    transaction_month CHAR(7),
    amount DECIMAL(12, 2),
    currency CHAR(3),
    transaction_type VARCHAR(40),
    transaction_status VARCHAR(20),
    payment_method VARCHAR(30),
    merchant_category VARCHAR(80),
    merchant_city VARCHAR(80),
    merchant_state VARCHAR(80),
    bank_name VARCHAR(100),
    card_type VARCHAR(20),
    customer_city VARCHAR(80),
    customer_state VARCHAR(80),
    description VARCHAR(255),
    is_successful BOOLEAN,
    is_failure BOOLEAN,
    FOREIGN KEY (card_id) REFERENCES cards_public(card_id),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id)
);