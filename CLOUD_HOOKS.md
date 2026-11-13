# Хуки облачного движка — где именно подключено

Ветка `rezhisser-2.0-helper`, HEAD `c359133`. Номера строк — по этому коммиту.
Всё, что ниже, проверено по фактическому коду (`git diff main..HEAD`), а не по памяти.

Коммиты поверх `main`:

| Коммит | Что делает |
|---|---|
| `6a00b23` | Add cloud generation engine beside native and ComfyUI |
| `6a2335f` | Start without CUDA: treat missing GPU as capability 0.0 |
| `ae9325b` | Add cloud backend picker to Studio, Director and Settings |
| `c359133` | Use official MiniMax H3-Image endpoints (images/generations, images/edits) |

`git diff --stat main..HEAD` → 11 файлов, **+670 / −1**. Единственное удаление —
строка `gpu_major, gpu_minor = ...` в `wgp.py`, заменена на условную (см. хук 5).
Ни один файл не удалён.

## 1. Точка входа генерации (главный хук)

`app/launch.py:27720-27726`, внутри `_run_generation`, сразу **после** ветки ComfyUI
(`27717-27718`) и **до** подготовки Viggle (`27728`):

```python
# Cloud engine: same queue/job contract, no local weights are loaded.
from services import cloud_generation
cloud_provider = job.setdefault("cloud_provider", cloud_generation.active_provider())
if cloud_provider:
    return cloud_generation.execute(
        job, cloud_provider, wgp.get_model_def(job["params"].get("model_type")), finalize=finalize,
    )
```

Почему это одна точка на всё: и Studio (`POST /api/v1/generate` → `_jobs` → `_run_generation`),
и Director (`director_pipeline._submit_and_wait` → тот же `_run_generation`) идут через этот
worker. `job.setdefault(...)` фиксирует провайдера на задаче: переключение `CLOUD_PROVIDER`
в `.env` во время уже запущенной задачи маршрут не меняет.

Порядок веток в worker: ComfyUI → **облако** → Viggle → локальный `wgp`.

## 2. Настройки: GET/PUT `/api/v1/cloud-config`

`app/launch.py:8381-8399`.

- `GET` → `cloud_generation.public_config()`: провайдер, `ready` по каждому провайдеру,
  булевы флаги «ключ задан», `llm_base_url`, `llm_model`. Значения ключей не отдаются никогда.
- `PUT` → валидирует `CLOUD_PROVIDER` (`local | minimax | fal | muapi`, иначе 400),
  затем `cloud_generation.save_env(body)` — пишет только ключи из белого списка,
  остальные строки `.env` не трогает.

## 3. Облачная LLM для планировщиков Director/Studio

`app/launch.py:9253-9258`, внутри `_ensure_llm_loaded`, после чтения настроек LLM:

```python
from services.cloud_generation import llm_override
cloud_llm = llm_override() if desired_provider == "local" else None
if cloud_llm:
    desired, desired_provider = cloud_llm["model_id"], cloud_llm["provider"]
    desired_remote_url, desired_api_key = cloud_llm["remote_url"], cloud_llm["api_key"]
```

Срабатывает только если `CLOUD_PROVIDER != local` **и** в `.env` есть `LLM_BASE_URL` +
`LLM_API_KEY`, **и** в настройках выбран провайдер `local`. Явно выбранный удалённый
провайдер в настройках всегда главнее.

## 4. Сам движок

`app/services/cloud_generation.py` — новый файл, 365 строк, без импорта torch:

| Блок | Строки | Что |
|---|---|---|
| settings | 37-98 | `load_env`, `env`, `save_env`, `ready`, `active_provider`, `public_config`, `llm_override` |
| HTTP | 103-144 | `post_json`, `get_json`, `data_uri`, `download`, `poll` |
| request shape | 149-191 | `request_from_params`, `_ratio`, `_first_image` |
| MiniMax | 196-251 | видео `/v2/video_generation` + polling `/v2/query/video_generation/{id}`; картинки `/v1/images/generations` и `/v1/images/edits` |
| fal | 254-292 | очередь `queue.fal.run/{model}` → `status_url` → `response_url` |
| MuAPI | 295-334 | `POST /{slug}` → `GET /predictions/{id}/result` |
| job bridge | 342-362 | `execute(job, provider, model_def, finalize)` → `update_job` / `finish_job` |

`execute()` пишет файл в `job["out_dir"]` под именем
`{timestamp}_cloud_{provider}_{job_id}.{png|mp4}`, ставит
`params["generation_engine"] = "cloud:{provider}"` и завершает задачу через
`finish_job(...)` — галерея и Director видят результат как обычный локальный.

## 5. Старт без CUDA

`app/wgp.py:2695` — одна строка:

```python
gpu_major, gpu_minor = torch.cuda.get_device_capability(...) if torch.cuda.is_available() else (0, 0)
```

Без GPU `launch.py` поднимается, локальная генерация просто недоступна, облачная работает.
Логика генерации `wgp.py` не тронута.

## 6. UI

| Файл | Что |
|---|---|
| `ui/src/components/shared/CloudEngineControl.tsx` | новый, 101 строка: селект провайдера; при `full` — ключи через `ApiKeyField` + поля облачной LLM |
| `ui/src/api/client.ts:2344-2370` | `CloudConfig`, `fetchCloudConfig`, `updateCloudConfig` |
| `ui/src/components/Sidebar/Sidebar.tsx:295` | монтирование в Studio (video/image workspace) |
| `ui/src/components/Sidebar/DirectorChat.tsx:2889` | монтирование в панель Director |
| `ui/src/components/SettingsDrawer/ServicesSettingsPanel.tsx:702-703` | секция «Cloud» с `full` |

Ключи в UI не показываются: `ApiKeyField` получает только `isSet` из `public_config()`.

## 7. Конфигурация и тесты

- `.env.example` — новый файл, 30 строк, пустые ключи (полный разбор — `CLOUD_KEYS.md`).
- `.gitignore:134-137` — `/.env` и `/.env.*` игнорируются, `.env.example` / `.env.sample` — исключения.
- `tests/test_cloud_generation.py` — 57 строк, без сети: маппинг параметров, тела запросов
  всех трёх провайдеров, запись/чтение `.env`, `llm_override`.
- `tests/test_cloud_call_sites.py` — проверяет сами хуки из этого документа (что ветка
  облака стоит на месте, что Director идёт через неё, что Editor её не касается).

## Director — отдельного хука нет, и не нужно

`app/services/director_pipeline.py` **не изменён**. Director получает тот же worker:

- `director_pipeline.init(...)` (`5891-5911`) принимает `run_gen_fn` и кладёт его в `_run_generation`;
- в `launch.py:852-862` при инициализации передаётся `run_gen_fn` / `terminal_callback`;
- `_submit_and_wait` создаёт задачу в общих `_jobs` и в потоке вызывает
  `_run_generation(job_id)` (`director_pipeline.py:6019`).

Поэтому облачная ветка покрывает Director целиком — картинки (`image_mode=1`),
видео (`image_mode=0`), `image_start` / `image_refs`. Дублировать хук в `director_*` нельзя:
это раздвоит маршрут и сломает `generation_engine_snapshot`.

## Editor — хука нет

`app/services/editor_*.py` **не изменены**, `cloud_generation` там не упоминается
(проверено grep'ом по всем `editor_*.py` — 0 совпадений). Editor — локальный монтаж,
экспорт и графика; облачная генерация в него не встраивается.

## Что не тронуто

`app/models`, логика генерации `wgp.py` (кроме строки 2695), ComfyUI-адаптер,
автозапуск, планировщик, все существующие тесты.

## Проверка

```powershell
python -m pytest tests/test_cloud_generation.py tests/test_cloud_call_sites.py -q
git diff --stat main..HEAD          # без удалённых файлов
```

## Открытый вопрос по веткам

На момент проверки (HEAD `c359133`) ветка `rezhisser-2.0-full`
(рабочая копия `C:\Users\User\workspace\rezhisser-2.0`) ушла вперёд на 5 коммитов,
которых **здесь нет**:

- `daf50de` — Match fal/MiniMax/MuAPI request fields to their docs
- `ef905b8` — Cloud: last-frame support; reject masks/source video/repaint/outpaint/blend/audio clearly
- `6254ebc` — Cloud: refuse clips over 15 s instead of clamping silently
- `a6b7d44` — Test: cloud branch wired before native generation in launch.py
- `6bbe55c` — Test: Director child job completes through the cloud engine

Суммарный diff этих коммитов: `app/services/cloud_generation.py` (+50/−11)
и `tests/test_cloud_generation.py` (+96/−11). Оба файла вне зоны помощника,
поэтому перенос не делался: в этой ветке тела запросов ещё не сверены
с документацией провайдеров, нет отказа от масок / source video / repaint /
outpaint / blend / audio и нет ограничения длительности 15 с.
Ветку `rezhisser-2.0-full` по условию задачи не трогал.
