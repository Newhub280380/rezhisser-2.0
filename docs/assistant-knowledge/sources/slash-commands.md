# ⚡ БИБЛИОТЕКА КОМАНД (slash-рецепты для видео и картинок)

## Как этим пользоваться (3 правила)
1. **Скелет НЕ переписывай.** Команда = зафиксированный рабочий шаблон. Меняй ТОЛЬКО то, что в `[квадратных скобках]`. Стабильность результата живёт именно в неизменном скелете.
2. Нужен другой тип видео — бери другую команду, не крути настройки этой.
3. Данные в скобках подставляй короткими словами (1–4 слова). Длинные описания ломают скелет.

**Оглавление:**
- Реклама: `/hero` `/ugc` `/hooks3` `/before-after` `/food` `/wear` `/levitate`
- Диалог и люди: `/dialogue-ad` `/talking-head` `/lipsync` `/face-swap`
- Мемы и юмор: `/dance` `/pet` `/brainrot` `/reveal`
- Картинки: `/poster` `/scene` `/meme-img` `/character`

---
---

# 🛒 РЕКЛАМА

---

## `/hero` — премиальный рекламный кадр продукта
**Получишь:** 5-сек «реклама из ТВ»: продукт в центре, камера плавно наезжает, лёгкий пар/блики, всё дорого.

**Где:** кадр → **Seedream 4.5** (или любой генератор картинок), оживление → **Kling 3.0** (режим Image-to-Video)

**Шаг 1 — кадр (скопируй):**
```
Product photo of [PRODUCT] centered on [SURFACE]. Soft studio key light
from the left, warm rim light, dark clean background, shallow depth of
field, style: premium TV commercial, 4K.
```
**Шаг 2 — оживление (вставь кадр в Kling I2V, промпт):**
```
Slow dolly push in on the product. Gentle steam rising slowly. Camera
moves smoothly, product geometry unchanged, label stays sharp and readable.
```
**Подставляешь:** `[PRODUCT]` (например: perfume bottle), `[SURFACE]` (black marble)
**Не трогай:** свет, движение камеры, «geometry unchanged» — это и есть стабильный скелет.

---

## `/ugc` — ролик-отзыв «как снятый на телефон»
**Получишь:** 14-сек вертикальный UGC-ролик: креатор говорит на камеру → показывает продукт → финал с призывом. Со звуком и голосом из коробки.

**Где:** **Vidu Q3** (режим text-to-video, нативный звук)

**Промпт (скопируй):**
```
Scene: bright bedroom, daylight, handheld phone camera feel, 9:16 vertical.
Character: friendly [CREATOR TYPE], casual clothes, talking straight to camera.
Action: 0–2s shows [PRODUCT] close to lens and says excitedly: "[HOOK LINE]".
2–8s demonstrates [PRODUCT] in use, natural movements.
8–14s smiles at camera and says: "[CTA LINE]".
Camera: handheld, slight natural shake, no cuts.
Sound: her voice, quiet room ambience, no music.
```
**Подставляешь:** `[CREATOR TYPE]` (young woman / студент / мама), `[PRODUCT]`, `[HOOK LINE]` (до 12 слов!), `[CTA LINE]` (до 8 слов)
**Не трогай:** тайминги 0–2/2–8/8–14 и блок Sound.
**Правило реплик:** не длиннее ~2.5 слов в секунду, иначе речь сомнётся.

---

## `/hooks3` — три хука на одно и то же демо
**Получишь:** 3 версии начала ролика под один продукт (проблема / интрига / результат) — для теста, какой зайдёт. Делаешь один раз, тестируешь неделю.

**Где:** любая LLM (текст) + **Vidu Q3** или **Kling** (видео)

**Шаг 1 — хуки (в чат-бот):**
```
Продукт: [PRODUCT]. Аудитория: [AUDIENCE]. Напиши ровно 3 хука для первых
2 секунд вертикальной рекламы, каждый до 10 слов: 1) проблема-вперёд,
2) интрига-вперёд, 3) результат-вперёд. Без кликбейта и обещаний.
```
**Шаг 2 — каждый хук прогоняешь через команду `/ugc`, меняя только `[HOOK LINE]`.** Тело ролика одинаковое → тест чистый.

---

## `/before-after` — трансформация «до/после»
**Получишь:** плавный переход из состояния ДО в состояние ПОСЛЕ (ремонт, похудение, макияж, уборка). Модель сама строит движение между кадрами.

**Где:** **Vidu Q3** или **Kling 3.0** — режим First & Last Frame (начальный и конечный кадр)

**Шаг 1:** сделай/найди две картинки: `[КАДР-ДО]` и `[КАДР-ПОСЛЕ]` (одна точка съёмки, один ракурс!)
**Шаг 2 — промпт:**
```
Smooth continuous transformation from the first frame to the last frame.
Camera stays static, locked composition. Motion is gradual and realistic,
no flicker, lighting transitions naturally.
```
**Подставляешь:** только сами две картинки.
**Критично:** ракурс и композиция на обоих кадрах должны совпадать — иначе будет каша. Это единственное условие стабильности.

---

## `/food` — фуд-коммершиал (еда и напитки)
**Получишь:** сочный макро-кадр: пар, капли, тянущийся сыр / льющийся кофе, медленная камера.

**Где:** **Seedream 4.5** → **Kling 3.0 I2V**

**Шаг 1 — кадр:**
```
Food photography close-up of [DISH], steam rising, glistening texture,
warm side light, dark rustic background, macro lens, style: TV food
commercial, 4K.
```
**Шаг 2 — оживление:**
```
Static camera, macro close-up. Steam drifts upward slowly, [FOOD ACTION]
in slow motion, shallow depth of field, everything else stays still.
```
**Подставляешь:** `[DISH]` (cheese pizza slice), `[FOOD ACTION]` (cheese stretching as the slice is lifted / coffee pouring into the cup)
**Секрет:** камера СТАТИЧНА, двигается только еда — так стабильнее всего.

---

## `/wear` — одежда на ИИ-модели без съёмки
**Получишь:** ролик, где виртуальная модель в твоей вещи идёт/позирует.

**Где:** **Kling 3.0**, режим Multi-Elements (@элементы)

**Промпт:**
```
@Item1 is worn by a tall fashion model walking slowly toward the camera
on a [LOCATION]. Medium full shot, steady tracking, soft daylight.
The outfit fits naturally, fabric moves realistically, model keeps calm
confident expression. Style: fashion lookbook film.
```
**Подставляешь:** загрузи фото вещи как элемент `@Item1` (плоско, без складок — лучший результат), `[LOCATION]` (bright studio / city street)
**Не трогай:** скорость ходьбы и тип кадра.

---

## `/levitate` — мем-реклама «парящий продукт» (тренд 2026)
**Получишь:** продукт-гигант летит на креатора и уменьшается в руки — формат, который сейчас рвёт у брендов.

**Где:** проще всего — готовый **шаблон в CapCut** (поиск: "levitating product"), либо **Kling 3.0 I2V**

**Вариант через Kling (кадр: креатор + продукт вдали):**
```
[PRODUCT] floats through the air toward the creator, slowly shrinking,
and lands gently into their open hands. The creator catches it and smiles.
Static camera, medium shot, smooth continuous motion, no cuts.
```
**Подставляешь:** `[PRODUCT]`, фото-кадр с креатором.

---
---

# 🗣 ДИАЛОГ И ЛЮДИ

---

## `/dialogue-ad` — реклама-сценка с диалогом (звук из коробки)
**Получишь:** 12–16 сек мини-сценки: два человека говорят, звук и липсинк уже внутри, без озвучки в редакторе.

**Где:** **Vidu Q3** (reference2video, загрузи 1–2 фото персонажей как референсы)

**Промпт:**
```
Scene: [LOCATION], [TIME OF DAY], natural light.
@PersonA stands [POSITION] when @PersonB enters.
@PersonA, curious tone: "[LINE A]"
@PersonB, confident tone: "[LINE B]"
Two-shot at chest height, then a close-up on @PersonB for the second line.
Sound: their voices, [AMBIENCE], no music.
Both faces stay matched to their reference images throughout.
```
**Подставляешь:** `[LOCATION]` (small office), `[TIME OF DAY]`, `[LINE A]` и `[LINE B]` — каждая до 12 слов, `[AMBIENCE]` (quiet office hum)
**Не трогай:** последнюю строку про лица — она держит постоянство.

---

## `/talking-head` — говорящая голова (эксперт/новости/спикер)
**Получишь:** стабильный «говорящий эксперт» на камеру, без переигрывания и уплывающего лица.

**Где:** **HeyGen / Magicroll / OmniHuman / Kling Avatars** — любое «аватарное» приложение

**Промпт (скелет):**
```
Realistic AI talking avatar, medium shot, steady camera, clean background.
Accurate lip sync, subtle micro-expressions, minimal gestures, soft studio
lighting. The speaker talks calmly and confidently.
```
**Подставляешь:** свой текст речи в поле сценария + фото/аватар спикера.
**Правила стабильности:**
- Аудио/текст — чистые: без шума и криков, темп обычный.
- Сначала тест на 5–8 секунд → проверил губы и лицо → только потом полный ролик.
- Плывёт липсинк — меняй только аудио. Плывёт лицо — меняй только фото. По одной вещи за раз.

---

## `/lipsync` — заменить речь в готовом видео
**Получишь:** человек в твоём видео «говорит» новый текст/язык, губы перестроены.

**Где:** **Kling** (функция lip sync: ролик + новая аудиодорожка) или **Akool**

**Порядок:** загрузил видео → загрузил чистую аудиодорожку (речь без музыки и шума) → генерация.
**Подставляешь:** только два файла. Промпт не нужен.
**Критично:** дорожка без музыки и без тишины по краям — иначе губы «плавают».

---

## `/face-swap` — замена лица в видео
**Получишь:** чужое тело в видео с нужным лицом, стабильно по кадрам.

**Где (по возрастанию серьёзности):** **Vidnoz** (бесплатно, 60 кредитов/день) → **Remaker** → **Akool** (коммерция, 4K)

**Порядок:** загрузил видео-цель → загрузил ОДНО хорошее фото лица (анфас, ровный свет, без очков) → генерация.
**Правила стабильности:**
- Фото анфас, лоб и подбородок открыты — лицо не «съедет».
- Исходное видео с ровной камерой и нормальным светом → результат кратно лучше.
- Нужно длинное видео → бери DeepSwap или режь на куски.

---
---

# 😂 МЕМЫ И ЮМОР

---

## `/dance` — танец из одной фотки (motion copy, самый стабильный мем-формат)
**Получишь:** человек с твоего фото танцует трендовый танец, движение в движение, под трендовый звук. Это не рулетка: движение копируется с шаблона, а не генерируется.

**Где:** **шаблоны CapCut** (поиск по названию тренда: "AI dance", "Real Madrid AI dance", "Bad Times", "I Got That Feeling")

**Порядок:** открыл шаблон в CapCut → вставил ОДНО фото в полный рост (лицо видно, ноги в кадре) → экспорт.
**Подставляешь:** только фото.
**Правило:** фото в полный рост, простой фон, человек стоит прямо — иначе шаблон криво наложится.

---

## `/pet` — говорящее животное-«боец» (стендап-питомец)
**Получишь:** кот/пёс стоит как человек, жестикулирует и «говорит» под вирусную аудиодорожку.

**Где:** фото питомца → **Kling 3.0 I2V** (или Vidu Q3 со звуком)

**Промпт:**
```
The [PET] stands upright on hind legs like a human, facing the camera,
gesturing with front paws while talking with big tough-guy energy.
Upper body framing, static camera, natural daylight. Mouth moves as if
speaking, exaggerated comedic expressions.
```
**Подставляешь:** `[PET]` (cat / dog), фото.
**Звук:** наложи трендовое аудио в CapCut поверх (или напиши реплику в кавычках для Vidu).

---

## `/brainrot` — хаотичный мем-ролик с дикой озвучкой
**Получишь:** перегруженный быстрый ролик под абсурдную озвучку (формат, который доминирует в ленте).

**Конвейер (фиксированный порядок):**
1. Сценарий в чат-боте: *«Напиши абсурдную историю на 30 секунд про [ТЕМА], стиль — гипертрофированный, каждая фраза короче 8 слов»*.
2. Озвучка: **ElevenLabs / Fish Audio** — голос энергичный, темп быстрый.
3. Визуал: 4–6 клипов по 2–3 сек в **Hailuo** (дёшево и быстро), промпты из 1–2 фраз каждый, только по сюжету.
4. Сборка в **CapCut**: смена кадра каждые 1.5–2 сек, жирные анимированные субтитры, зумы, мемные звуки.
**Подставляешь:** `[ТЕМА]` и текст. Скелет монтажа не меняется.

---

## `/reveal` — «невозможный результат → как сделал»
**Получишь:** быстрорастущий туториал-формат: сначала шокирующий результат, потом раскрытие «как это сделано ИИ».

**Где:** результат → любой видео-генератор (например `/hero`), раскрытие → скрин-запись процесса.
**Скелет (фиксированный):**
```
0–3 сек: невозможный кадр (самое сочное, что есть)
3–5 сек: крупный текст "Как я это сделал?"
5–15 сек: ускоренная запись процесса + голос-комментарий
```
**Подставляешь:** только свой «невозможный» кадр и свой процесс. Структура всегда одна — она и работает.

---
---

# 🖼 КАРТИНКИ

---

## `/poster` — постер/баннер с надписью (текст рендерится ровно)
**Получишь:** постер, где надпись написана без ошибок и ровно тем текстом, что ты дал.

**Где:** **Seedream 4.5** (или **Qwen-Image**)

**Промпт:**
```
Design a [TYPE] poster. Bold title "[TEXT]" at the top in [COLOR] bold
letters. Below: [MAIN VISUAL]. Clean composition, high contrast, 4K.
```
**Подставляешь:** `[TYPE]` (sale / event / product), `[TEXT]` (до 5 слов — критично!), `[COLOR]`, `[MAIN VISUAL]` (a sneaker exploding into neon particles)
**Правило:** текст только в двойных кавычках и не длиннее 5 слов — иначе поплывёт.

---

## `/scene` — продукт в интерьере из вырезанного фото
**Получишь:** твой реальный продукт, вписанный в любую сцену (кухня, студия, улица), с нормальным светом.

**Где:** **Seedream 4.5** (режим с референсом) или **FLUX Kontext**

**Промпт (вместе с фото продукта как референсом):**
```
Place the product from the reference image into [SCENE], keep the product
exactly unchanged: same label, shape and colors. Natural light matching
the environment, soft realistic shadow under the product, 4K.
```
**Подставляешь:** `[SCENE]` (modern kitchen counter at morning)
**Ключевая строка — «keep the product exactly unchanged» — не удаляй.**

---

## `/meme-img` — картинка-мем с подписью
**Получишь:** мем-изображение в нужном стиле с ровной надписью.

**Где:** **Seedream 4.5**

**Промпт:**
```
Meme-style image of [SITUATION], exaggerated funny expression, bright
colors, bold caption text "[CAPTION]" at the top in white impact font
with black outline.
```
**Подставляешь:** `[SITUATION]` (a cat sitting at an office desk full of paperwork), `[CAPTION]` (до 5 слов)

---

## `/character` — лист персонажа для серии роликов/комиксов
**Получишь:** один и тот же персонаж в 4 позах/ракурсах — дальше гоняй его во все видео через референсы, лицо не поплывёт.

**Где:** **Seedream 4.5**

**Промпт:**
```
Character sheet of [CHARACTER], four views: front, side, back, smiling
close-up. Same person in all views, identical face, hair and outfit:
[OUTFIT]. Plain light background, clean consistent style, 4K.
```
**Подставляешь:** `[CHARACTER]` (25-year-old guy with red curly hair), `[OUTFIT]` (blue hoodie, jeans)
**Дальше:** этот лист режешь на фото и используешь как референсы в `/wear`, `/dialogue-ad`, Kling Elements и т.д. — это и есть «вечный» персонаж.

---
---

## 🧭 Если команда не дала результат
Не перенастраивай скелет. Сделай ровно одно:
- **Видео не то по содержанию** → поменяй только строку с действием (1 глагол).
- **Не то по камере** → поменяй только первую фразу (движение камеры).
- **Лицо/продукт поплыл** → добавь строку `keep geometry and identity unchanged` и сократи клип до 4 сек.
- **Совсем мусор** → возьми картинку из удачного кадра и запусти эту же команду в режиме image-to-video вместо text-to-video.
