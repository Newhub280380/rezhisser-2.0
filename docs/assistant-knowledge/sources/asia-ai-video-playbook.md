# 🎬 AI-видео и картинки: полный полевой мануал по азиатскому рынку (Китай + Индия)
### Как перестать сидеть целый день в настройках и получать нужный результат, а не «русскую рулетку»
*Ресерч от 10.10.2026. Все данные — из свежих источников, ссылки в тексте.*

---

## 0. Главный вывод (прочитай хотя бы это)

«Русская рулетка» возникает, когда ты просишь модель сделать всё сразу из одного текстового промпта. Профессионалы в Китае и Индии так не работают. Их «секрет» — **конвейер из 5 шагов, где каждый шаг управляется отдельно**:

```
Идея/сценарий (пишет LLM: DeepSeek/Doubao/любой чат-бот)
   → КЛЮЧЕВЫЙ КАДР как картинка (Seedream / FLUX / Midjourney)
   → Оживление кадра: image-to-video с первым/последним кадром (Kling / Hailuo / Vidu)
   → Звук: нативный (Vidu Q3) или озвучка (ElevenLabs / Fish Audio)
   → Склейка, субтитры, хук в первые 2 секунды (CapCut / Jianying)
```

Ключевой принцип: **текст управляет ЧТО происходит, картинка управляет КАК это выглядит**. Никогда не доверяй внешний вид финального ролика чистому text-to-video — это и есть рулетка (замер: только ~40% чистых кадров при prompt-only подходе, против ~75% при референсном подходе) [4](https://www.vidu.com/blog/keyframing-vs-ai-video-motion-control).

Второй принцип: **один клип = одно действие + одно движение камеры + 4–8 секунд**. Длинные сцены собираются монтажом из коротких кусков, а не одним промптом на 60 секунд.

---

## 1. Карта азиатского рынка: кто есть кто (октябрь 2026)

### 🇨🇳 Китай — здесь сейчас лучшие видео-модели мира

| Модель | Компания | Сильная сторона | Цена входа |
|---|---|---|---|
| **Kling 3.0 / Omni** | Kuaishou | Люди, мимика, сторителлинг, 4K/60fps, до 15 сек, мультикадровые сценарии, @элементы для постоянства персонажа | ~$10/мес [4](https://pixo.video/blog/best-ai-video-generators) |
| **Hailuo 2.3 / H3** | MiniMax | Быстро, дёшево ($0.025/сек), реалистичная физика движения, командные скобки `[Pan left]` для камеры [1](https://minimax-ai.chat/models/minimax-hailuo-director-models/) | ~$10–15/мес |
| **Vidu Q3** | Shengshu | **Нативный звук + диалоги + липсинк в одном поколении**, до 16 сек, мульти-референсы (до 7 фото), лучший для постоянства персонажа [1](https://app.cinevva.com/guides/long-reference-video-models) | от $0.04 за видео [5](https://gptproto.com/ru/blog/most-affordable-ai-video-generator-2026) |
| **Seedance 2.0** | ByteDance (Jimeng/即梦, веб-версия Dreamina) | Лучшее следование промпту, коммерческий/продуктовый контент, мульти-кадр, нативный звук, рендер текста в кадре [4](https://pixo.video/blog/best-ai-video-generators) | от ~$15/мес |
| **Wan 2.6** | Alibaba | Открытые веса + API, звук в 1080p, любимец разработчиков и ComfyUI-сцены [1](https://aivunex.com/best-chinese-ai-video-generators/) | от $0.45/видео |
| **PixVerse** | AIsphere | Короткие вирусные ролики для соцсетей, эффекты [3](https://dtf.ru/kursfinder/4157075-top-10-kitayskikh-neyrosetey) | бесплатно/кредиты |
| **Seedream 4.0/4.5** | ByteDance | **Картинки**: до 6 референсов, идеальный рендер текста (в т.ч. иероглифы), 4K, редактирование промптом [1](https://www.magnific.com/blog/seedream-4-0/) | кредиты |
| **Qwen-Image / Kolors** | Alibaba / Kuaishou | Картинки: лучший в мире рендер текста на изображении (англ.+китайский), открытые веса [1](https://botmonster.com/ai/best-local-image-generation-models-2026/) | бесплатно локально |
| **Doubao / Jimeng** | ByteDance | Чат-бот-ассистент для сценариев, встроен в экосистему Douyin [1](https://pikabu.ru/story/kitayskie_neyroseti_luchshie_servisyi_iskusstvennogo_intellekta_13396614) | бесплатно |

**Важно про доступ:** китайские внутренние версии (即梦 Jimeng, Kling CN) часто мощнее/дешевле международных, но требуют китайский номер/язык. Международные версии: klingai.com, hailuoai.video, vidu.com, dreamina.capcut.com — доступны отовсюду и понимают английский промпт.

### 🇮🇳 Индия — сильна не моделями, а конвейерами локализации

Индийский рынок ($34.7 млн в 2026, быстро растёт [2](https://www.fortunebusinessinsights.com/ai-video-generator-market-110060)) берёт другим: **мультиязычность на 20+ региональных языков и дешёвое производство вариаций**.

| Инструмент | Специализация |
|---|---|
| **inVideo AI** (Мумбаи) | Текст → готовый ролик целиком (сценарий, футаж, озвучка). Кейс: бренд из Мумбаи сделал AI-видео для 500+ SKU → +38% конверсии карточек, −61% стоимость креатива [1](https://quickuppsoftech.com/ai-video-marketing-2026/) |
| **Fliki** | Текст/блог → видео с озвучкой на 75+ языках [4](https://www.researchgate.net/publication/403254678_Top_10_AI_Video_Generation_Tools_in_2026) |
| **Magicroll AI** | Сделан под Индию: хинди/Hinglish + 35 языков, AI-новости, D2C-реклама, без «кредитных» ловушек [5](https://magicroll.ai/blogs/ai-video-in-india-the-future-of-content-creation-for-2026) |
| **HeyGen / Synthesia** | Говорящие аватары; в Индии массово юзаются EdTech и SaaS для объяснялок [1](https://quickuppsoftech.com/ai-video-marketing-2026/) |
| **ElevenLabs + Murf** | Озвучка на индийских языках для мультиязычных кампаний [1](https://quickuppsoftech.com/ai-video-marketing-2026/) |

**Индийский кейс, который стоит скопировать:** D2C-бренд делает ОДИН шаблон ролика и прогоняет его через хинди (Раджастхан), маратхи (Махараштра) и бенгали → +35% вовлечённости региональной рекламы, −20% затрат [5](https://magicroll.ai/blogs/ai-video-in-india-the-future-of-content-creation-for-2026). Для Казахстана аналог = один шаблон на русский/казахский.

---

## 2. Универсальная формула промпта для видео (работает во всех моделях)

Профессиональные гайды Kling, Hailuo и Vidu сходятся в одной структуре из 6 блоков [1](https://phygital.plus/blog/kling-3-ai-prompts-guide/) [4](https://wan27.org/blog/minimax-h3-prompt-guide):

```
[КАМЕРА: глагол движения] + [КТО: субъект с 2-3 яркими признаками] +
[ЧТО ДЕЛАЕТ: один активный глагол] + [ГДЕ: место/атмосфера] +
[СВЕТ: один источник/настроение] + [СТИЛЬ: один ярлык]
```

### 5 золотых правил (это и есть «секретные методики»)

1. **Глагол движения камеры — в первых 8–10 словах.** Если закопать «dolly» в середине длинного описания, модель его с большой вероятностью проигнорирует [3](https://www.stevenvideo.com/blog/kling-3-cinematic-camera-guide-2026).
   ❌ *«Красивый закат над гаванью Ванкувера с медленным наездом»*
   ✅ *«Slow dolly toward Vancouver harbour at sunset…»*

2. **Только кинематографические глаголы.** «Moves» и «едет» — мусор. Работают: `dolly push, truck left, pan right, orbit, crane up, tracking shot, whip-pan, rack focus, crash zoom, handheld, static shot` [2](https://www.atlabs.ai/blog/kling-3-0-prompting-guide-master-ai-video-generation).

3. **Одно движение камеры + максимум один мягкий модификатор.** Стек из трёх движений = каша. «Slow crane up with a gentle pan right» — потолок [3](https://www.stevenvideo.com/blog/kling-3-cinematic-camera-guide-2026).

4. **Одно действие субъекта на клип.** «Идёт, открывает дверь и садится» в одном 5-секундном клипе = морфинг и «плавление» геометрии. Правило: 4–6 секунд на одно действие [5](https://affiliatemarketingdude.com/hailuo-ai-video-prompt-guide/).

5. **Ограничения формулируй ПОЗИТИВНО.** «The bottle remains upright», «both hands remain visible», «keep silhouette identical» работают лучше длинных негативных списков [2](https://www.videotoprompt.app/posts/hailuo-h3-prompt-guide) [4](https://invideo.io/blog/hidden-secrets-of-kling-ai/).

### Словарь камеры (копируй как есть)

| Команда | Что делает | Когда юзать |
|---|---|---|
| `slow dolly push in` | Плавный наезд на субъекта | Напряжение, герой продукта, эмоция |
| `truck left / right` | Сдвиг камеры вбок | Распаковка витрины, проход по интерьеру |
| `pan left / right` | Поворот камеры на месте | Обзор пейзажа, сцены |
| `tilt up / down` | Наклон вверх/вниз | Масштаб здания, деталь на столе |
| `crane up` | Подъём камеры | Финальный кадр-«раскрытие» |
| `orbit around` | Облёт вокруг объекта | Продукт 360°, герой |
| `tracking shot` | Камера следует за движением | Ходьба, бег, машина |
| `handheld` | Ручная тряска | Реализм, репортаж, экшн |
| `static shot` | Камера неподвижна | Говорящая голова, продукт |
| `dolly zoom in/out` | Эффект Вертиго | Драма, мем-момент |
| `whip pan` | Резкий смазанный поворот | Переход между сценами, энергия |
| `macro close-up` | Макро | Текстуры крема, еда, капли |

⚠️ Не путай **zoom и dolly**: зум меняет перспективу/сжатие, долли — нет. Для «реалистичного» движения почти всегда нужен dolly [3](https://www.stevenvideo.com/blog/kling-3-cinematic-camera-guide-2026).

---

## 3. Чит-листы по моделям (одна страница на модель)

### 🟠 Kling 3.0 (Kuaishou) — «режиссёрская» модель
- Промпт = режиссура: кто → что делает → где → как снимает камера → свет [1](https://phygital.plus/blog/kling-3-ai-prompts-guide/).
- **Multi-Shot с таймкодами:** `Shot 1 (0–3s): … Shot 2 (3–6s): …` + «at the 8th second, the camera zooms» [2](https://www.atlabs.ai/blog/kling-3-0-prompting-guide-master-ai-video-generation).
- **Постоянный персонаж:** режим мульти-референсов — до 7 картинок/элементов, в промпте ссылайся `@Image1` (сцена/стиль) и `@Element1` (запертый персонаж): *«@Grace walks through @Image1 at dusk»* [1](https://app.cinevva.com/guides/long-reference-video-models). К элементу можно привязать голос 5–30 сек — один голос на все шоты.
- Диалоги: именуй персонажей `[Character A: Detective]`, иначе модель путает кто говорит [2](https://www.atlabs.ai/blog/kling-3-0-prompting-guide-master-ai-video-generation).
- Есть встроенный «улучшайзер»: добавить звук, липсинк, анимацию после генерации [5](https://www.unisender.com/ru/blog/krutye-nejroseti-dlya-generacii-video/). ИИ-модели для одежды (виртуальные модели для e-commerce) — прямо в интерфейсе [4](https://www.jivo.ru/blog/ai/kitajskie-nejroseti.html).

### 🔵 Hailuo / MiniMax H3 — быстрая рабочая лошадка
- **Команды камеры в квадратных скобках в начале промпта:** `[Push in] The camera moves slowly toward the subject's face…` [1](https://minimax-ai.chat/models/minimax-hailuo-director-models/). Полный список команд — в таблице выше, он официально поддерживается.
- Формула: `один кадр камеры + одно действие субъекта + одна атмосфера` [1](https://minimax-ai.chat/models/minimax-hailuo-director-models/).
- **Проза до ~40 слов, без негативных промптов.** Негативные списки на H3 вредят (модель «думает» о том, что ты запретил). Пиши как для человека-режиссёра [4](https://wan27.org/blog/minimax-h3-prompt-guide).
- Анатомия действий: не «открывает дверь», а *«берётся правой рукой за ручку, тянет тяжёлую дверь на себя, отступает назад»* [2](https://www.videotoprompt.app/posts/hailuo-h3-prompt-guide).
- От «мультяшности»: добавь `photorealistic, shot on Arri Alexa, cinematic movie style, natural lighting` [3](https://filmora.wondershare.com/ai-prompt/hailuo-ai-prompt-guide.html).
- Тайминг через физику: вместо «медленно смотрит вверх» → «за 10 секунд взгляд поднимается примерно на 20 градусов» [5](https://affiliatemarketingdude.com/hailuo-ai-video-prompt-guide/).

### 🟣 Vidu Q3 (Shengshu) — диалоги и звук из коробки
- Промпт = мини-сценарий + звуковой бриф из 5 блоков: **сцена → персонаж → действие → камера → звук** [1](https://vidu.xin/en/blog/vidu-q3-text-to-video-complete-guide/).
- Реплики **в кавычках**, с манерой подачи: `…says, in a calm French-accented voice, slowly: "Where are you?"` [3](https://prompt-architects.com/blog/257-vidu-q3-prompt-templates).
- **~2.5 слова в секунду — потолок длины реплики**, иначе речь будет скомкана/обрезана [3](https://prompt-architects.com/blog/257-vidu-q3-prompt-templates).
- Называй ВСЕ слои звука явно (реплика + SFX + фон + «тишина»), иначе модель сама придумает звук [3](https://prompt-architects.com/blog/257-vidu-q3-prompt-templates).
- Пара «реплика + видимое действие» (повернулся, шагнул, указал) резко улучшает синхронность [4](https://deevid.ai/blog/vidu-q3-review).
- First/last frame: загрузи два кадра (начало и конец) — модель сама построит движение между ними (~75% годных дублей) [4](https://www.vidu.com/blog/keyframing-vs-ai-video-motion-control).
- До 7 референсных картинок персонажа, можно сохранить в личную библиотеку для серии клипов [2](https://www.vidu.com/blog/ai-animation-generator-from-image).

### 🟢 Seedance 2.0 (ByteDance) — король коммерческого контента
- Лучшее следование промпту среди всех моделей + нативный звук + мультикадр + рендер текста в кадре [4](https://pixo.video/blog/best-ai-video-generators).
- Есть версия **Seedance 2.0 Fast** для дешёвых черновиков: сначала гоняешь идею на Fast, финалку делаешь на обычной [5](https://gptproto.com/ru/blog/most-affordable-ai-video-generator-2026).

### 🟡 Wan 2.x (Alibaba) — для гиков и автоматизации
- Промпт-стиль **как теги датасета** (в отличие от «прозы» у Hailuo), негативные промпты часто необходимы и полезны [4](https://wan27.org/blog/minimax-h3-prompt-guide).
- Открытые веса → локальный запуск, ComfyUI, API [1](https://aivunex.com/best-chinese-ai-video-generators/).

> 💡 Запомни мост: **для H3/Kling пиши как режиссёр актёру; для Wan — как разметчик датасета.** Попытка промптить их одинаково — самая частая причина «гавна на выходе» [4](https://wan27.org/blog/minimax-h3-prompt-guide).

---

## 4. Анти-рулетка: 12 приёмов предсказуемого результата

1. **Сначала картинка, потом видео.** Сгенерируй идеальный статичный кадр (в нужном стиле, свете, композиции) и оживляй его через image-to-video. Это переносит 80% контроля из «рулетки» в детерминированную зону [3](https://diyai.io/ai-tools/video-generation/best-ai-image-to-video-generators/).
2. **First/last frame** там, где известен финал (переходы, «до/после», циклы): задаёшь начало и конец, модель достраивает середину [4](https://www.vidu.com/blog/keyframing-vs-ai-video-motion-control).
3. **Мульти-референсы вместо описаний.** Загружай 3–7 фото персонажа/продукта с разных ракурсов. Статистика годных дублей: ~40% (только текст) → ~75% (референсы) [4](https://www.vidu.com/blog/keyframing-vs-ai-video-motion-control).
4. **Планируй перебор заранее.** Даже у профи «консистентно» означает «большинство дублей», а не «каждый дубль». Закладывай 2–4 генерации на один нужный кадр и выбирай лучший — это дешевле, чем часы настройки [4](https://www.vidu.com/blog/keyframing-vs-ai-video-motion-control).
5. **Меняй ровно ОДНУ переменную за итерацию.** Не понравилось движение — правь только блок камеры, не трогай остальное. Иначе непонятно, что сработало [4](https://wan27.org/blog/minimax-h3-prompt-guide) [2](https://www.omnihuman-15.com/blog/improve-omnihuman-1-5-lip-sync-realism).
6. **Веди журнал промптов** (таблица: промпт / модель / настройки / результат). Выиграл удачный кадр — зафиксировал формулу навсегда.
7. **Чернови на дешёвом, финаль на дорогом:** 720p/Standard или Fast-версии для поиска композиции и движения, потом тот же промпт в 4K/Pro. Vidu Q3 Pro стоит ~$0.12/сек против $0.013 у Kling Standard — разница в 10 раз [5](https://gptproto.com/ru/blog/most-affordable-ai-video-generator-2026).
8. **Держи клипы 4–8 секунд** и склеивай в секвенцию. Длинная генерация = накопление дрейфа лица и деталей [1](https://app.cinevva.com/guides/long-reference-video-models).
9. **Повторяй описание персонажа дословно** во всех промптах серии (один и тот же набор слов: «30-year-old woman, short black bob, red jacket»). Любое изменение формулировки = новое лицо [3](https://filmora.wondershare.com/ai-prompt/hailuo-ai-prompt-guide.html).
10. **Один стиль на промпт.** Два стиля («кинематографично + аниме») дерутся за управление и дают дрейф [4](https://wan27.org/blog/minimax-h3-prompt-guide).
11. **Текст в кадре — короткий (1–3 слова), в кавычках, простым жирным шрифтом.** Длинные надписи и рукописные шрифты = кракозябры [4](https://wan27.org/blog/minimax-h3-prompt-guide) [3](https://crazyrouter.com/en/blog/seedream-4-api-tutorial-image-generation).
12. **Слабое движение лучше сильного.** Если объект «плывёт» и искажается — смягчи глаголы до `subtle / slow / micro` и добавь замки пропорций: «keep silhouette identical, maintain scale» [4](https://invideo.io/blog/hidden-secrets-of-kling-ai/).

---

## 5. Картинки (текст → изображение): что брать

| Модель | Когда брать | Особенности |
|---|---|---|
| **Seedream 4.0 / 4.5** (ByteDance) | Реклама, постеры, мультиязычные макеты, серии | До 6 референсов, 2K/4K, идеальный рендер текста, понимание англ.+кит., редактирование промптом [1](https://www.magnific.com/blog/seedream-4-0/) |
| **Qwen-Image** (Alibaba) | Постеры/вывески с текстом, в т.ч. иероглифика | Лучший в мире рендер текста на картинке; открытые веса, от 8 ГБ VRAM [1](https://botmonster.com/ai/best-local-image-generation-models-2026/) |
| **FLUX.2** | Фотореализм, сложные сцены, точное следование промпту | Топ качества (9.5/10), Kontext-режим сохраняет продукт в разных сценах [3](https://www.socialoverlab.com/blog/comparing-best-ai-image-models-2026) [2](https://www.addogs.ai/blog/best-ai-image-model-for-ads) |
| **Midjourney V8** | Эстетика, арт, мудборды | Красиво, но хуже держит продукт/бренд [2](https://www.addogs.ai/blog/best-ai-image-model-for-ads) |

### Правила промптов для Seedream (лучше всего задокументированы) [1](https://www.promptus.ai/blog/seedream-4-0)
1. **Полные предложения**: `субъект + действие + окружение`, а не список слов через запятую.
2. **Указывай сценарий использования**: «Design a logo for…», «Poster for…», «Product photo of…» — модель сама подстроит композицию.
3. **Текст на картинке — строго в двойных кавычках**: `A poster with the title "SALE 50% OFF" in bold red letters` + укажи цвет/шрифт/расположение. Короткие фразы (1–5 слов) [3](https://crazyrouter.com/en/blog/seedream-4-api-tutorial-image-generation).
4. **Редактирование командами** `Add / Remove / Replace` и явно говори, что НЕ менять: *«Replace this dog with a Schnauzer. Keep color scheme unchanged.»* [2](https://www.atlabs.ai/blog/master-seedream-4o-prompting-guide)
5. **Мульти-изображения**: «Replace subject in Image 1 with subject from Image 2», «Apply the color scheme of Image 2 to Image 1» — так собирают бренд-серии из 10+ картинок в одном стиле.
6. **Не пиши промпты длиннее ~300 слов** — информация «размазывается», модель теряет детали [4](https://docs.byteplus.com/en/docs/ModelArk/1541523).
7. Фото-реализм добавляй связкой: `photorealistic portrait, 85mm lens, shallow depth of field, natural lighting` [3](https://crazyrouter.com/en/blog/seedream-4-api-tutorial-image-generation).

---

## 6. Замена лица (face swap) и говорящие головы

### Рейтинг инструментов на 2026 [1](https://theairankings.com/best-ai-face-swap-apps/) [1](https://airmore.ai/ai-review/best-ai-face-swap-tools)
| Задача | Инструмент |
|---|---|
| Бесплатно и просто (фото/видео, мульти-лица) | **Vidnoz** — 60 кредитов/день бесплатно [2](https://theairankings.com/best-ai-face-swap-apps/) |
| Быстрые тесты в браузере, батчи | **Remaker AI** (до 2K) |
| Коммерция, бренды, стабильность на длинных видео, 4K | **Akool** — держит лицо при быстром движении и перекрытиях, персонализация кампаний [1](https://airmore.ai/ai-review/best-ai-face-swap-tools) |
| Длинные видео | **DeepSwap** [1](https://theairankings.com/best-ai-face-swap-apps/) |
| Полная приватность, локально на своём ПК | **FaceFusion** (open source) [2](https://theairankings.com/best-ai-face-swap-apps/) |
| Идеальная замена лица на ОДНОЙ картинке | **Gemini / Nano Banana** — не «наклеивает» лицо, а перерисовывает с сохранением идентичности [1](https://theairankings.com/best-ai-face-swap-apps/) |

### Говорящие головы и липсинк (рекламные «спикеры», новости, эксперты)
- **OmniHuman** (ByteDance), **HeyGen**, **Magicroll** (Индия), **Kling lip-sync** (загружаешь ролик + новую аудиодорожку — модель перестраивает губы) [4](https://www.jivo.ru/blog/ai/kitajskie-nejroseti.html).
- Формула «директорского» промпта для аватара: **роль + крупность + уровень эмоций + лимит жестов + камера + свет + «accurate lip sync»**. Пример: *«Realistic AI talking avatar, medium shot, steady camera, clean background. Accurate lip sync, subtle micro-expressions, minimal gestures, soft studio lighting.»* [2](https://www.omnihuman-15.com/blog/improve-omnihuman-1-5-lip-sync-realism)
- Короткие промпты бьют длинные. Если жестикуляция переигрывает — добавь одну строку: *«Minimal gestures, controlled expression, no exaggerated motion.»*
- **Главный множитель качества липсинка — чистый звук**: обрежь тишину по краям, убери шум, нормализуй громкость, темп речи естественный [2](https://www.omnihuman-15.com/blog/improve-omnihuman-1-5-lip-sync-realism).
- Всегда сначала **тест-клип 5–8 секунд**, проверяй: смыкание губ на п/б/м, стабильность зубов, дрейф лица, моргание, жесты [2](https://www.omnihuman-15.com/blog/improve-omnihuman-1-5-lip-sync-realism).
- Чини по одному: липсинк плывёт → меняй только аудио; лицо «уплывает» → меняй только фото; переигрывает → только промпт [2](https://www.omnihuman-15.com/blog/improve-omnihuman-1-5-lip-sync-realism).

---

## 7. Плейбуки по жанрам

### 🛒 7.1 Реклама / e-commerce (китайский и индийский подход)

**Структура 15-секундного UGC-ролика** (стандарт, который юзают все) [2](https://jackrighteous.com/en-us/blogs/ai-art-visuals-creatives/how-to-build-ai-ugc-ads-hooks-product-demo-creator-video):

| Время | Задача | Что показываем |
|---|---|---|
| 0–2 сек | ХУК | Проблема / результат / вопрос / наглядное демо |
| 2–6 сек | Контекст | Почему это важно зрителю |
| 6–11 сек | Решение | Продукт делает одну понятную работу |
| 11–15 сек | Развязка + CTA | Результат + один следующий шаг |

**Рабочий процесс (не рулетка):**
1. Сначала бриф, не промпт: оффер → аудитория → одна боль → угол (демо/проблема-решение/история/отзыв) → хук → доказательство → CTA [2](https://jackrighteous.com/en-us/blogs/ai-art-visuals-creatives/how-to-build-ai-ugc-ads-hooks-product-demo-creator-video).
2. Попроси LLM сгенерить **8 хуков** (2 проблема-вперёд, 2 результат-вперёд, 2 демо-вперёд, 2 вопрос-вперёд) — хук это переменная, остальной ролик константа [2](https://jackrighteous.com/en-us/blogs/ai-art-visuals-creatives/how-to-build-ai-ugc-ads-hooks-product-demo-creator-video) [3](https://craftstory.com/blog/how-to-make-ugc-ads-with-ai/).
3. Сделай «Пакет правды продукта»: мастер-фото, разрешённые формулировки, доказательный кадр. Это защищает от «поплывшего» логотипа и запрещённых обещаний [5](https://www.genflowai.io/en/blog/ai-video-ad-generator-product-images-ugc-ads).
4. Финальный промпт собирается по формуле: `тип креатора + продукт + обстановка + хук первых 2 сек + действие демо + доказательство + стиль камеры + свет + фраза озвучки + текст плашки + CTA + 9:16` [1](https://ugcmaker.org/blog/detail/UGC-AI-Video-Prompts-12-Copy-and-Paste-Templates-for-Better-Ads-a45dfaf0ecf3/).
5. Всегда 3 вариации хука на один продукт → запуск с малым бюджетом → через 48–72 часа убить проигравших, масштабировать победителя [3](https://craftstory.com/blog/how-to-make-ugc-ads-with-ai/).
6. Порядок конвейера НЕ менять: чистка фото продукта → генерация сцен → оживление → озвучка → монтаж → экспорт (1080×1920, H.264, 15–20 Mbps) [4](https://www.vidau.ai/complete-ugc-ad-workflow-product-photo-to-ai-video/). «Никогда не анимируй до того, как зафиксировал визуал».
7. **ИИ-модели для одежды**: вместо съёмок — виртуальные модели в Kling / Seedance; кейс Мумбаи: 500+ SKU, −61% затрат на креатив [1](https://quickuppsoftech.com/ai-video-marketing-2026/).

**Шаблон продуктового хиро-шота (копируй):**
```
Slow dolly push in on [PRODUCT] centered on a marble surface.
Soft studio key light from the left, warm rim light, shallow depth of field.
Micro droplets / steam rising slowly from the product. Camera moves
smoothly, product label stays sharp and readable, geometry unchanged.
Style: premium TV commercial, 4K.
```

### 😂 7.2 Юмор и мемы (самая быстрая ниша)

Главный инсайт 2026: **мемы не генерируют промптами с нуля — берут готовый шаблон и подставляют своё**. Форматы, у которых миллионы просмотров, имеют три свойства: шаблонность (любой может повторить), аудио-управляемость (ритм песни диктует монтаж), развлечение важнее сообщения [2](https://lightreel.ai/blogs/meme-edit-ugc-videos).

Актуальные форматы-шаблоны [4](https://www.getstarrd.app/blog/viral-ai-video-trends-2026) [2](https://lightreel.ai/blogs/meme-edit-ugc-videos):
- **Tung Tung Tung Sahur** — 3D-полено-персонаж поверх любого трендового танца через CapCut green-screen (аккаунты с <2000 подписчиков берут 5М+ просмотров) [2](https://lightreel.ai/blogs/meme-edit-ugc-videos).
- **AI dance / motion copy** — одно твоё фото превращается в танец, скопированный движение-в-движение («Bad Times», «I Got That Feeling», Real Madrid dance — 2М+ постов). Это не промпт, это перенос движения — поэтому результат предсказуемый [4](https://www.getstarrd.app/blog/viral-ai-video-trends-2026).
- **Levitating Product** — гигантский продукт летит на креатора и уменьшается в руки (топ для брендов) [2](https://lightreel.ai/blogs/meme-edit-ugc-videos).
- **«Show the impossible output, then reveal how»** — сначала невозможный результат, потом «как я это сделал» — самый быстрорастущий кластер туториалов [2](https://lightreel.ai/blogs/meme-edit-ugc-videos).
- **Brainrot-конвейер**: гиперболизированный сценарий → энергичная AI-озвучка (Fish Audio / ElevenLabs) → сюрреалистичные клипы (Runway/Pika/Kling) → CapCut: джамп-каты, эмодзи, жирные анимированные субтитры, зумы → экспорт 9:16 [1](https://fish.audio/blog/top-online-ai-brainrot-video-generators/).
- Чистый хаос «брэйрота» уже насыщен — брендам лучше заимствовать его **монтажный язык**, а не суть [2](https://lightreel.ai/blogs/meme-edit-ugc-videos).

### 🗣 7.3 Говорящая голова / эксперт / новости
- Индия: Magicroll (хинди и 35 языков), HeyGen, Synthesia [5](https://magicroll.ai/blogs/ai-video-in-india-the-future-of-content-creation-for-2026).
- Формула промпта и тесты — из раздела 6. Сценарий пиши через LLM, озвучку — ElevenLabs, губы — липсинк модели.

### 🎭 7.4 Мини-драма с диалогом (китайский жанр «дуаньцзюй»)
Шаблон для Vidu Q3 (нативный звук!) [1](https://vidu.xin/en/blog/vidu-q3-text-to-video-complete-guide/):
```
Scene: small apartment living room, night, warm desk lamp.
Character: young woman in loungewear, anxious.
Action: 0–4s stares at phone; 4–10s looks up and confronts;
10–16s silence, walks to window.
Camera: locked medium → facial close-up → back medium.
Sound: phone ping; she says quietly: "Where are you?";
low city ambience, no music.
```

---

## 8. Траблшутинг: симптом → причина → фикс

| Симптом | Причина | Фикс |
|---|---|---|
| Деревянное движение | Действие описано статично («стоит», «смотрит») или завалено прилагательными | Активный глагол в начало; одно движение камеры [4](https://wan27.org/blog/minimax-h3-prompt-guide) |
| Камера не та / не двигается | Термин камеры в конце промпта или конфликт («статично» + «трекинг») | Команда камеры в первые 8–10 слов, одна команда [3](https://www.stevenvideo.com/blog/kling-3-cinematic-camera-guide-2026) |
| «Плавление» объектов, морфинг | Несколько действий в одном клипе | Одно действие на 4–6 секунд; «hands remain completely still» [5](https://affiliatemarketingdude.com/hailuo-ai-video-prompt-guide/) |
| Лицо персонажа меняется от кадра к кадру | Описание персонажа переформулируется | Дословно одинаковое описание + мульти-референсы / @элементы [1](https://app.cinevva.com/guides/long-reference-video-models) |
| Кракозябры вместо надписи | Длинный текст, декоративный шрифт | 1–3 слова, кавычки, «bold plain font» [4](https://wan27.org/blog/minimax-h3-prompt-guide) |
| Мультяшный вид вместо фото | Нет якоря стиля | `photorealistic, shot on Arri Alexa, 8k, natural lighting` [3](https://filmora.wondershare.com/ai-prompt/hailuo-ai-prompt-guide.html) |
| Продукт деформируется в движении | Агрессивные глаголы | `subtle, slow, micro` + «keep silhouette identical» [4](https://invideo.io/blog/hidden-secrets-of-kling-ai/) |
| Липсинк «плавает» | Грязное аудио / длинная реплика | Чистка аудио, ≤2.5 слов/сек, тест 5–8 сек [2](https://www.omnihuman-15.com/blog/improve-omnihuman-1-5-lip-sync-realism) |
| Стиль «дрейфует» в аниме | Два стиля в одном промпте | Один стиль на промпт [4](https://wan27.org/blog/minimax-h3-prompt-guide) |
| Камера есть, а субъект «уплывает» | Не закреплена позиция | «centered in frame, stays in place, camera follows from the side» [1](https://minimax-ai.chat/models/minimax-hailuo-director-models/) |

---

## 9. Готовые стеки под бюджет

**🆓 Бесплатный старт (тесты и мемы):**
- Видео: бесплатные кредиты Kling (6 генераций/день), Hailuo (200 кредитов на старте), Wan (10 кредитов/день) [4](https://www.jivo.ru/blog/ai/kitajskie-nejroseti.html); Seedance без водяного знака [2](https://www.seedance.tv/ru/blog/best-free-ai-video-generator-2026-ru)
- Картинки: Qwen-Image локально / бесплатные тарифы
- Лица: Vidnoz (60 кредитов/день), FaceFusion локально
- Монтаж: CapCut / Jianying (оба от ByteDance, куча вирусных шаблонов)
- Сценарии: DeepSeek / Doubao бесплатно

**💰 ~$30–40/мес (стабильный продакшн):**
- Kling Standard (~$10) + Vidu (~$8) + Hailuo (~$10–15) — закрывает 95% задач [5](https://gptproto.com/ru/blog/most-affordable-ai-video-generator-2026)
- Озвучка: ElevenLabs / Fish Audio

**🚀 Про (агентство / поток):**
- Kling 3.0 Pro + Seedance 2.0 + Vidu Q3 Pro + Seedream 4.5 + Akool (face swap 4K) + ComfyUI/Wan для автоматизации через API

---

## 10. Итоговая шпаргалка «на холодильник»

1. Никогда не начинай важный ролик с чистого text-to-video. Сначала ключевой кадр картинкой.
2. Глагол движения камеры — в первых 8–10 словах промпта.
3. Один клип = одно действие + одно движение камеры + 4–8 секунд.
4. Персонажа описывай дословно одинаково или через референсы (@элементы, 3–7 фото).
5. Ограничения — позитивно («бутылка остаётся стоять»), не негативными списками.
6. Не нравится результат — меняй ровно одну переменную и веди журнал промптов.
7. Чернови на дешёвых режимах, финаль на дорогих. Закладывай 2–4 дубля на нужный кадр.
8. Реклама: сначала 8 хуков в тексте, потом один ролик на хук, убивай проигравших за 48 часов.
9. Мемы: не выдумывай — бери шаблон (CapCut) и подставляй своё; аудио управляет монтажом.
10. Для диалогов и звука в одном поколении — Vidu Q3; реплики в кавычках, ≤2.5 слов/сек.

*Удачи — и пусть рулетка останется в казино.* 🎰➡️🎯
