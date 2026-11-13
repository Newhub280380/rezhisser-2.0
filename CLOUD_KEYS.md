# Ключи облачных провайдеров — где лежат и как задаются

Ветка `rezhisser-2.0-helper`, HEAD `c359133`. Всё сверено с `app/services/cloud_generation.py`
и `.env.example`, не по памяти.

## Где хранятся

Один файл — **`.env` в корне репозитория**, путь вычисляется как
`Path(__file__).resolve().parents[2] / ".env"` (`cloud_generation.py:20`).

- `.env` **нет в репозитории** и в этой рабочей копии его нет — файл создаётся из `.env.example`.
- `.gitignore:134-137`: `/.env`, `/.env.*` игнорируются; исключения — `/.env.example`, `/.env.sample`.
- Читается один раз при импорте: `load_env()` в конце модуля (`cloud_generation.py:365`),
  парсер `KEY=VALUE`, `#` — комментарий.
- **Приоритет: реальное окружение процесса главнее файла** (`os.environ.setdefault`).
  Если переменная экспортирована в шелле / Pinokio / systemd — значение из `.env` её не перезапишет.
- Ключи никогда не уходят наружу: `public_config()` возвращает только `bool(env(key))`,
  в UI приходит «ключ задан / не задан».

## Два класса ключей

| Класс | Переменные | Кто пишет |
|---|---|---|
| Секреты (`SECRET_KEYS`) | `MINIMAX_API_KEY`, `FAL_KEY`, `MUAPI_API_KEY`, `LLM_API_KEY` | UI (`PUT /api/v1/cloud-config`) или вручную в `.env` |
| Обычные (`PLAIN_KEYS`) | `CLOUD_PROVIDER`, `LLM_BASE_URL`, `LLM_MODEL` | то же |

`save_env()` (`cloud_generation.py:52-67`) пишет **только** эти 7 имён; любой другой ключ
из тела запроса молча отбрасывается (проверено тестом `EVIL` → не попадает в файл).
Остальные строки `.env` остаются как были, включая комментарии; отсутствующие ключи
дописываются в конец.

## Секреты по провайдерам

| Провайдер | Переменная | Заголовок запроса | Готовность |
|---|---|---|---|
| MiniMax API | `MINIMAX_API_KEY` | `Authorization: Bearer <key>` | `ready("minimax")` |
| fal | `FAL_KEY` | `Authorization: Key <key>` | `ready("fal")` |
| MuAPI | `MUAPI_API_KEY` | `x-api-key: <key>` | `ready("muapi")` |

`ready(name)` = провайдер известен и все его ключи непустые. Если выбран провайдер без ключа,
`execute()` падает с `CloudError: ... has no API key. Add it in Settings → Cloud.`

## Модели и адреса (читаются из `.env`, но через API не пишутся)

Значения по умолчанию — ровно те, что в коде:

| Переменная | По умолчанию | Где используется |
|---|---|---|
| `CLOUD_PROVIDER` | `local` | выбор движка: `local` / `minimax` / `fal` / `muapi` |
| `MINIMAX_BASE_URL` | `https://api.minimax.io` | база MiniMax |
| `MINIMAX_VIDEO_MODEL` | `MiniMax-H3` | `POST /v2/video_generation` |
| `MINIMAX_IMAGE_MODEL` | `MiniMax-H3-Image` | `POST /v1/images/generations` и `/v1/images/edits` |
| `FAL_VIDEO_MODEL` | `minimax/h3/image-to-video` | fal, есть референс-картинка |
| `FAL_T2V_MODEL` | `minimax/h3/text-to-video` | fal, без картинки |
| `FAL_IMAGE_MODEL` | `fal-ai/moss-image` | fal, картинки |
| `MUAPI_VIDEO_MODEL` | `minimax-h3-image-to-video` | MuAPI, i2v |
| `MUAPI_T2V_MODEL` | `minimax-h3-text-to-video` | MuAPI, t2v |
| `MUAPI_IMAGE_MODEL` | `minimax-h3-image` | MuAPI, картинки |
| `MUAPI_EDIT_MODEL` | `qwen2-1-image-to-image` | MuAPI, правка по картинке |
| `LLM_BASE_URL` | — | облачная LLM для планировщиков |
| `LLM_API_KEY` | — | то же |
| `LLM_MODEL` | `MiniMax-M2` | то же |

Слаги MuAPI сверены только для `minimax-h3-image-to-video` (комментарий в коде,
`cloud_generation.py:303-304`): если другой слаг вернёт 4xx — правится в `.env`,
код менять не нужно.

## Облачная LLM (Director / Studio)

`llm_override()` (`cloud_generation.py:90-98`) включается только при трёх условиях:

1. `CLOUD_PROVIDER` не `local`;
2. заданы и `LLM_BASE_URL`, и `LLM_API_KEY`;
3. в настройках Maestro провайдер LLM = `local`.

Хук стоит в `launch.py:9253-9258` (`_ensure_llm_loaded`). Из `LLM_BASE_URL` срезается
хвостовой `/v1` — `llm_service` добавляет `/v1/chat/completions` сам. Модель по умолчанию
`MiniMax-M2`. Явно выбранный в настройках удалённый провайдер всегда главнее `.env`.

## Как задать ключи

**Через UI (основной путь):** Настройки → Services → **Cloud** (`CloudEngineControl full`):
селект провайдера, поля ключей MiniMax / fal / MuAPI, поля облачной LLM.
Ключи пишутся в `.env` на сервере, обратно приходят только флаги.
Тот же селект без полей ключей стоит в сайдбаре Studio и в панели Director.

**Вручную:** скопировать `.env.example` → `.env`, заполнить нужные строки, перезапустить
`launch.py` (файл читается при импорте модуля).

```powershell
Copy-Item .env.example .env
notepad .env      # заполнить MINIMAX_API_KEY / FAL_KEY / MUAPI_API_KEY
```

Проверка без запуска генерации:

```powershell
python -m pytest tests/test_cloud_generation.py tests/test_cloud_call_sites.py -q
curl.exe http://127.0.0.1:7860/api/v1/cloud-config
```

Ответ отдаёт `provider`, `providers[].ready`, `keys{...: bool}`, `llm_base_url`, `llm_model`.

## Чего в `.env.example` нет и почему

- Токенов HuggingFace/CivitAI и ключей LLM-провайдеров из «Services» — они живут в
  `app/services_config.json` (в `.gitignore:138`), а не в `.env`.
- Значений по умолчанию для `MINIMAX_BASE_URL` и моделей — они **есть** в `.env.example`
  явно, чтобы было видно, что можно переопределить.
- Секретов в примере нет вообще: все четыре секретных ключа пустые.

## Правила безопасности

- `.env` не коммитить, не пересылать, не вставлять в чат/логи.
- В `.env` попадают только 7 имён из белого списка — остальное API отбрасывает.
- Значения ключей не возвращаются ни в `GET /api/v1/cloud-config`, ни в UI.
- Если ключ утёк — перевыпустить в кабинете провайдера и обновить `.env`;
  старый ключ в истории git не появится, потому что файл игнорируется.
