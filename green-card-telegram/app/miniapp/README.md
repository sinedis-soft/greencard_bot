# Mini App

## Local run
1. `cd app/miniapp`
2. `npm install`
3. `npm run dev`

## Telegram BotFather URL
Set Mini App URL in BotFather.

## Backend submission
POST `/api/applications`.

## Alembic migrations
- `python -c "from alembic.versions import 20260526_01_init as m; m.upgrade()"`

## Bitrix24 mapping notes
Telegram user fields are local only; not sent to Bitrix24.
