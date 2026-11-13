export type AssistantCategory = 'face_swap' | 'photo_to_video' | 'text_to_video'

export type KnowledgePreset = {
  id: AssistantCategory
  title: string
  short: string
  screen: 'director' | 'studio' | 'editor'
  steps: string[]
  defaultParams: Record<string, string | number>
  promptTemplate: string
}

export const KNOWLEDGE_PRESETS: KnowledgePreset[] = [
  {
    id: 'face_swap',
    title: 'Замена лица',
    short: 'Подставить лицо с фото в ролик или в кадр.',
    screen: 'studio',
    steps: [
      'Открыть Студию',
      'Загрузить фото лица как исходник',
      'Выставить длительность и размер кадра',
      'Подставить промпт из библиотеки и запустить генерацию',
      'Следить за очередью и отдать готовый файл',
    ],
    defaultParams: {
      duration_seconds: 5,
      resolution: '480p',
      mode: 'image_to_video',
    },
    promptTemplate:
      'Тот же человек, что на загруженном фото. Лицо узнаваемое, естественный свет, без искажений. Сцена: {scene}',
  },
  {
    id: 'photo_to_video',
    title: 'Видео по фото',
    short: 'Оживить одно или несколько фото в короткий ролик.',
    screen: 'studio',
    steps: [
      'Открыть Студию',
      'Загрузить исходное фото',
      'Выставить длительность 5 секунд и 480p для пробы, больше — если нужно',
      'Вписать сцену в промпт и запустить генерацию',
      'Дождаться очереди и отдать ролик',
    ],
    defaultParams: {
      duration_seconds: 5,
      resolution: '480p',
      mode: 'image_to_video',
    },
    promptTemplate:
      'Оживи это фото: лёгкое естественное движение, стабильная камера, тот же свет и композиция. Сцена: {scene}',
  },
  {
    id: 'text_to_video',
    title: 'Текст в видео',
    short: 'Собрать ролик только по описанию, без исходного фото.',
    screen: 'director',
    steps: [
      'Открыть Режиссёра или Студию',
      'Выставить длительность и размер',
      'Собрать понятный промпт по описанию человека',
      'Запустить генерацию',
      'Следить за очередью и отдать файл',
    ],
    defaultParams: {
      duration_seconds: 5,
      resolution: '480p',
      mode: 'text_to_video',
    },
    promptTemplate:
      'Короткий кинокадр. {scene} Камера спокойная, свет естественный, движение простое и понятное.',
  },
]

export function knowledgeForPrompt(): string {
  return KNOWLEDGE_PRESETS.map(preset => {
    return [
      `Категория: ${preset.title} (id: ${preset.id})`,
      preset.short,
      `Экран: ${preset.screen}`,
      `Шаги: ${preset.steps.join(' → ')}`,
      `Параметры по умолчанию: ${JSON.stringify(preset.defaultParams)}`,
      `Шаблон промпта: ${preset.promptTemplate}`,
    ].join('\n')
  }).join('\n\n')
}

export function findPreset(id?: string | null): KnowledgePreset | undefined {
  return KNOWLEDGE_PRESETS.find(preset => preset.id === id)
}
