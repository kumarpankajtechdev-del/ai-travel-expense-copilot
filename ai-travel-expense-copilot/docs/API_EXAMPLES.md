# API Examples

## Health Check

```bash
curl http://localhost:8000/api/v1/health
```

## Parse Receipt

```bash
curl -X POST http://localhost:8000/api/v1/receipts/parse \
  -H 'Content-Type: application/json' \
  -d '{"receipt_text":"Blue Orchid Hotel Mumbai\nHotel stay Mumbai\nRoom charge INR 4200"}'
```

## Review Claim

```bash
curl -X POST http://localhost:8000/api/v1/claims/review \
  -H 'Content-Type: application/json' \
  -d '{
    "employee_id": "EMP-1001",
    "employee_grade": "L4",
    "expense_type": "hotel",
    "city": "Mumbai",
    "amount": 4200,
    "currency": "INR",
    "receipt_text": "Blue Orchid Hotel Mumbai Hotel stay Mumbai Room charge INR 4200"
  }'
```
