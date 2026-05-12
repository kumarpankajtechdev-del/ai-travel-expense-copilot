CREATE DATABASE IF NOT EXISTS travel_expense;

CREATE TABLE IF NOT EXISTS travel_expense.claim_events
(
    event_time DateTime DEFAULT now(),
    event_date Date DEFAULT toDate(event_time),
    event_type LowCardinality(String),
    claim_id String,
    employee_grade LowCardinality(String),
    expense_type LowCardinality(String),
    amount Float64,
    currency LowCardinality(String),
    city LowCardinality(String),
    risk_score Float64 DEFAULT 0,
    reason String DEFAULT ''
)
ENGINE = MergeTree
ORDER BY (event_date, event_type, expense_type, city)
SETTINGS index_granularity = 8192;
