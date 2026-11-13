# STATUS — облачный бэкенд Maestro 4.1.1 (ветка `rezhisser-2.0-full`)

Дата: 2026-11-13. Все коммиты локальные, удалённой пары у ветки нет, `origin` не трогали.
Из Maestro ничего не удалено (`git diff --diff-filter=D main..HEAD` — пусто).

## Итог

Готово всё, что можно сделать без настоящих ключей. **Жёсткий блок:** реальные вызовы
MiniMax / fal / MuAPI не выполнялись — нужны настоящие ключи (и оплата у провайдеров).
Ключ вставляется в http://127.0.0.1:7860/ → Settings → Integrations → Cloud (пишется в `.env`).

## Что сделано

| Пункт | Где |
|---|---|
| Облачный движок рядом с локальным и ComfyUI: MiniMax (H3 видео, H3-Image), fal (`minimax/h3/*`, `fal-ai/moss-image`), MuAPI (`minimax-h3-*`, `qwen2-1-image-to-image`) | `app/services/cloud_generation.py`, ветка в `launch._run_generation` |
| Studio, Director, операции Editor — через одну точку `_run_generation` | `CLOUD_HOOKS.md` |
| Первый и последний кадр, правка картинки по референсу | там же |
| Явный отказ для того, что облако не умеет (исходное видео, маски, аудио-гайд, Viggle, repaint/outpaint/recast, blend, звук, клипы > 15 с) | `cloud_generation.unsupported_reason` |
| Облачная LLM для планировщиков Director (OpenAI-совместимый адрес) | `_ensure_llm_loaded`, `.env` `LLM_*` |
| Ключи в `.env`, пустой `.env.example`, поля в UI; значения ключей наружу не отдаются | `/api/v1/cloud-config` |
| UI: переключатель в Studio, строка «Engine» в Director (в стиле Video/Image), раздел Cloud в Settings → Integrations | `ui/src/components/shared/CloudEngineControl.tsx` |
| Editor: анимированные титры в облаке без скачанных весов | `ui/src/editor/useEditorTitleStore.ts` |
| Запуск без GPU: старт без CUDA; баннер «нет GPU» в облачном режиме — предупреждение | `app/wgp.py` (1 строка), `system_preflight` |
| Слияние ветки помощника | `CLOUD_HOOKS.md`, `CLOUD_KEYS.md`, `tests/test_cloud_call_sites.py` |

## Что проверено

- **Без GPU** (`CUDA_VISIBLE_DEVICES=""`, torch CPU): Maestro стартует; на заглушке MiniMax API из Studio
  прошли видео (первый + последний кадр), картинка, правка картинки; задача с исходным видео
  получила понятный отказ. Облачная LLM ответила через адрес из `.env`.
- **Director:** настоящий `director_pipeline._submit_and_wait` завершает задачу через облако (тест).
- **Тесты:** облачные и помощника — 23/23 (`test_cloud_generation.py` 9, `test_cloud_call_sites.py` 14).
  Полный набор Maestro: 6484 прошло. Все оставшиеся падения сверены с чистым `main` — они не наши:
  - 4 теста требуют `triton` (GPU-ядра) — на torch CPU его нет;
  - `test_editor_projects::test_distinct_preview_builds_use_at_most_two_workers` нестабилен и на `main` (4 падения из 5);
  - `flashvsr_plus_runtime`, `agent_access_desktop_bundle` — падают только в полном прогоне, отдельно проходят.
  26 других падений `main` были из-за системного ffmpeg 9.0 — исправлено окружением (ниже).
- **UI-тесты Maestro (Playwright + Chrome):** 15 тестов Studio/Director/Editor/Settings дают одинаковый
  результат на этой ветке и на `main`. `sidebar_redesign` нашёл падение панели из-за переключателя — исправлено.
- **Пробный запуск интерфейса:** настоящий UI на http://127.0.0.1:7860/ — переключатель виден и работает
  в Studio, Director и Settings → Integrations, ошибок страницы нет.

## Окружение этого ПК (не в git)

- `app/env`: torch 2.10.0+cpu и requirements без тяжёлых GPU-пакетов (на диске было ~8 ГБ).
  Локальная генерация здесь недоступна; для неё нужна штатная установка Maestro через Pinokio.
- `app/ffmpeg_bins`: ffmpeg 7.1.1 (gyan.dev). Maestro берёт его раньше системного ffmpeg 9.0,
  в котором удалены `-vsync` и `-filter_complex_script` — без этого не работали экспорт Editor и склейка Director.
- Maestro запущен отдельным процессом Windows на порту 7860; после перезагрузки ПК сам не стартует
  (автозапуск по условию не настраивался).

## Что осталось

1. **Настоящие ключи** MiniMax / fal / MuAPI и облачной LLM — жёсткий блок, нужен ввод владельца.
   После этого — один реальный прогон на каждого провайдера.
2. Поля MuAPI `minimax-h3-image` в документации не описаны; при ошибке 4xx меняется `MUAPI_IMAGE_MODEL` в `.env`.
3. В галерее остались две плитки «Generation Failed» от тестов на заглушке; удаление записей через API
   заблокировано правилами доступа — закрываются крестиком на плитке.
4. Временная рабочая копия `main` для сравнения тестов: `%TEMP%\cloudmock\base` (git worktree);
   не удалял, потому что в ней ссылки на настоящие `ui/node_modules` и `ui/dist`.
5. Музыка Director, TTS и прочие аудио-модели — только локально (облачные провайдеры для них не заказывались).

## Решения

См. `DECISIONS.md`.
