# Green Card Telegram MVP — пошаговый запуск для новичка

Ниже инструкция максимально простыми шагами: **что установить, как заполнить `.env`, как поднять локально, как проверить работу**, и отдельно — **как развернуть в продакшене на Ubuntu**, чтобы сервис стартовал после перезагрузки.

---

## 1) Что нужно заранее

1. **Docker + Docker Compose plugin**
2. Доступ к токенам Telegram-ботов:
   - `BOT_TOKEN` (клиентский бот)
   - `OPERATOR_BOT_TOKEN` (операторский бот)
3. URL Mini App (если фронт уже размещён)
4. Webhook URL Bitrix24

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

### Шаг 2.3 — что означает каждая переменная

Пример:

```env
BOT_TOKEN=123456:ABC...
OPERATOR_BOT_TOKEN=654321:XYZ...
OPERATOR_IDS=123456789,987654321
MINI_APP_URL=https://miniapp.example.com
BITRIX24_WEBHOOK_URL=https://yourcompany.bitrix24.com/rest/1/your_webhook/
DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres:5432/green_card
REDIS_URL=redis://redis:6379/0
ADMIN_API_TOKEN=super-secret-admin-token
DEFAULT_LANGUAGE=ru
```

Расшифровка:
- `BOT_TOKEN` — токен клиентского бота.
- `OPERATOR_BOT_TOKEN` — токен бота операторов.
- `OPERATOR_IDS` — Telegram ID операторов через запятую.
- `MINI_APP_URL` — URL фронта Mini App (используется кнопкой `/apply` в client bot).
- `BITRIX24_WEBHOOK_URL` — webhook Bitrix24.
- `DATABASE_URL` — строка подключения к PostgreSQL (в docker-compose уже подготовлена).
- `REDIS_URL` — Redis для очередей/воркеров.
- `ADMIN_API_TOKEN` — токен доступа к admin endpoint.
- `DEFAULT_LANGUAGE` — язык по умолчанию.

> Важно: `.env` не коммитим в git.

---

## 3) Локальный запуск проекта (на вашем сервере/ПК)

Из корня проекта:

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
- `client_bot`
- `operator_bot`

Остановка:

```bash
docker compose down
```

---

## 4) Как проверить backend

### 4.1 Health endpoint

```bash
curl http://localhost:8000/health
```

Ожидается:

```json
{"status":"ok"}
```

### 4.2 Проверка admin endpoint (без токена — запрет)

```bash
curl http://localhost:8000/api/admin/applications/test/events
```

Ожидается 403.

### 4.3 Проверка admin endpoint (с токеном)

```bash
curl -H "x-admin-token: YOUR_ADMIN_API_TOKEN" \
  http://localhost:8000/api/admin/applications/test/events
```

---

## 5) Как проверить client bot

1. Откройте Telegram.
2. Найдите клиентского бота.
3. Отправьте `/start`.
4. Проверьте выбор языка.
5. Отправьте `/apply`:
   - если `MINI_APP_URL` заполнен, должна появиться WebApp-кнопка;
   - если пуст, бот покажет сообщение о временной недоступности формы.

---

## 6) Как проверить operator bot

1. Убедитесь, что ваш Telegram ID добавлен в `OPERATOR_IDS`.
2. Откройте operator bot и отправьте `/start`.
3. Отправьте `/tickets`.
4. Проверьте, что заявки отображаются (включая CRM/SLA статус).
5. Команды:
   - `/take <request_id>`
   - `/reply <request_id> <text>`
   - `/close <request_id>`

Если Telegram ID не в `OPERATOR_IDS`, должен быть `Access denied`.

---

## 7) Как проверить отправку заявки

### Вариант A: через Mini App
1. Откройте Mini App через `/apply`.
2. Заполните шаги формы.
3. Прикрепите jpg/png/pdf (до 10 МБ, не более 10 файлов).
4. Отправьте форму.
5. Проверьте:
   - в ответе есть `request_id`;
   - заявка появилась в БД;
   - оператор получил уведомление.

### Вариант B: через API напрямую
`/api/applications` ожидает `multipart/form-data`:
- `application_json`
- `vehicle_docs[]`

---

## 8) Как смотреть логи

Живые логи:

```bash
docker compose logs -f backend
docker compose logs -f client_bot
docker compose logs -f operator_bot
docker compose logs -f bitrix_retry_worker
docker compose logs -f sla_worker
```

Логи конкретного контейнера за последние 200 строк:

```bash
docker compose logs --tail=200 backend
```

---

## 9) Продакшен на Ubuntu (рекомендуемый путь)

## 9.1 Где размещать проект
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

## 9.2 Установка Docker на Ubuntu

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

## 9.3 Запуск в проде

```bash
cd /opt/green-card-telegram
cp .env.example .env
nano .env
docker compose up -d --build
```

## 9.4 Чтобы запускалось после перезагрузки

В `docker-compose.yml` для каждого сервиса желательно добавить:

```yaml
restart: unless-stopped
```

После этого Docker автоматически поднимет контейнеры после reboot.

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

## 9.5 Рекомендации для стабильности

1. Делайте бэкап:
   - `.env`
   - volume PostgreSQL (`pg_data`)
2. Лимитируйте доступ к серверу (UFW, SSH keys).
3. Держите `ADMIN_API_TOKEN` сложным.
4. Если публикуете наружу — поставьте reverse proxy (Nginx/Caddy) + HTTPS.

---

## 10) Проверка сценария «Bitrix24 недоступен»

Ожидаемое поведение:
- API не падает;
- заявка сохраняется локально;
- создаётся sync job с pending/retrying;
- worker пытается повторно отправить в Bitrix.

Проверять через:
- логи `backend` и `bitrix_retry_worker`;
- таблицы `applications` и `bitrix_sync_jobs`.
