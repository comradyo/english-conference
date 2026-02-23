# Сервис регистрации для конференции по английскому языку

Проект состоит из двух сервисов:

- **api** — принимает webhook-заявки из формы Tilda, валидирует/нормализует данные и сохраняет их в MongoDB.
- **worker** — периодически проверяет MongoDB на наличие записей с необработанными файлами, скачивает файл публикации с
  Яндекс.Диска и записывает результат обработки в поле `result`.

> Файлы скачиваются в docker-volume `downloads` (по умолчанию монтируется в `/data/downloads` внутри контейнера
`worker`).

---

## Архитектура и поток данных

1. Пользователь отправляет форму на Tilda.
2. Tilda отправляет POST на `api` → `POST /tilda/webhook`.
3. `api`:
    - проверяет ключ (заголовок `TILDA_API_KEY_NAME`, по умолчанию `Authorization`)
    - парсит `application/json` или form-data
    - валидирует/нормализует поля через `schemas/tilda.py`
    - сохраняет документ в коллекцию MongoDB (`submissions`) и выставляет `result: null`, `locked_at: null`
4. `worker`:
    - забирает “задачу” атомарно через `find_one_and_update` (ставит `locked_at`, `lock_owner`, увеличивает `attempts`)
    - получает ссылку на скачивание через API Яндекс.Диска (`/resources/download`)
    - скачивает файл в `DOWNLOAD_DIR`
    - выполняет обработку (сейчас заглушка в `worker/services/processor.py`)
    - пишет результат в поле `result` и сохраняет `file_local_path`

---

## Требования

- Docker + Docker Compose v2

---

## Быстрый старт (Docker Compose)

### 1) Подготовить env-файл

Скопируй пример и заполни значения:

```bash
cp docker/.env_example docker/.env
```

Важные переменные:

- `TILDA_API_KEY_NAME`, `TILDA_API_KEY_VALUE` — ключ, который должен приходить в webhook-запросе от Tilda
- `YANDEX_API_TOKEN` — OAuth-токен для Яндекс.Диска (нужен воркеру)
- `YANDEX_DISK_PATH` — путь на Диске до каталога с файлами

### 2) Запустить сервисы

Вариант А (зайти в папку `docker/`, чтобы автоматически подхватился `docker/.env`):

```bash
cd docker
docker compose -f compose.yaml up --build
```

Вариант Б (из корня репозитория):

```bash
docker compose --env-file docker/.env -f docker/compose.yaml up --build
```

После запуска:

- `api` доступен на `http://localhost:8000`
- MongoDB наружу не проброшена (доступна только внутри compose-сети)

---

## Настройка Tilda Webhook

В этом проекте webhook защищён токеном (заголовок `TILDA_API_KEY_NAME`, по умолчанию `Authorization`).

Как правильно настроить передачу токена на стороне Tilda — см. официальную инструкцию:

https://help-ru.tilda.cc/forms/webhook

Минимально нужно:

- указать URL вебхука: `http(s)://<ваш_домен>/tilda/webhook`
- включить передачу ключа API и выставить совпадающее значение с `TILDA_API_KEY_VALUE`

---

## Токен Яндекс.Диска

`worker` использует API Яндекс.Диска для получения ссылки скачивания.

Токен (`YANDEX_API_TOKEN`) берётся по документации:

https://yandex.ru/dev/disk/rest

---

## API

### `POST /tilda/webhook`

- Принимает данные формы от Tilda (form-data или JSON)
- Возвращает `202 Accepted` и строку `Accepted`
- Тестовый пинг `test=test` обрабатывается и возвращает `200 ok` (но в текущей реализации ключ всё равно проверяется до
  парсинга тела)

Пример локального запроса (mock), form-data:

```bash
curl -X POST 'http://localhost:8000/tilda/webhook'   -H 'Authorization: supersecret-token'   -H 'Accept: application/json'   --data-urlencode 'Фамилия=Иванов'   --data-urlencode 'Имя=Иван'   --data-urlencode 'Отчество=Иванович'   --data-urlencode 'Место_учебы=...'   --data-urlencode 'Кафедра=...'   --data-urlencode 'Место_работы=...'   --data-urlencode 'Должность=...'   --data-urlencode 'Телефон_для_связи=+7...'   --data-urlencode 'Электронная_почта=test@example.com'   --data-urlencode 'Участие=выступление с презентацией'   --data-urlencode 'Секция=...'   --data-urlencode 'Название_публикации=...'   --data-urlencode 'Консультант_по_языку=...'   --data-urlencode 'Файл_публикации=https://example.com/file.docx'
```

---

## MongoDB: как посмотреть данные

Так как порт Mongo на хост не проброшен, заходи внутрь контейнера:

```bash
docker exec -it eng-conf-form-handler-mongo-1 mongosh
```

Или, если контейнер не запущен:

```bash
docker compose -f docker/compose.yaml exec mongo mongosh
```

Внутри `mongosh`:

```bash
use eng_conference
show collections
db.submissions.find().sort({created_at: -1}).limit(3).pretty()
```

---

## Worker: логика повторов (retry)

- `worker` берёт документ, где:
    - `result == null` **или** `result.status == "error"`
    - и `locked_at == null` **или** `locked_at` истёк (старше `LOCK_TIMEOUT_SEC`)
- если обработка падает:
    - выставляется `result.status = "error"`
    - ставится `locked_at = now` (cooldown на `LOCK_TIMEOUT_SEC`)
    - затем задача станет доступна для повторной попытки

---

## Переменные окружения

Основные (см. `docker/.env_example`):

- `COMPOSE_PROJECT_NAME` — имя проекта compose
- `API_IMAGE_TAG` — тег образов `api` и `worker`
- `TILDA_API_KEY_NAME`, `TILDA_API_KEY_VALUE` — защита вебхука
- `MONGO_URI`, `MONGO_DB`, `MONGO_COLLECTION` — подключение к MongoDB
- `POLL_INTERVAL_SEC` — интервал опроса Mongo worker-ом
- `LOCK_TIMEOUT_SEC` — таймаут “залипания” lock и cooldown при ошибке
- `MAX_ATTEMPTS` — сколько попыток до статуса `failed`
- `DOWNLOAD_DIR` — куда сохраняются файлы внутри контейнера worker
- `WORKER_ID` — идентификатор воркера (для lock_owner и логов)
- `LOG_LEVEL` — уровень логирования воркера
- `YANDEX_API_URL`, `YANDEX_API_TOKEN`, `YANDEX_DISK_PATH` — доступ к Яндекс.Диску

