# Green Card Telegram MVP — пошаговый запуск для новичка

Ниже инструкция максимально простыми шагами: **что установить, как заполнить `.env`, как поднять локально, как проверить работу**, и отдельно — **как развернуть в продакшене на Ubuntu**, чтобы сервис стартовал после перезагрузки.

---

## 1) Что нужно заранее

1. **Docker + Docker Compose plugin**
2. Доступ к токенам Telegram-ботов:
   - `BOT_TOKEN` (клиентский бот)
   - `OPERATOR_BOT_TOKEN` (операторский бот)
   - `ADMIN_BOT_TOKEN` (опционально, если админские уведомления должны идти отдельным ботом)
3. URL Mini App (если фронт уже размещён)
4. Webhook URL Bitrix24
5. Секреты для API и защиты данных:
   - `ADMIN_API_TOKEN`
   - `BITRIX_MESSAGE_API_TOKEN`
   - `PII_HASH_SECRET`

Проверка Docker:

```bash
docker --version
docker compose version
```

---

## 2) Как заполнить `.env`

### Шаг 2.1 — создать `.env` из шаблона

```bash
cp .env.example .env
```

### Шаг 2.2 — открыть файл

```bash
nano .env
```

### Шаг 2.3 — пример `.env`

```env
BOT_TOKEN=123456:ABC...
OPERATOR_BOT_TOKEN=654321:XYZ...
ADMIN_BOT_TOKEN=987654:ADMIN...

# Только bootstrap/fallback. Основной список операторов хранится в таблице operators.
OPERATOR_IDS=123456789,987654321

MINI_APP_URL=https://miniapp.example.com
BITRIX24_WEBHOOK_URL=https://yourcompany.bitrix24.com/rest/1/your_webhook/
DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres:5432/green_card
REDIS_URL=redis://redis:6379/0

ADMIN_API_TOKEN=super-secret-admin-token
BITRIX_MESSAGE_API_TOKEN=super-secret-bitrix-token
PII_HASH_SECRET=replace-with-long-random-secret
DEFAULT_LANGUAGE=ru
```

Расшифровка:
- `BOT_TOKEN` — токен клиентского бота.
- `OPERATOR_BOT_TOKEN` — токен бота операторов.
- `ADMIN_BOT_TOKEN` — токен для админских уведомлений; если пустой, используется `OPERATOR_BOT_TOKEN`.
- `OPERATOR_IDS` — **только первичный bootstrap/fallback** для доступа операторов, пока таблица `operators` пуста или БД временно недоступна. Постоянно операторов нужно вести через `/api/admin/operators`.
- `MINI_APP_URL` — URL фронта Mini App.
- `BITRIX24_WEBHOOK_URL` — webhook Bitrix24.
- `DATABASE_URL` — строка подключения к PostgreSQL.
- `REDIS_URL` — Redis для очередей, rate-limit и кэша текстов.
- `ADMIN_API_TOKEN` — токен доступа к admin endpoint.
- `BITRIX_MESSAGE_API_TOKEN` — токен, которым Bitrix подписывает запросы в backend.
- `PII_HASH_SECRET` — секрет HMAC-SHA256 для индекса дублей; в проде должен быть длинным и случайным.
- `DEFAULT_LANGUAGE` — язык по умолчанию.

> Важно: `.env` не коммитим в git. При смене `PII_HASH_SECRET` старые HMAC-индексы дублей перестанут совпадать с новыми.

---

## 3) Правило миграций Alembic

### Главное правило

**Любое изменение структуры БД в `app/db/models.py` должно идти вместе с новой Alembic-миграцией в `alembic/versions`.**

Нельзя коммитить только модель без миграции или миграцию без соответствующей модели.

### Команды для разработки

Проверить текущую ревизию БД:

```bash
docker compose exec backend alembic current
```

Применить все миграции:

```bash
docker compose exec backend alembic upgrade head
```

Откатить одну миграцию назад для проверки downgrade:

```bash
docker compose exec backend alembic downgrade -1
```

Вернуть обратно на последнюю миграцию:

```bash
docker compose exec backend alembic upgrade head
```

Создать новую миграцию вручную:

```bash
docker compose exec backend alembic revision -m "short_description"
```

После создания миграции обязательно:

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend alembic downgrade -1
docker compose exec backend alembic upgrade head
```

### Правила оформления миграций

1. `revision` должен быть уникальным.
2. `down_revision` должен указывать на предыдущую миграцию, чтобы цепочка была линейной.
3. В `upgrade()` создаём/изменяем таблицы, индексы и колонки.
4. В `downgrade()` откатываем изменения в обратном порядке.
5. Для Telegram/Bitrix ID используем `BigInteger`, не `Integer`.
6. Не используем `alembic upgrade head || true`: если миграция не прошла, backend не должен стартовать поверх несовместимой схемы.

---

## 4) Локальный запуск проекта

Из папки `green-card-telegram`:

```bash
docker compose up -d --build
```

Проверить, что контейнеры поднялись:

```bash
docker compose ps
```

Должны быть сервисы:
- `backend`
- `postgres`
- `redis`
- `bitrix_retry_worker`
- `sla_worker`
- `reminder_worker`
- `client_bot`
- `operator_bot`

Остановка:

```bash
docker compose down
```

Полная очистка локальной БД и volume PostgreSQL, если нужно начать с нуля:

```bash
docker compose down -v
```

---

## 5) Как проверить backend

### 5.1 Health endpoint

```bash
curl http://localhost:8000/health
```

Ожидается:

```json
{"status":"ok"}
```

### 5.2 Проверка admin endpoint без токена

```bash
curl http://localhost:8000/api/admin/applications/test/events
```

Ожидается 403.

### 5.3 Проверка admin endpoint с токеном

```bash
curl -H "x-admin-token: YOUR_ADMIN_API_TOKEN" \
  http://localhost:8000/api/admin/applications/test/events
```

---

## 6) Управление операторами

Основной источник операторов — таблица `operators`, а не `.env`.

Добавить оператора:

```bash
curl -X POST http://localhost:8000/api/admin/operators \
  -H "Content-Type: application/json" \
  -H "x-admin-token: YOUR_ADMIN_API_TOKEN" \
  -d '{"telegram_user_id":123456789,"name":"Анна","role":"operator","languages":["ru"],"max_active_tickets":10,"is_active":true}'
```

Список операторов:

```bash
curl -H "x-admin-token: YOUR_ADMIN_API_TOKEN" \
  http://localhost:8000/api/admin/operators
```

Отключить оператора без удаления истории:

```bash
curl -X POST -H "x-admin-token: YOUR_ADMIN_API_TOKEN" \
  http://localhost:8000/api/admin/operators/1/deactivate
```

`OPERATOR_IDS` оставлен только как аварийный fallback/bootstrap, чтобы можно было зайти в operator bot до первичного заполнения таблицы.

---

## 7) Как проверить client bot

1. Откройте Telegram.
2. Найдите клиентского бота.
3. Отправьте `/start`.
4. Проверьте выбор языка.
5. Отправьте `/calc` и посчитайте цену — backend создаст безопасный `calculator_lead` и reminder follow-up на 45 минут.
6. Отправьте `/apply`:
   - если `MINI_APP_URL` заполнен, появится WebApp-кнопка;
   - если используется Telegram-сценарий, создаётся безопасный `application_draft` и reminders на 30 минут / 24 часа / 3 дня.

---

## 8) Как проверить operator bot

1. Добавьте свой Telegram ID в `/api/admin/operators` или временно в `OPERATOR_IDS` для bootstrap.
2. Откройте operator bot и отправьте `/start`.
3. Отправьте `/tickets`.
4. Проверьте, что заявки отображаются, включая CRM/SLA статус.
5. Команды:
   - `/take <request_id>`
   - `/reply <request_id> <text>`
   - `/close <request_id>`

Если Telegram ID не найден среди активных операторов и отсутствует в fallback `OPERATOR_IDS`, должен быть `Access denied`.

---

## 9) Как проверить отправку заявки

### Вариант A: через Mini App

1. Откройте Mini App через `/apply`.
2. Заполните шаги формы.
3. Прикрепите jpg/png/pdf (до 10 МБ, не более 9 файлов).
4. Отправьте форму.
5. Проверьте:
   - в ответе есть `request_id`;
   - заявка появилась в БД;
   - активные calculator/draft reminders отменились;
   - клиент получил уведомление `application_accepted`;
   - оператор получил уведомление/тикет, если требуется ручная обработка.

### Вариант B: через API напрямую

`/api/applications` ожидает `multipart/form-data`:
- `application_json`
- `vehicle_docs[]`

---

## 10) Уведомления и напоминания

### NotificationService

Все клиентские, операторские и админские уведомления должны идти через `NotificationService`, а не через разрозненные `bot.send_message()` в бизнес-логике.

Проверить шаблоны:

```bash
curl -H "x-admin-token: YOUR_ADMIN_API_TOKEN" \
  http://localhost:8000/api/admin/notification-templates
```

Проверить правила/throttle:

```bash
curl -H "x-admin-token: YOUR_ADMIN_API_TOKEN" \
  http://localhost:8000/api/admin/notification-rules
```

### Reminder worker

`reminder_worker` раз в минуту берёт due-задачи из `reminder_tasks`, проверяет актуальность и отправляет через `NotificationService`.

Ручной запуск одной проверки:

```bash
docker compose exec backend python -c "from app.workers.reminder_worker import run_reminder_checks; print(run_reminder_checks())"
```

Смотреть pending reminders:

```bash
docker compose exec postgres psql -U postgres -d green_card -c "select id, reminder_type, status, scheduled_at, dedupe_key from reminder_tasks order by scheduled_at desc limit 20;"
```

---

## 11) Отправка сообщения клиенту из Bitrix в Telegram

После создания сделки Telegram chat ID клиента сохраняется в поле Bitrix `UF_CRM_1780237379152`. Чтобы отправить клиенту сообщение из Bitrix, вызовите endpoint backend:

```bash
curl -X POST "https://your-backend.example.com/api/bitrix/send-message" \
  -H "Content-Type: application/json" \
  -H "X-Bitrix-Token: super-secret-bitrix-token" \
  -d '{"UF_CRM_1780237379152":"12345","message":"Стоимость полиса: 10 USD"}'
```

Можно также передать поля `chat_id` и `text` вместо `UF_CRM_1780237379152` и `message`. Backend отправит сообщение через клиентский Telegram bot (`BOT_TOKEN`).

---

## 12) Очистка локальных персональных данных

После успешного создания сделок в Bitrix backend очищает локальные данные заявки и оставляет минимальную строку `applications`: `request_id`, `telegram_user_id`, `bitrix_deal_ids_json`, `status`, `created_at`, `updated_at`, `source_channel`.

Для отложенной очистки файлов и операционных данных запускайте retention worker по расписанию, например cron раз в день:

```bash
docker compose exec backend python -c "from app.workers.data_retention_worker import run_data_retention; print(run_data_retention())"
```

Он удаляет локальные файлы из `storage/applications/<request_id>/...` через 72 часа после успешной передачи в Bitrix, а через 90 дней очищает старые операторские/аналитические/технические данные.

---

## 13) Как смотреть логи

Живые логи:

```bash
docker compose logs -f backend
docker compose logs -f client_bot
docker compose logs -f operator_bot
docker compose logs -f bitrix_retry_worker
docker compose logs -f sla_worker
docker compose logs -f reminder_worker
```

Логи конкретного контейнера за последние 200 строк:

```bash
docker compose logs --tail=200 backend
```

---

## 14) Продакшен на Ubuntu

### 14.1 Где размещать проект

Рекомендуемая папка:

```bash
/opt/green-card-telegram
```

Почему:
- стандартно для self-hosted сервисов;
- удобно для бэкапов/доступов;
- не зависит от домашней папки пользователя.

Развернуть:

```bash
sudo mkdir -p /opt/green-card-telegram
sudo chown -R $USER:$USER /opt/green-card-telegram
cd /opt/green-card-telegram
# git clone ... или rsync исходников
```

### 14.2 Установка Docker на Ubuntu

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Добавить пользователя в группу docker:

```bash
sudo usermod -aG docker $USER
# перелогиниться
```

### 14.3 Запуск в проде

```bash
cd /opt/green-card-telegram
cp .env.example .env
nano .env
docker compose up -d --build
```

### 14.4 Чтобы запускалось после перезагрузки

В `docker-compose.yml` для сервисов используется:

```yaml
restart: unless-stopped
```

Также включите Docker service:

```bash
sudo systemctl enable docker
sudo systemctl start docker
```

Проверка после перезагрузки:

```bash
sudo reboot
# после входа:
cd /opt/green-card-telegram
docker compose ps
```

### 14.5 Рекомендации для стабильности

1. Делайте бэкап:
   - `.env`
   - volume PostgreSQL (`pg_data`)
2. Лимитируйте доступ к серверу (UFW, SSH keys).
3. Держите `ADMIN_API_TOKEN`, `BITRIX_MESSAGE_API_TOKEN`, `PII_HASH_SECRET` сложными.
4. Если публикуете наружу — поставьте reverse proxy (Nginx/Caddy) + HTTPS.
5. Перед деплоем новой версии всегда применяйте и проверяйте миграции на staging или свежем бэкапе.

---

## 15) Проверка сценария «Bitrix24 недоступен»

Ожидаемое поведение:
- API не падает;
- заявка сохраняется локально;
- создаётся sync job с pending/retrying;
- worker пытается повторно отправить в Bitrix;
- после исчерпания попыток создаётся операторский тикет `bitrix_sync_failed`.

Проверять через:
- логи `backend` и `bitrix_retry_worker`;
- таблицы `applications`, `bitrix_sync_jobs`, `operator_tickets`.
