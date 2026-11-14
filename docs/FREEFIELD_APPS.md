# Приложения Freefield в Режиссёре 2.0

Кнопка **«Приложения»** (справа внизу, над «Помощником») открывает каталог в духе Freefield
(github.com/neuregex/freefield): одно приложение на одну функцию, разделы Видео / Фото / Звук / Помощники.

* **работает** — запрос уходит в облако fal (локального GPU нет). Сначала можно бесплатно нажать
  «Проверить запрос» (показывает точный запрос, ничего не отправляет). «Запустить» платный и спрашивает подтверждение с ценой.
* **скоро** — карточка без кнопок, на ней написано, чего не хватает.

Код: `app/services/freefield_apps.py` (каталог, проверка полей, сборка запроса, dry-run, запуск),
маршруты `/api/v1/freefield/...` в `app/launch.py`, интерфейс `ui/src/components/FreefieldApps/`.
Тесты: `tests/test_freefield_apps.py` — запросы сверяются со схемами fal (сохранены 2026-11-14 в
`tests/fixtures/freefield_fal_schemas/`), запуск — с подменённым клиентом fal, без реальных генераций.

## Пять главных

| Приложение | Freefield | fal endpoint | Цена (страница fal, 2026-11-14) |
|---|---|---|---|
| Замена персонажа (Recast) | recast | fal-ai/wan/v2.2-14b/animate/replace | $0.04/с 480p · $0.06/с 580p · $0.08/с 720p |
| Recast на SCAIL-2 + SAM 3.1 | recast | — скоро | у fal нет публичного API SCAIL-2; нужен RunPod + ComfyUI |
| Перенос движения (Wan Animate) | motion-transfer | fal-ai/wan/v2.2-14b/animate/move | как выше |
| Переозвучка (DubIt) | dub | — скоро | нужна LTX-2.5 + DubIt IC-LoRA на своём GPU |
| Дубляж (облако VEED) — замена DubIt пока | dub | veed/dubbing | $0.11 за секунду исходника |
| Говорящее фото (текст) | speak | lightricks/ltx-2.5/image-to-video/fast | $0.09/с 720p · $0.13/с 1080p |
| Говорящее фото (свой звук) | talking | lightricks/ltx-2.5/audio-to-video/fast | $0.13 за секунду звука |
| Улучшить видео до 4K | upscale-video | fal-ai/seedvr/upscale/video | $0.001 за мегапиксель (5 с 4K ≈ $1) |

## Остальное

Работает: LTX-2.5 видео со звуком из фото/текста, MiniMax H3 продление, BiRefNet фон (фото и видео),
SAM 3 трекинг, FLUX Klein (картинка и персонаж), Qwen Edit (ракурсы, следующая сцена), Krea 2 стиль,
Z-Image Turbo, MiniMax Music 3, Stable Audio 3 SFX, SeedVR2 фото.
Скоро: Gemma 4 (подготовка промпта), Wan-эффекты с LoRA, переснять ракурс (H3+MoGe), MediaPipe лица, Qwen relight.

## Как подключить к Режиссёру 1.0 и HQ (план)

* **Режиссёр 1.0** (`seedance-ai-studio`, Python): файл `freefield_apps.py` переносится как есть в
  `director/freefield_apps.py`; клиент fal — тонкая обёртка над `director/transport.py` (как в `fal_route.py`),
  маршруты `GET /api/director/freefield/apps`, `POST .../dry-run`, `POST .../run` (с confirm=true, как уже принято в R1)
  добавляются в `director/server.py` рядом с `/api/director/tasks`; карточки — в `director/ui/director-client.js`.
* **HQ** (`beautyart-hq`, Node): каталог выгружается в JSON, сборщики запросов переписываются в
  `server/engine/freefield.mjs`; отправка идёт через уже существующий `fal.run` в `server/engine/providers.mjs`;
  новые модели дописываются в `server/engine/models.mjs`; экран — раздел «Приложения» внутри плитки «Режиссёр»
  мастерской (`src/workshop/Home.tsx`, экран `script`).
