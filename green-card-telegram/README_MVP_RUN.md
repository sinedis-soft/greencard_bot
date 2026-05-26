# MVP Run Guide

## 1) Fill `.env`
Copy `.env.example` to `.env` and set real values:
- `BOT_TOKEN`
- `OPERATOR_BOT_TOKEN`
- `OPERATOR_IDS`
- `MINI_APP_URL` (used by client bot `/apply` WebApp button)
- `BITRIX24_WEBHOOK_URL`
- `DATABASE_URL`
- `REDIS_URL`
- `ADMIN_API_TOKEN`
- `DEFAULT_LANGUAGE`

## 2) Start project
```bash
docker compose up -d --build
```

## 3) Logs
```bash
docker compose logs -f backend
docker compose logs -f client_bot
docker compose logs -f operator_bot
```

## 4) Stop project
```bash
docker compose down
```

## 5) Check backend
```bash
curl http://localhost:8000/health
```
Expected: `{"status":"ok"}`.

## 6) Check client bot
- Send `/start` and `/apply` in Telegram.
- Ensure WebApp button opens `MINI_APP_URL` from `.env`.

## 7) Check operator bot
- Send `/start`, `/tickets` with operator account from `OPERATOR_IDS`.
- Non-operator account should get `Access denied`.

## 8) Check application submit
- Open Mini App and submit form with files.
- Verify backend logs contain request_id.
- Verify records in DB (`applications`, `vehicles`, `uploaded_documents`, `operator_tickets`).

## 9) Bitrix24 outage behavior
If Bitrix is down:
- application still stored locally;
- `bitrix_sync_jobs` contains pending/retrying job;
- worker retries in background.
