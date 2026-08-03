# Radio Desk — панель управления MPD

Веб-панель для нескольких контейнеров **MPD** (internet radio): play/pause/stop, next/previous, громкость, плейлист, загрузка треков и альбомов.

На выходе — Docker-образ `radio-desk` и пример `docker-compose` с двумя радиостанциями.

## Возможности

- Управление несколькими MPD на разных хостах/портах
- Play / Pause / Stop / Next / Previous / Seek
- Громкость, Repeat / Random / Single / Consume
- Плейлист и переход к треку по клику
- Загрузка **отдельного трека** или **альбома** (несколько файлов или ZIP)
- После загрузки — `update` базы MPD и добавление в плейлист

## Быстрый старт

1. Проверьте станции в `config/config.yaml` (хосты `mpd-rock` / `mpd-jazz` уже совпадают с compose).
2. Положите музыку в `music/rock` и `music/jazz` (или загрузите через UI).
3. Запустите стек:

```bash
docker compose up -d --build
```

| Сервис     | URL / порт |
|------------|------------|
| Панель     | http://localhost:8080 |
| Rock MPD   | `localhost:6601` (`mpc -h 127.0.0.1 -p 6601`) |
| Rock stream| http://localhost:8001 |
| Jazz MPD   | `localhost:6602` |
| Jazz stream| http://localhost:8002 |

Порты хоста можно переопределить через `.env` (см. `.env.example`).

Остановка:

```bash
docker compose down
```

## Только панель (свои MPD уже запущены)

1. Скопируйте пример и поправьте хосты/порты/каталоги:

```bash
cp config/config.example.yaml config/config.yaml
```

2. Запустите с примонтированным конфигом и музыкой:

```bash
docker build -t radio-desk .
docker run -d --name radio-desk \
  -p 8080:8080 \
  -v ./config/config.yaml:/config/config.yaml:ro \
  -v /path/to/rock/music:/music/rock \
  -v /path/to/jazz/music:/music/jazz \
  radio-desk
```

Каталоги `/music/...` внутри панели должны быть **теми же томами**, что и `music_directory` у соответствующих MPD. Иначе файлы загрузятся, но демон их не увидит.

## Конфигурация

Весь runtime-конфиг — YAML-файл. По умолчанию контейнер читает `/config/config.yaml`.

Пример (`config/config.yaml`):

```yaml
server:
  host: 0.0.0.0
  port: 8080
  mpd_timeout: 5
  max_upload_mb: 500

instances:
  - id: rock
    host: mpd-rock
    port: 6600
    music_dir: /music/rock
    label: Rock Radio
    # password: secret

  - id: jazz
    host: mpd-jazz
    port: 6600
    music_dir: /music/jazz
    label: Jazz Radio
```

| Поле | Описание |
|------|----------|
| `server.host` / `server.port` | Адрес HTTP-панели |
| `server.mpd_timeout` | Таймаут команд MPD (сек) |
| `server.max_upload_mb` | Лимит загрузки |
| `instances[].id` | Уникальный id станции |
| `instances[].host` / `port` | Адрес MPD |
| `instances[].music_dir` | Куда писать загруженные треки |
| `instances[].label` | Имя в UI |
| `instances[].password` | Пароль MPD (опционально) |

Поиск файла:

1. `RADIO_DESK_CONFIG` — явный путь (только если нужно)
2. `/config/config.yaml`
3. `/config/radio-desk.yaml`
4. `./config/config.yaml` (локальный запуск)

## API (кратко)

- `GET /api/instances` — список станций и статусы
- `POST /api/instances/{id}/play|pause|toggle|stop|next|previous`
- `POST /api/instances/{id}/volume` `{"level": 80}`
- `POST /api/instances/{id}/upload/track` — `multipart` поле `file`
- `POST /api/instances/{id}/upload/album` — `album_name` + `files[]` или `archive` (zip)

## Локальная разработка

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# использует ./config/config.yaml
python -m app.run
# или:
RADIO_DESK_CONFIG=./config/config.yaml uvicorn app.main:app --reload --port 8080
pytest
```

## Структура

```
app/                 # FastAPI + UI
config/              # YAML-конфиг панели (монтируется в контейнер)
mpd/                 # образ и конфиги демо-MPD
Dockerfile           # образ панели radio-desk
docker-compose.yml   # панель + 2 MPD
```
