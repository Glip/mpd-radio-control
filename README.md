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

```bash
docker compose up -d --build
```

Панель: [http://localhost:8080](http://localhost:8080)

| Сервис      | Порт MPD (хост) | HTTP-поток |
|-------------|-----------------|------------|
| Rock Radio  | `6601`          | `8001`     |
| Jazz Radio  | `6602`          | `8002`     |

Классический `mpc` по-прежнему работает:

```bash
mpc -h 127.0.0.1 -p 6601 status
mpc -h 127.0.0.1 -p 6602 status
```

## Только панель (свои MPD уже запущены)

```bash
docker build -t radio-desk .
docker run -d --name radio-desk \
  -p 8080:8080 \
  -e MPD_INSTANCES="rock:host.docker.internal:6601:/music/rock:Rock,jazz:host.docker.internal:6602:/music/jazz:Jazz" \
  -v /path/to/rock/music:/music/rock \
  -v /path/to/jazz/music:/music/jazz \
  radio-desk
```

Каталоги `/music/...` внутри панели должны быть **теми же томами**, что и `music_directory` у соответствующих MPD. Иначе файлы загрузятся, но демон их не увидит.

## Конфигурация

### `MPD_INSTANCES` (CSV)

```
id:host:port[:music_dir[:label]]
```

Несколько станций — через запятую:

```
rock:mpd-rock:6600:/music/rock:Rock Radio,jazz:mpd-jazz:6600:/music/jazz:Jazz Radio
```

### `MPD_INSTANCES_JSON`

```json
[
  {
    "id": "rock",
    "host": "mpd-rock",
    "port": 6600,
    "music_dir": "/music/rock",
    "label": "Rock Radio"
  }
]
```

Опционально:

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `APP_PORT` | Порт панели | `8080` |
| `MPD_TIMEOUT` | Таймаут MPD (сек) | `5` |
| `MAX_UPLOAD_MB` | Лимит загрузки | `500` |
| `MPD_PASSWORD_<ID>` | Пароль MPD для станции | — |

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
export MPD_INSTANCES="rock:127.0.0.1:6601:/tmp/music/rock:Rock"
uvicorn app.main:app --reload --port 8080
pytest
```

## Структура

```
app/                 # FastAPI + UI
mpd/                 # образ и конфиги демо-MPD
Dockerfile           # образ панели radio-desk
docker-compose.yml   # панель + 2 MPD
```
