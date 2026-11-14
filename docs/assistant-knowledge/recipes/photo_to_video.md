# Видео по фото

Оживить одно фото в клип 5–10 с.

## Шаги
1. `upscale_image` — Улучшить фото и поднять до 4К (длинная сторона 3840) — когда: если фото меньше 1080 по короткой стороне
2. `convert_jpeg` — Перевести в JPEG (quality 95, sRGB, без альфы: прозрачный фон заливать белым или фоном сцены)
3. `generate_scene` — Оживить кадр в клип — {"engine": "wan2.2_fal", "seconds": 5, "resolution": "480p"}

## Шаблон промпта
```
{camera}, {subject}, {action}, {place}, {light}, {style}, photorealistic, natural motion, stable composition
```
