curl --location '127.0.0.1:18881/api/v1/trades' \
--header 'Content-Type: application/json' \
--header 'Cookie: session_token=uYsEZZdH9ecQ432HQUdfab292I14suk4GuI12-cAyuw' \
--data '{
    "friendly_name": "20250908-CA-PUT",
    "symbol": "CA",
    "exchange_id": 1,
    "underlying_currency": "EUR",
    "trade_type": "SELL_PUT",
    "trade_strategy": "WHEEL",
    "trade_date": "2025-09-08",
    "quantity": 1,
    "quantity_multiplier": 100,
    "price_cents": 17,
    "expiry_date": "2025-09-09",
    "strike_price_cents": 1220,
    "commission_cents": 114
}'

curl --location '127.0.0.1:18881/api/v1/trades' \
--header 'Content-Type: application/json' \
--header 'Cookie: session_token=uYsEZZdH9ecQ432HQUdfab292I14suk4GuI12-cAyuw' \
--data '{
    "friendly_name": "20250920-CA-ASSIGN",
    "symbol": "CA",
    "exchange_id": 1,
    "cycle_id": 1,
    "underlying_currency": "EUR",
    "trade_type": "ASSIGNMENT",
    "trade_strategy": "WHEEL",
    "trade_date": "2025-09-20",
    "quantity": 100,
    "quantity_multiplier": 1,
    "price_cents": 1220,
    "commission_cents": 0
}'

curl --location '127.0.0.1:18881/api/v1/trades' \
--header 'Content-Type: application/json' \
--header 'Cookie: session_token=uYsEZZdH9ecQ432HQUdfab292I14suk4GuI12-cAyuw' \
--data '{
    "friendly_name": "20250923-CA-CALL",
    "symbol": "CA",
    "exchange_id": 1,
    "cycle_id": 1,
    "underlying_currency": "EUR",
    "trade_type": "SELL_CALL",
    "trade_strategy": "WHEEL",
    "trade_date": "2025-09-23",
    "quantity": 1,
    "quantity_multiplier": 100,
    "price_cents": 31,
    "expiry_date": "2025-10-10",
    "strike_price_cents": 1200,
    "commission_cents": 114
}'