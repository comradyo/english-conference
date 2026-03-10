# Сервис регистрации для конференции по английскому языку

Проект имеет две части:

- стек из `api` и `worker` для приёма Tilda webhook и фоновой обработки файлов (**_legacy_**);
- затем система была перестроена в полноценный личный кабинет с авторизацией, формой подачи заявки, административной
  панелью, автоматической проверкой файлов, email-очередью и резервным копированием MongoDB.

## Что есть в текущей системе

### Пользовательский контур

- регистрация и вход в личный кабинет;
- восстановление пароля по email;
- создание заявки на конференцию;
- предварительная проверка `.docx` до отправки основной заявки;
- просмотр своих заявок;
- просмотр статуса, результатов автоматической проверки и комментариев;
- редактирование заявки только в статусе `На доработке`;
- добавление новых комментариев в заявку без потери предыдущих.

### Административный контур

- просмотр всех заявок;
- группировка заявок по секциям;
- изменение статуса заявки;
- скачивание файла публикации и экспертного заключения;
- добавление комментариев автору заявки;
- просмотр всей истории комментариев.

### Служебные процессы

- фоновая автоматическая проверка файлов публикации;
- отдельная очередь email-уведомлений;
- резервное копирование MongoDB;
- публикация `web` через `caddy`.

## Архитектура

Текущий compose-стек находится в [docker/compose.yaml](docker/compose.yaml) и включает:

- `web` — FastAPI-приложение личного кабинета;
- `caddy` — reverse proxy перед `web`;
- `checker` — фоновый воркер автоматической проверки публикаций;
- `checker-api` — внутренний HTTP API для предварительной проверки файлов;
- `mailer` — отдельный сервис отправки email из очереди MongoDB;
- `mongo` — основная MongoDB;
- `mongo-backup` — сервис резервного копирования всей базы.

Legacy-компоненты:

- `api/` — старый webhook-сервис для Tilda;
- `worker/` — старый downloader/processor-процесс для файлов заявок.

Они сохранены в репозитории, но в текущем сценарии по умолчанию не запускаются.

## Бизнес-правила

### Авторизация и роли

- пользователь не может зарегистрировать два аккаунта на один и тот же email;
- права администратора определяются через `WEB_ADMIN_EMAILS`;
- при открытии `/` авторизованный пользователь перенаправляется на `/my-registrations`;
- страница всех заявок доступна только администратору по маршруту `/all_applications`.

### Языки и время

- интерфейс двуязычный: русский и английский;
- весь отображаемый текст вынесен в словари локализации;
- даты и время показываются в часовом поясе `UTC+3 (Europe/Moscow)`.

## Структура заявки

### Поля формы

- `Фамилия` — обязательное текстовое поле;
- `Имя` — обязательное текстовое поле;
- `Отчество` — необязательное текстовое поле;
- `Место учёбы` — обязательное текстовое поле;
- `Кафедра` — необязательное текстовое поле;
- `Место работы` — обязательное текстовое поле;
- `Должность` — необязательное текстовое поле;
- `Телефон для связи` — обязательный телефон;
- `Электронная почта` — обязательный email;
- `Формат участия` — обязательный выбор;
- `Секция` — обязательный выбор;
- `Название публикации` — обязательное текстовое поле;
- `ФИО консультанта по иностранному языку` — обязательное текстовое поле;
- `Файл публикации` — обязательный `.docx` при создании заявки;
- `Экспертное заключение` — необязательный `.docx`.

### Статусы заявки

Используются четыре статуса:

- `На рассмотрении`
- `Принята`
- `На доработке`
- `Отклонена`

Правила:

- редактирование доступно только при статусе `На доработке`;
- после сохранения исправлений заявка снова уходит в статус `На рассмотрении`.

В интерфейсе используются цветовые акценты:

- `На рассмотрении` — серый;
- `На доработке` — жёлтый;
- `Принята` — зелёный;
- `Отклонена` — красный.

### Комментарии к заявке

Комментарии хранятся историей в массиве `comments[]`. Один элемент содержит:

- `author_role` — `admin` или `author`;
- `author_email`;
- `text`;
- `created_at`.

Поведение:

- администратор и автор заявки могут добавлять много комментариев;
- старые комментарии не исчезают после новых изменений;
- email о смене статуса использует последний комментарий администратора;
- комментарии автора и администратора отображаются общим тредом.

### Формат участия

Поддерживаются варианты:

- `Выступление с презентацией`
- `Online-презентация (для иногородних участников)`
- `Публикация в сборнике (без презентации)`
- `Гость`

### Секция

Поддерживаются секции:

- `Электроника и лазерная техника`
- `Фундаментальная математика и физика`
- `Инженерные технологии`
- `Машиностроение`
- `Энергетика`
- `Робототехника и комплексная автоматизация`
- `Информатика и ИТ`
- `Биомедицинские технологии`
- `Инженерный бизнес и менеджмент`
- `Гуманитарные науки`

### Дополнительные замечания по форме

- после успешного сохранения показывается модальное окно с подтверждением;
- в форме есть плейсхолдеры и подсказки на двух языках;
- обязательные поля помечаются `*`.

## Поток данных

1. Пользователь регистрируется или входит в аккаунт.
2. Пользователь открывает `/conference/register`.
3. При необходимости пользователь сначала отправляет файл в `/conference/precheck`.
4. `web` обращается к `checker-api` и показывает результат предварительной проверки без долговременного сохранения этого
   временного результата.
5. После основной отправки заявки данные сохраняются в MongoDB.
6. `checker` асинхронно обрабатывает загруженные публикации и записывает результат в `publication_validation`.
7. Администратор открывает `/all_applications`, выбирает заявку, меняет статус и при необходимости добавляет
   комментарий.
8. `web` создаёт задачу в коллекции `email_tasks`.
9. `mailer` забирает задачу из очереди и отправляет письмо через SMTP.
10. `mongo-backup` периодически делает резервную копию всей MongoDB.

## Быстрый старт

### Требования

- Docker;
- Docker Compose v2.

### 1. Подготовить `.env`

Скопируйте шаблон:

```bash
cp docker/.env_example docker/.env
```

Критичные переменные для текущего стека:

- `MONGO_URI`
- `MONGO_DB`
- `WEB_ADMIN_EMAILS`
- `WEB_NOTIFICATION_EMAIL_SENDER`
- `WEB_NOTIFICATION_EMAIL_PASSWORD`
- `WEB_NOTIFICATION_EMAIL_SMTP_HOST`
- `WEB_NOTIFICATION_EMAIL_SMTP_PORT`
- `WEB_NOTIFICATION_EMAIL_USE_SSL`
- `WEB_CHECKER_API_URL`

Примечание:

В [docker/.env_example](docker/.env_example) остались legacy-переменные `TILDA_API_KEY_*`, `YANDEX_*`, `DOWNLOAD_DIR`,
`WORKER_ID`, `POLL_INTERVAL_SEC`, `LOCK_TIMEOUT_SEC`, `MAX_ATTEMPTS`. Для текущего личного кабинета они не являются
обязательными.

### 2. Запустить сервисы

```bash
cd docker
docker compose -f compose.yaml up -d --build
```

### 3. Доступ к приложению

В продакшене `caddy` настроен на домен `reg.graduate26.ru` с автоматическим выпуском сертификата.

Для локальной работы есть два варианта:

- использовать доменное имя из [docker/Caddyfile](docker/Caddyfile);
- временно раскомментировать `ports` у сервиса `web` в [docker/compose.yaml](docker/compose.yaml) и открыть приложение
  напрямую.

По умолчанию наружу публикуется именно `caddy`, а не `web`.

## Основные переменные окружения

Полный список находится в [docker/.env_example](docker/.env_example). Ниже перечислены только актуальные группы.

### MongoDB и коллекции

- `MONGO_URI`
- `MONGO_DB`
- `WEB_USERS_COLLECTION`
- `WEB_REGISTRATIONS_COLLECTION`
- `WEB_EMAIL_TASKS_COLLECTION`
- `WEB_PASSWORD_RESET_TOKENS_COLLECTION`
- `WEB_SESSIONS_COLLECTION`

### Web

- `WEB_SESSION_COOKIE_NAME`
- `WEB_SESSION_TTL_HOURS`
- `WEB_PASSWORD_RESET_TTL_MINUTES`
- `WEB_ADMIN_EMAILS`
- `WEB_CHECKER_API_URL`
- `WEB_CHECKER_API_TIMEOUT_SEC`

### Mailer

- `WEB_NOTIFICATION_EMAIL_SENDER`
- `WEB_NOTIFICATION_EMAIL_PASSWORD`
- `WEB_NOTIFICATION_EMAIL_SMTP_HOST`
- `WEB_NOTIFICATION_EMAIL_SMTP_PORT`
- `WEB_NOTIFICATION_EMAIL_USE_SSL`
- `MAILER_POLL_INTERVAL_SEC`
- `MAILER_RETRY_DELAY_SEC`
- `MAILER_MAX_ATTEMPTS`

### Checker

- `CHECKER_POLL_INTERVAL_SEC`
- `CHECKER_PROCESSING_TIMEOUT_SEC`

### Backup

- `MONGO_BACKUP_HOST_DIR`
- `MONGO_BACKUP_INTERVAL_SEC`
- `MONGO_BACKUP_FILE_PREFIX`
- `MONGO_BACKUP_KEEP_LAST`

## Полезные маршруты

### Пользовательские

- `GET /` — стартовая страница входа и регистрации;
- `POST /register-account` — регистрация аккаунта;
- `POST /login` — вход;
- `GET /logout` — выход;
- `POST /forgot-password` — запрос на сброс пароля;
- `GET /reset-password` — страница установки нового пароля;
- `POST /reset-password` — сохранение нового пароля;
- `GET /conference/register` — форма новой заявки;
- `POST /conference/precheck` — предварительная проверка файла публикации;
- `POST /conference/register` — создание заявки;
- `GET /conference/register/{registration_id}/edit` — форма редактирования;
- `POST /conference/register/{registration_id}/edit` — сохранение правок;
- `GET /my-registrations` — список заявок пользователя;
- `POST /my-registrations/comment/{registration_id}` — добавление комментария автором.

### Административные

- `GET /all_applications` — список всех заявок;
- `GET /all_applications/file/{registration_id}/{file_kind}` — скачивание вложений;
- `POST /all_applications/comment/{registration_id}` — смена статуса и новый комментарий администратора.

### Служебные

- `GET /health` — базовая проверка процесса;
- `GET /ready` — проверка готовности `web` и MongoDB;
- `POST /validate` — внутренний endpoint `checker-api`.

## Работа с MongoDB

Подключение к `mongosh`:

```bash
docker compose --env-file docker/.env -f docker/compose.yaml exec mongo mongosh
```

Примеры:

```javascript
use
eng_conference
show
collections
db.conference_registrations.find().sort({created_at: -1}).limit(5).pretty()
db.email_tasks.find().sort({created_at: -1}).limit(5).pretty()
```

## Резервные копии MongoDB

Сервис `mongo-backup`:

- делает `mongodump --archive --gzip`;
- пишет архивы в каталог `/backups` внутри контейнера;
- сохраняет их в bind-mounted каталог хоста через `MONGO_BACKUP_HOST_DIR`;
- удаляет старые архивы и оставляет только последние `MONGO_BACKUP_KEEP_LAST`.

Полезные команды:

```bash
docker compose --env-file docker/.env -f docker/compose.yaml logs -f mongo-backup
docker compose --env-file docker/.env -f docker/compose.yaml build --no-cache mongo-backup
docker compose --env-file docker/.env -f docker/compose.yaml up -d mongo-backup
```

### Важное замечание по правам на prod

Если в логах `mongo-backup` появляется `permission denied` при записи во временный файл в `/backups`, проблема почти
всегда в правах на host-directory, смонтированную через `MONGO_BACKUP_HOST_DIR`.

Что проверить:

- каталог на хосте существует;
- пользователь Docker имеет право записи в этот каталог;
- на Linux правильно выставлены `owner`, `group` и `chmod`;
- на Windows или Docker Desktop каталог разрешён для file sharing.

Типовой сценарий для Linux:

```bash
mkdir -p /path/to/mongo-backups
chown -R 999:999 /path/to/mongo-backups
chmod -R 775 /path/to/mongo-backups
```

Если UID/GID внутри контейнера отличаются, их нужно подстроить под фактического пользователя процесса.

## Диагностика

Статус сервисов:

```bash
cd docker
docker compose -f compose.yaml ps
```

Логи:

```bash
cd docker
docker compose -f compose.yaml logs -f web
docker compose -f compose.yaml logs -f checker
docker compose -f compose.yaml logs -f mailer
docker compose -f compose.yaml logs -f mongo-backup
```

Проверка готовности `web` изнутри compose-сети:

```bash
docker compose -f compose.yaml exec web curl -fsS http://localhost:8000/ready
```

## Структура репозитория

- [web](web) — личный кабинет, формы, админка, локализация, MongoDB-интеграция;
- [checker](checker) — фоновая и предварительная проверка `.docx`;
- [mailer](mailer) — отправка email из очереди MongoDB;
- [backup](backup) — shell-скрипт резервного копирования MongoDB;
- [docker](docker) — compose, Dockerfiles и конфигурация `caddy`;
- [api](api) — legacy webhook-сервис для Tilda;
- [worker](worker) — legacy downloader/processor-процесс.

## Описание legacy-части

> Проект состоит из двух сервисов:
> 
> - **api** — принимает webhook-заявки из формы Tilda, валидирует/нормализует данные и сохраняет их в MongoDB.
> - **worker** — периодически проверяет MongoDB на наличие записей с необработанными файлами, скачивает файл публикации с
>   Яндекс.Диска и записывает результат обработки в поле `result`.
> 
> > Файлы скачиваются в docker-volume `downloads` (по умолчанию монтируется в `/data/downloads` внутри контейнера
> `worker`).
> 
> ---
> 
> ## Архитектура и поток данных
> 
> 1. Пользователь отправляет форму на Tilda.
> 2. Tilda отправляет POST на `api` → `POST /tilda/webhook`.
> 3. `api`:
>     - проверяет ключ (заголовок `TILDA_API_KEY_NAME`, по умолчанию `Authorization`)
>     - парсит `application/json` или form-data
>     - валидирует/нормализует поля через `schemas/tilda.py`
>     - сохраняет документ в коллекцию MongoDB (`submissions`) и выставляет `result: null`, `locked_at: null`
> 4. `worker`:
>     - забирает “задачу” атомарно через `find_one_and_update` (ставит `locked_at`, `lock_owner`, увеличивает `attempts`)
>     - получает ссылку на скачивание через API Яндекс.Диска (`/resources/download`)
>     - скачивает файл в `DOWNLOAD_DIR`
>     - выполняет обработку (сейчас заглушка в `worker/services/processor.py`)
>     - пишет результат в поле `result` и сохраняет `file_local_path`
> 
> ---
> 
> ## Быстрый старт (Docker Compose)
> 
> ### 1) Подготовить env-файл
> 
> Важные переменные:
> 
> - `TILDA_API_KEY_NAME`, `TILDA_API_KEY_VALUE` — ключ, который должен приходить в webhook-запросе от Tilda
> - `YANDEX_API_TOKEN` — OAuth-токен для Яндекс.Диска (нужен воркеру)
> - `YANDEX_DISK_PATH` — путь на Диске до каталога с файлами
> 
> ### 2) Запустить сервисы
> 
> ```bash
> cd docker
> docker compose -f compose.yaml up --build
> ```
> 
> После запуска:
> 
> - `api` доступен на `http://localhost:8000`
> - MongoDB наружу не проброшена (доступна только внутри compose-сети)
> 
> ---
> 
> ## Настройка Tilda Webhook
> 
> В этом проекте webhook защищён токеном (заголовок `TILDA_API_KEY_NAME`, по умолчанию `Authorization`).
> 
> Как правильно настроить передачу токена на стороне Tilda — см. официальную инструкцию:
> 
> https://help-ru.tilda.cc/forms/webhook
> 
> Минимально нужно:
> 
> - указать URL вебхука: `http(s)://<ваш_домен>/tilda/webhook`
> - включить передачу ключа API и выставить совпадающее значение с `TILDA_API_KEY_VALUE`
> 
> ---
> 
> ## Токен Яндекс.Диска
> 
> `worker` использует API Яндекс.Диска для получения ссылки скачивания.
> 
> Токен (`YANDEX_API_TOKEN`) берётся по документации:
> 
> https://yandex.ru/dev/disk/rest
> 
> ---
> 
> ## API
> 
> ### `POST /tilda/webhook`
> 
> - Принимает данные формы от Tilda (form-data или JSON)
> - Возвращает `202 Accepted` и строку `Accepted`
> - Тестовый пинг `test=test` обрабатывается и возвращает `200 ok` (но в текущей реализации ключ всё равно проверяется до
>   парсинга тела)
> 
> Пример локального запроса (mock), form-data:
> 
> ```bash
> curl -X POST 'http://localhost:8000/tilda/webhook'   -H 'Authorization: supersecret-token'   -H 'Accept: application/json'   --data-urlencode 'Фамилия=Иванов'   --data-urlencode 'Имя=Иван'   --data-urlencode 'Отчество=Иванович'   --data-urlencode 'Место_учебы=...'   --data-urlencode 'Кафедра=...'   --data-urlencode 'Место_работы=...'   --data-urlencode 'Должность=...'   --data-urlencode 'Телефон_для_связи=+7...'   --data-urlencode 'Электронная_почта=test@example.com'   --data-urlencode 'Участие=выступление с презентацией'   --data-urlencode 'Секция=...'   --data-urlencode 'Название_публикации=...'   --data-urlencode 'Консультант_по_языку=...'   --data-urlencode 'Файл_публикации=https://example.com/file.docx'
> ```
> 
> ---
> 
> ## MongoDB: как посмотреть данные
> 
> Внутри `mongosh`:
> 
> ```bash
> use eng_conference
> show collections
> db.submissions.find().sort({created_at: -1}).limit(3).pretty()
> ```
> 
> ---
> 
> ## Worker: логика повторов (retry)
> 
> - `worker` берёт документ, где:
>     - `result == null` **или** `result.status == "error"`
>     - и `locked_at == null` **или** `locked_at` истёк (старше `LOCK_TIMEOUT_SEC`)
> - если обработка падает:
>     - выставляется `result.status = "error"`
>     - ставится `locked_at = now` (cooldown на `LOCK_TIMEOUT_SEC`)
>     - затем задача станет доступна для повторной попытки
> 
> ---
> 
> ## Переменные окружения
> 
> Основные (см. `docker/.env_example`):
> 
> - `COMPOSE_PROJECT_NAME` — имя проекта compose
> - `API_IMAGE_TAG` — тег образов `api` и `worker`
> - `TILDA_API_KEY_NAME`, `TILDA_API_KEY_VALUE` — защита вебхука
> - `MONGO_URI`, `MONGO_DB`, `MONGO_COLLECTION` — подключение к MongoDB
> - `POLL_INTERVAL_SEC` — интервал опроса Mongo worker-ом
> - `LOCK_TIMEOUT_SEC` — таймаут “залипания” lock и cooldown при ошибке
> - `MAX_ATTEMPTS` — сколько попыток до статуса `failed`
> - `DOWNLOAD_DIR` — куда сохраняются файлы внутри контейнера worker
> - `WORKER_ID` — идентификатор воркера (для lock_owner и логов)
> - `LOG_LEVEL` — уровень логирования воркера
> - `YANDEX_API_URL`, `YANDEX_API_TOKEN`, `YANDEX_DISK_PATH` — доступ к Яндекс.Диску


