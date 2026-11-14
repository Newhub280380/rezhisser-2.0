# Облачный бэкенд генерации для Режиссёр 2.0 4.1.1

Принцип: **ничего не удаляем**. Облако — ещё один движок рядом с локальными
моделями и ComfyUI. Интерфейс Studio / Director / Editor остаётся прежним,
добавляется только переключатель провайдера и поля ключей.

## Где сейчас вызывается генерация

| Кто | Путь |
|---|---|
| Studio | UI `api.submitGeneration` → `POST /api/v1/generate` (`app/launch.py`) → задача в `_jobs` → `_run_generation(job_id)` → `wgp.generate_video(...)` |
| Director | `services/director_pipeline.py::_submit_and_wait` создаёт задачу в тех же `_jobs` и вызывает тот же `launch._run_generation` (картинки `image_mode=1`, видео `image_mode=0`, `image_start`/`image_end`) |
| ComfyUI (прецедент) | `_run_generation` в начале отдаёт задачу в `_comfy_adapter.execute(job)` — облако встраивается тем же способом |
| LLM Director | `_ensure_llm_loaded` → `llm_service.load_model(provider=...)` → `generate()` → `{url}/v1/chat/completions`. Провайдер `remote` (OpenAI-совместимый) уже есть |

Единая точка — `_run_generation`. Ветка облака там покрывает и Studio, и Director.

## Что добавляем

1. `app/services/cloud_generation.py` — провайдеры (из прошлой ветки, без её удалений):
   - MiniMax API: видео `MiniMax-H3` (`/v2/video_generation`), картинки `MiniMax-H3-Image` (`/v1/image_generation`);
   - fal: `minimax/h3/*` видео, `fal-ai/moss-image` картинки;
   - MuAPI: `minimax-h3-*` видео/картинки, `qwen2-1-image-to-image` правка по картинке.
   - Выбор: `CLOUD_PROVIDER` в `.env` (`local` | `minimax` | `fal` | `muapi`).
   - `execute(job)`: берёт `prompt`, `image_start`/`image_refs`, `resolution`, `video_length`, `image_mode` из параметров задачи, пишет файл в `out_dir`, завершает задачу через `finish_job` — галерея и Director видят результат как обычный.
2. `launch.py`:
   - ветка в `_run_generation`: если провайдер облачный — `cloud_generation.execute(...)`, локальная модель не грузится;
   - `GET/PUT /api/v1/cloud-config` — провайдер, флаги «ключ задан», запись ключей в `.env` (значения ключей наружу не отдаются);
   - LLM: если в `.env` заданы `LLM_BASE_URL` + `LLM_API_KEY` и в настройках не указан другой удалённый сервер — `_ensure_llm_loaded` использует `remote` с этими значениями.
3. UI: компонент `CloudEngineControl` (выбор провайдера + ключи через существующий `ApiKeyField`), показан в Studio (сайдбар), в Director (панель) и в Настройках.
4. `.env.example` — пустые ключи. `.env` в `.gitignore`.

## Запуск без GPU

- `wgp` не грузит веса при импорте (preload выключен по умолчанию) — модели грузятся только при локальной генерации.
- Окружение на этом ПК: torch CPU + requirements без тяжёлых GPU-пакетов (onnxruntime-gpu, insightface, pyannote, whisper и т.п.). Если на старте падает импорт такого пакета — делаем импорт ленивым (перенос внутрь функции), не удаляем.

## Статус (2026-11-13)

| Пункт | Состояние |
|---|---|
| Ветка облака в `_run_generation` (Studio, Director, операции Editor через очередь) | готово |
| MiniMax / fal / MuAPI, первый и последний кадр | готово, поля сверены с документацией |
| Облачная LLM из `.env` | готово |
| `/api/v1/cloud-config` + UI в Studio, Director, Настройках | готово |
| Старт без CUDA | готово (`wgp.py`: одна строка); баннер без GPU в облачном режиме — предупреждение |
| Editor: анимированные титры в облаке | готово (блок «установите модель» только для Local) |
| Слияние ветки помощника | готово (`CLOUD_HOOKS.md`, `CLOUD_KEYS.md`, `tests/test_cloud_call_sites.py`) |
| Пробный запуск UI (Playwright + Chrome) | готово: переключатель в Studio, Director (строка Engine), Настройки → Integrations |
| Крючки в `editor_*` | не нужны: по `CLOUD_HOOKS.md` (ветка помощника) `editor_*` генерацию не вызывают, операции Editor идут через общую очередь; тесты помощника 14/14 на этой ветке |

Сверка с документацией:
- MiniMax H3 видео: `POST /v2/video_generation`, `content[]` с `role` first_frame/last_frame, `ratio` только для текст→видео, `resolution` 768P | 2K, `duration` 4–15. Опрос `/v2/query/video_generation/{id}` → `task.content.url`.
- MiniMax H3-Image: `POST /v1/images/generations`; с референсом — `/v1/images/edits` (`images[].image_url`). Ответ `data[0].url`.
- fal: `minimax/h3/text-to-video` (`aspect_ratio`), `minimax/h3/image-to-video` (`image_url`, `end_image_url`), разрешения 480P/768P/2K/4K; `fal-ai/moss-image` — только текст→картинка.
- MuAPI: `minimax-h3-text-to-video`, `minimax-h3-image-to-video` (`image_url`, `last_image_url`), `qwen2-1-image-to-image` (`images_list`). Поля `minimax-h3-image` в документации не описаны.

Облако честно отказывает (понятная ошибка, а не тихая подмена) для: исходного видео, масок,
аудио-гайда, Viggle, repaint/outpaint/recast, blend, генерации звука и клипов длиннее 15 с.

## Не трогаем

Автозапуск, Планировщик, модели `app/models`, `wgp.py`-логику генерации, Editor, тесты.

## Проверка

- `git diff --stat` перед каждым коммитом — без удалённых файлов.
- Тест `tests/test_cloud_generation.py`: тела запросов провайдеров и выбор провайдера (без сети).
- Запуск `launch.py` с `CUDA_VISIBLE_DEVICES=""`, ответ `/api/v1/cloud-config`, UI собирается.
