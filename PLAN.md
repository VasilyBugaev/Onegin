# «Онегин»: пошаговая инструкция по сборке self-hosted ассистента

## Context

Цель — собственный персональный ассистент по имени **Онегин**, который хостится на своём железе. Принятые решения:

- **Мозг:** локальная LLM на ноутбуке сейчас, вынос на свой GPU-сервер позже.
- **Интерфейс:** веб-приложение (PWA) на домашнем экране iPhone.
- **Навыки:** личный органайзер, поиск и ресёрч, управление ПК.
- **Хостинг:** ноутбук сейчас, сервер потом.

- **Запуск:** в Docker с первого дня (Docker Desktop + WSL2).

Железо (проверено): RTX 5060 Laptop **8 ГБ VRAM**, i5-14450HX, **16 ГБ RAM**, Windows 11 Pro. Есть git; WSL, Docker, Python, Node, Ollama не установлены (`wsl.exe` в системе — только заглушка, перед Docker нужен `wsl --install --no-distribution`).

## Как мы работаем

**Команды выполняешь и код пишешь ты.** Моя роль — инструктор и ревьюер:

1. Перед этапом я выдаю подробную инструкцию: команды, какие файлы создать, что в каждом должно быть, скелет ключевых мест.
2. Ты выполняешь команды и пишешь код.
3. Присылаешь вывод, ошибку или файл — я разбираю и делаю ревью.
4. Сам я ничего не устанавливаю и файлы проекта не создаю, пока ты прямо не попросишь.

Этапы 0–2 ниже расписаны до команд. Этапы 3–8 — шаги и команды установки; детальную инструкцию по коду каждого из них я выдаю, когда ты до него дойдёшь (к тому моменту будет понятно, как реально ведёт себя модель на твоём железе).

## Архитектура

```
iPhone / браузер (PWA «Онегин»)
        │ HTTPS + WebSocket (через Tailscale)
        ▼
┌──────────────── Core (FastAPI, в Docker) ───────────────────┐
│ агентный цикл · реестр инструментов · память · планировщик  │
│ STT / TTS · Web Push · SQLite                               │
└──────┬─────────────────────────────────┬────────────────────┘
       │ OpenAI-совместимый API          │ исходящий WebSocket от агента
       ▼                                 ▼
  LLM-сервер (Ollama)              PC Agent (Windows, нативно)
  сейчас localhost,                программы, файлы, звук, окна,
  потом свой GPU-сервер            wake word «Онегин»
```

Три правила, благодаря которым переезд на сервер — смена конфига:

1. LLM — только через OpenAI-совместимый endpoint (`LLM_BASE_URL`).
2. PC Agent сам подключается к Core исходящим WebSocket (работает за NAT).
3. Всё состояние — в одном Docker-томе `onegin_data` (SQLite + файлы).

**Что в Docker, а что нет:**

| Компонент | Где | Почему |
|---|---|---|
| Core (FastAPI, агент, голос, планировщик) | контейнер | переносится на сервер как есть |
| SearXNG (с этапа 6) | контейнер | свой поиск без API-ключей |
| Ollama | **нативно на Windows** | GPU работает без настройки, а WSL не приходится отдавать память под загрузку модели; на сервере станет контейнером |
| PC Agent | **нативно на Windows** | из контейнера нельзя управлять окнами, звуком и программами хоста |
| Tailscale | нативно на Windows | проксирует на опубликованный порт контейнера |
| `uv` и Node на хосте | только инструменты разработки | управление зависимостями, подсказки в IDE, dev-сервер фронтенда |

**Бюджет RAM (16 ГБ):** WSL ограничиваем 4 ГБ через `.wslconfig`, иначе он заберёт до половины памяти. Windows ~5 ГБ, Ollama ~1–2 ГБ, остальное — браузер и VS Code. Впритык, но рабоче; тяжёлые приложения на время работы закрывать.

**Бюджет VRAM:** LLM ≈ 5,2 ГБ + ~1 ГБ на контекст 8k. Поэтому распознавание речи, синтез и эмбеддинги по умолчанию — на CPU.

## Структура проекта

```
onegin/
  core/
    app.py            # FastAPI: REST + WebSocket
    config.py         # настройки из .env
    db.py             # SQLite
    cli.py            # отладочный клиент в терминале
    llm/client.py     # клиент LLM со стримингом
    agent/loop.py     # цикл: модель → инструменты → модель
    agent/prompts.py  # личность Онегина
    tools/            # registry.py + файл на группу инструментов
    memory/  voice/  scheduler.py  push.py
  pc_agent/           # отдельный Windows-процесс
  web/                # PWA
  evals/              # тестовые запросы
  Dockerfile          # образ Core
  compose.yml         # сервисы и том onegin_data
  .env                # в .gitignore
```

---

## Этап 0. Окружение (1 вечер)

Все команды — в PowerShell.

**Шаг 1. Установка инструментов**

```powershell
winget install --id Docker.DockerDesktop -e
winget install --id astral-sh.uv -e
winget install --id Ollama.Ollama -e
winget install --id OpenJS.NodeJS.LTS -e
winget install --id Tailscale.Tailscale -e
```

ffmpeg на хост не ставим — он будет внутри образа.

**Шаг 1а. Ограничить память WSL.** Создай файл `C:\Users\bugae\.wslconfig`:

```ini
[wsl2]
memory=4GB
swap=4GB
```

Перезагрузи компьютер (Docker Desktop этого всё равно потребует), запусти Docker Desktop и дождись статуса «Engine running». Проверь в новом терминале:

```powershell
docker --version; docker compose version; uv --version; ollama --version; node --version
docker run --rm hello-world
```

**Шаг 2. Проект**

```powershell
mkdir C:\Users\bugae\onegin
cd C:\Users\bugae\onegin
git init
uv init --python 3.12
```

`uv` сам скачает Python 3.12. Удали созданный `main.py`. В `.gitignore` допиши строки: `.env`, `node_modules/`, `web/dist/`. Создай `.dockerignore` со строками: `.venv`, `.git`, `node_modules`, `web/dist`.

**Шаг 3. Модели**

```powershell
ollama pull qwen3:8b
ollama pull bge-m3
```

**Шаг 4. Контекст 8k** (по умолчанию он маленький)

```powershell
setx OLLAMA_CONTEXT_LENGTH 8192
```

Затем выйди из Ollama через значок в трее и запусти заново.

**Шаг 5. Проверка**

```powershell
ollama run qwen3:8b "Привет, представься в двух предложениях" --verbose
ollama ps
curl.exe http://localhost:11434/v1/models
```

Что должно быть: `ollama ps` показывает `100% GPU`; в выводе `--verbose` запиши `eval rate` (токены/сек) — это наша отправная точка. Пришли мне эти цифры.

**Шаг 6. Первый коммит**

```powershell
git add .; git commit -m "Init project"
```

Подводные камни:
- В PowerShell `curl` — это псевдоним другой команды, пиши именно `curl.exe`.
- Если `ollama ps` показывает CPU — обнови драйвер NVIDIA.
- Если Docker Desktop не стартует — проверь, что в BIOS включена виртуализация, и выполни `wsl --update`.
- Docker Desktop бесплатен для личного использования.
- Qwen3 по умолчанию «размышляет» перед ответом, это медленно. Для обычных реплик отключим на этапе 1.

---

## Этап 1. Ядро: текстовый чат (2–3 вечера)

**Шаг 1. Зависимости**

```powershell
uv add fastapi "uvicorn[standard]" openai pydantic-settings aiosqlite
```

**Шаг 2. Файлы, по порядку**

1. `core/__init__.py` (пустой) и такие же в подпапках.
2. `.env`: `LLM_BASE_URL=http://host.docker.internal:11434/v1`, `LLM_MODEL=qwen3:8b`, `DATA_DIR=/app/data`. Адрес `host.docker.internal` — это «хост-машина изнутри контейнера»; `localhost` там указывал бы на сам контейнер.
3. `core/config.py` — класс `Settings(BaseSettings)`, читающий `.env`.
4. `core/llm/client.py` — `AsyncOpenAI(base_url=..., api_key="ollama")` и функция, отдающая поток токенов.
5. `core/agent/prompts.py` — системный промпт: кто такой Онегин, текущие дата и время, «отвечай кратко».
6. `core/db.py` — таблицы `conversations` и `messages`, функции «сохранить» и «загрузить историю».
7. `core/agent/loop.py` — агентный цикл (скелет ниже).
8. `core/cli.py` — бесконечный `input()` → цикл → печать токенов.
9. `core/app.py` — FastAPI с WebSocket `/ws/chat`.

Скелет цикла — сердце проекта:

```python
async def run(messages, tools, max_steps=6):
    for _ in range(max_steps):
        reply = await llm.chat(messages, tools=tools)   # со стримингом
        messages.append(reply)
        if not reply.tool_calls:
            return reply                                 # финальный ответ
        for call in reply.tool_calls:
            result = await registry.execute(call)        # ошибки тоже возвращаем
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
```

Важно: если модель прислала невалидный JSON в аргументах — не падать, а вернуть ей текст ошибки, она исправится на следующем шаге.

**Шаг 3. Dockerfile и compose.yml**

`Dockerfile`:

```dockerfile
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY core ./core
CMD ["uv", "run", "--no-sync", "uvicorn", "core.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

`compose.yml`:

```yaml
services:
  core:
    build: .
    env_file: .env
    environment:
      WATCHFILES_FORCE_POLLING: "true"   # иначе --reload не видит правки с Windows
    ports:
      - "127.0.0.1:8000:8000"            # только локально; наружу — через Tailscale
    volumes:
      - ./core:/app/core                 # код с хоста, чтобы не пересобирать образ
      - onegin_data:/app/data
    command: uv run --no-sync uvicorn core.app:app --host 0.0.0.0 --port 8000 --reload

volumes:
  onegin_data:
```

**Шаг 4. Запуск и проверка**

```powershell
docker compose up --build              # сервер; логи в этом окне
docker compose run --rm core uv run --no-sync python -m core.cli   # CLI, в другом окне
docker compose logs -f core            # логи, если запускал с -d
```

Готово, когда: диалог в CLI идёт со стримингом, после `docker compose down` и повторного `up` история на месте, на вопрос «как тебя зовут» отвечает «Онегин».

Подводные камни Docker:
- После каждого `uv add` нужен `docker compose up --build` — зависимости живут в образе, а не в примонтированной папке.
- Базу SQLite держим в томе `onegin_data`, а не в папке Windows: на примонтированных Windows-папках у SQLite ломаются блокировки.
- `docker compose down -v` **удаляет том с базой**. Без `-v` данные сохраняются.
- Если Core не достучался до Ollama: `setx OLLAMA_HOST 0.0.0.0` и перезапусти Ollama.

Про личность: лёгкая ирония и вежливая отстранённость в духе персонажа — да, стихи и архаизмы в каждом ответе — нет, быстро надоест. Отключение размышлений: добавь `/no_think` в системный промпт.

---

## Этап 2. PWA и доступ с iPhone (2–3 вечера)

**Шаг 1. Фронтенд**

```powershell
cd C:\Users\bugae\onegin
npm create vite@latest web -- --template react-ts
cd web
npm install
npm install -D vite-plugin-pwa
```

**Шаг 2. Что написать**

1. `web/vite.config.ts` — подключить `VitePWA` (имя «Онегин», `display: "standalone"`, иконки 192 и 512) и прокси `/ws` и `/api` на `localhost:8000`.
2. Экран чата: поле ввода, лента сообщений, WebSocket к `/ws/chat`, вывод токенов по мере прихода.
3. Список диалогов и строка «Онегин вызывает инструмент…».
4. В `core/app.py` — раздача `web/dist` через `StaticFiles` (один origin, без CORS).
5. В `Dockerfile` — первая стадия `FROM node:22-slim AS web`, которая делает `npm ci && npm run build`, и `COPY --from=web /web/dist ./web/dist` в основной стадии. Так собранный фронтенд попадает в образ.

**Шаг 3. Сборка и запуск**

```powershell
npm run dev                  # разработка: из папки web, с горячей перезагрузкой
cd ..
docker compose up --build    # «боевой» вариант: фронтенд внутри образа
```

**Шаг 4. Tailscale**

1. Войди в Tailscale на ноутбуке и на iPhone под одним аккаунтом.
2. В админ-консоли Tailscale включи MagicDNS и HTTPS Certificates.
3. Выполни:

```powershell
tailscale serve --bg 8000
tailscale serve status
```

Команда покажет адрес вида `https://<ноутбук>.<tailnet>.ts.net`.

**Шаг 5. Проверка**

На iPhone отключи Wi-Fi, открой адрес в Safari → «Поделиться» → «На экран Домой». Готово, когда приложение открывается без адресной строки и Онегин отвечает через мобильную сеть.

HTTPS обязателен: без него на iOS не работают микрофон, service worker и push.

---

## Этап 3. Инструменты, память, органайзер (4–5 вечеров)

```powershell
uv add apscheduler sqlalchemy pywebpush sqlite-vec
uv run vapid --gen        # ключи для push
```

Шаги:
1. `tools/registry.py` — декоратор, превращающий функцию с Pydantic-моделью в JSON Schema; флаг `requires_confirmation`.
2. Карточка подтверждения в PWA: опасное действие ставит цикл на паузу до «Разрешить / Отклонить».
3. Инструменты: заметки, задачи, напоминания, таймеры.
4. `scheduler.py` (APScheduler с хранилищем в SQLite) и `push.py` (Web Push); кнопка «Включить уведомления» в PWA.
5. Память: файл-профиль с фактами о тебе (всегда в промпте, пополняется инструментом `remember`) и сводки прошлых диалогов с поиском по эмбеддингам `bge-m3`.
6. `evals/` — 30–40 запросов на русском с ожидаемым инструментом и скрипт прогона. Запускать при каждой смене модели или промпта.

Готово, когда: «напомни через 2 минуты выключить чайник» → push на заблокированный iPhone; в новом диалоге Онегин помнит факт из прошлого.

Подводные камни: push на iOS работает только у приложения с домашнего экрана и только после нажатия кнопки; модель путается, если инструментов больше 10–12 — подавать только нужную группу.

## Этап 4. Голос (4–5 вечеров)

```powershell
uv add faster-whisper piper-tts
cd web; npm install @ricky0123/vad-web
```

Шаги:
1. `voice/stt.py` — `faster-whisper`, сначала `device="cpu"`, `compute_type="int8"`; сравнить модели `small` и `large-v3-turbo` по скорости.
2. `voice/tts.py` — Piper с русским голосом (например, `ru_RU-dmitri-medium`).
3. PWA: кнопка «зажми и говори» → аудио на сервер → текст → агент → синтез по предложениям.
4. Режим «свободные руки» с VAD в браузере и перебиванием.
5. На iPhone: команда Siri, открывающая PWA с `?voice=1`.

Готово, когда: от конца фразы до начала голосового ответа ≤ 2,5 с, время STT / LLM / TTS пишется в лог.

Подводные камни: Safari пишет `audio/mp4`, а не webm; звук на iOS «разблокируется» первым касанием; слушать «Онегин» в фоне iPhone не умеет.

## Этап 5. Почта и календарь (3–4 вечера)

```powershell
uv add google-api-python-client google-auth-oauthlib
```

Шаги:
1. Google Cloud Console: создать проект, включить Calendar API и Gmail API, создать OAuth-клиент типа «Desktop», скачать `credentials.json` и положить в том: `docker compose cp credentials.json core:/app/data/`.
2. Перевести приложение из «Testing» в «In production» — иначе токен умирает каждые 7 дней.
3. Инструменты: события на период, создать/перенести событие, непрочитанные письма, поиск по почте, черновик ответа.
4. Отправка писем и удаление событий — только через подтверждение.
5. Утренний брифинг по расписанию: календарь + задачи + почта → push.

Готово, когда: «что у меня завтра?» совпадает с календарём, созданное событие видно на телефоне.

## Этап 6. Поиск и ресёрч (3–4 вечера)

```powershell
uv add trafilatura pymupdf
```

Шаги:
0. Добавить в `compose.yml` сервис `searxng` (образ `searxng/searxng`), в его `settings.yml` включить формат `json`. Core обращается к нему по имени сервиса: `http://searxng:8080`.
1. Инструменты `web_search` (через SearXNG), `fetch_page`, чтение PDF.
2. Режим ресёрча: несколько запросов → чтение источников → сводка со ссылками (здесь размышления модели включить).
3. Индексатор твоих папок: чанки → `bge-m3` → `sqlite-vec`.

Готово, когда: ответ на свежий вопрос идёт со ссылками; находится фрагмент из твоей заметки.

**Безопасность:** страницы, письма и документы — недоверенный текст. Пока он в контексте, любое действие с последствиями требует подтверждения.

## Этап 7. Управление ПК (3–4 вечера)

```powershell
uv add --group pc pycaw pywin32 mss websockets vosk sounddevice
winget install --id voidtools.Everything -e
```

Шаги:
1. `pc_agent/` — процесс, который подключается к Core по WebSocket с токеном и объявляет свои инструменты. Запускается **на хосте, не в Docker**: `uv run --group pc python -m pc_agent`, адрес Core — `ws://localhost:8000`.
2. Инструменты: запустить программу, открыть файл/URL, громкость и медиа, окна, буфер обмена, скриншот, поиск файлов, блокировка/сон.
3. Белый список программ и папок; произвольная команда PowerShell — всегда с подтверждением.
4. Wake word «Онегин»: Vosk с маленькой русской моделью и словарём из одного слова — готовых моделей под это имя нет, а такой способ работает без обучения.
5. Автозапуск через Планировщик заданий Windows.

Готово, когда: с iPhone «открой VS Code и сделай потише» выполняется на ноутбуке; «удали папку X» показывает карточку подтверждения; «Онегин, который час?» срабатывает с микрофона ноутбука.

## Этап 8. Переезд на сервер (2–3 вечера, когда появится железо)

1. Склонировать репозиторий на сервер; в `compose.yml` добавить сервис `ollama` с доступом к GPU (NVIDIA Container Toolkit).
2. Перенести том: `docker run --rm -v onegin_data:/d -v ${PWD}:/b alpine tar czf /b/data.tgz -C /d .` на ноутбуке, распаковать так же на сервере.
3. Сменить `LLM_BASE_URL` на `http://ollama:11434/v1`, поставить Tailscale на сервер; в конфиге PC Agent сменить адрес Core.
4. С GPU от 24 ГБ: модель класса 30B, более качественный голос, STT на GPU.
5. Ежедневный бэкап тома `onegin_data` той же командой `tar`.

Готово, когда: ноутбук выключен, а Онегин на iPhone отвечает и напоминания приходят; `evals/` проходят на новой модели.

---

## Сквозные правила

- Секреты — только в `.env` и в томе `onegin_data`; в образ они не попадают.
- Зависимости добавляются на хосте через `uv add`, после этого — `docker compose up --build`.
- Доступ — только из tailnet; PC Agent дополнительно по токену.
- Логировать каждый запрос к LLM и каждый вызов инструмента.
- Коммит после каждого работающего шага.

## Итоговая проверка

1. `evals/` — не ниже 85% верных вызовов.
2. С iPhone через мобильную сеть, голосом: «что у меня сегодня и напомни в шесть позвонить маме» → сводка голосом, push в 18:00.
3. Ресёрч-вопрос → ответ со ссылками.
4. Управление ПК с телефона и отказ через карточку подтверждения.
5. После рестарта Core история, память и напоминания на месте.

## С чего начать

Этап 0, шаги 1–5. Пришли вывод `ollama ps` и `eval rate` — по ним решим, оставляем `qwen3:8b` или пробуем другую модель, и я выдам детальную инструкцию по коду этапа 1.
