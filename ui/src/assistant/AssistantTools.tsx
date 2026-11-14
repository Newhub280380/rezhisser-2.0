import { useRef } from 'react'
import {
  fetchActiveJobs,
  fetchDirectorQueue,
  fetchOutputs,
  getFileUrl,
  startDirectorQueue,
  startStudioQueue,
  uploadImage,
} from '../api/client'
import { useStore } from '../stores/useStore'
import type { GenerateParams } from '../types'
import {
  cancelAutopilot,
  fetchAutopilot,
  readKnowledge,
  refImageUrl,
  regenerateScene,
  searchKnowledge,
  startAutopilot,
} from './autopilotApi'
import { findPreset, type AssistantCategory } from './knowledge'
import { useFrontendTool } from './useFrontendTool'

const SCREENS = ['director', 'studio', 'editor', 'settings'] as const

function asString(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function asNumber(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim() && Number.isFinite(Number(value))) return Number(value)
  return undefined
}

export function AssistantTools({
  category,
  fileInputRef,
  attachments,
  onAutopilot,
  onImage,
}: {
  category: AssistantCategory | null
  fileInputRef: React.RefObject<HTMLInputElement | null>
  /** Upload file names the person attached in the chat. */
  attachments: string[]
  /** Called with the run id so the chat shows live progress and the final player. */
  onAutopilot: (runId: string) => void
  /** Shows a reference picture in the chat. */
  onImage: (url: string, caption: string) => void
}) {
  const lastUpload = useRef<{ filename: string; path: string; url: string } | null>(null)

  useFrontendTool(
    {
      name: 'open_screen',
      description: 'Открыть экран приложения: director, studio, editor или settings.',
      parameters: {
        type: 'object',
        properties: {
          screen: {
            type: 'string',
            enum: SCREENS,
            description: 'Какой экран открыть',
          },
        },
        required: ['screen'],
        additionalProperties: false,
      },
      handler: async ({ screen }) => {
        const target = asString(screen)
        const store = useStore.getState()
        if (target === 'settings') {
          store.setSettingsOpen(true)
          return { ok: true, screen: 'settings' }
        }
        if (target === 'director' || target === 'studio' || target === 'editor') {
          store.setSettingsOpen(false)
          store.setSidebarMode(target)
          return { ok: true, screen: target }
        }
        return { ok: false, error: 'Неизвестный экран. Есть director, studio, editor и settings.' }
      },
    },
    [],
  )

  useFrontendTool(
    {
      name: 'upload_photo',
      description: 'Открыть окно выбора фото на компьютере и загрузить его в Режиссёр.',
      parameters: {
        type: 'object',
        properties: {
          role: {
            type: 'string',
            enum: ['start', 'face', 'reference'],
            description: 'Зачем это фото: исходный кадр, лицо или референс',
          },
        },
        additionalProperties: false,
      },
      handler: async ({ role }) => {
        const input = fileInputRef.current
        if (!input) return { ok: false, error: 'Окно выбора файла ещё не готово.' }
        const file = await new Promise<File | null>(resolve => {
          const onChange = () => {
            input.removeEventListener('change', onChange)
            resolve(input.files?.[0] ?? null)
            input.value = ''
          }
          input.addEventListener('change', onChange, { once: true })
          input.click()
        })
        if (!file) return { ok: false, error: 'Фото не выбрано.' }
        const uploaded = await uploadImage(file, { reuseIdentical: true })
        lastUpload.current = uploaded
        const imagePath = uploaded.path || uploaded.filename
        const store = useStore.getState()
        store.setStartImage(file)
        useStore.setState(current => ({
          params: {
            ...current.params,
            image_start: imagePath,
          },
        }))
        return {
          ok: true,
          role: asString(role) || 'start',
          filename: uploaded.filename,
          path: uploaded.path,
          url: uploaded.url,
        }
      },
    },
    [fileInputRef],
  )

  useFrontendTool(
    {
      name: 'set_params',
      description: 'Выставить параметры генерации: промпт, длительность, размер кадра, категорию.',
      parameters: {
        type: 'object',
        properties: {
          prompt: { type: 'string', description: 'Текст сцены или готовый промпт' },
          duration_seconds: { type: 'number', description: 'Длина ролика в секундах' },
          resolution: { type: 'string', description: 'Размер кадра, например 480p или 720p' },
          category: {
            type: 'string',
            description: 'id рецепта из библиотеки знаний (recipes.json), например photo_to_video',
          },
          scene: { type: 'string', description: 'Короткое описание сцены для шаблона' },
        },
        additionalProperties: false,
      },
      handler: async args => {
        const preset = findPreset(asString(args.category) || category || '')
        const scene = asString(args.scene)
        let prompt = asString(args.prompt)
        if (!prompt && preset) {
          prompt = preset.promptTemplate.replace('{scene}', scene || 'естественная живая сцена')
        }
        const duration = asNumber(args.duration_seconds) ?? asNumber(preset?.defaultParams.duration_seconds)
        // The Studio prompt lives in params.prompt; setParams keeps the store's own side effects.
        const partial: Partial<GenerateParams> = {}
        if (prompt) partial.prompt = prompt
        if (duration) partial.video_length = duration
        if (asString(args.resolution)) partial.resolution = asString(args.resolution)
        useStore.getState().setParams(partial)
        return {
          ok: true,
          prompt: useStore.getState().params.prompt,
          duration_seconds: duration ?? null,
          resolution: asString(args.resolution) || preset?.defaultParams.resolution || null,
          category: preset?.id || null,
          screen: preset?.screen || null,
        }
      },
    },
    [category],
  )

  useFrontendTool(
    {
      name: 'start_generation',
      description: 'Запустить генерацию на текущем экране (Студия или Режиссёр) и сдвинуть очередь.',
      parameters: {
        type: 'object',
        properties: {
          where: {
            type: 'string',
            enum: ['studio', 'director', 'auto'],
            description: 'Где запускать. auto — по текущему экрану',
          },
        },
        additionalProperties: false,
      },
      handler: async ({ where }) => {
        const store = useStore.getState()
        const target = asString(where) || 'auto'
        const mode = target === 'auto' ? store.sidebarMode : target
        if (mode === 'director') {
          store.setSidebarMode('director')
          await store.directorGenerate()
          await startDirectorQueue().catch(() => null)
        } else {
          store.setSidebarMode('studio')
          await store.startGeneration('now')
          await startStudioQueue().catch(() => null)
        }
        const after = useStore.getState()
        const error = after.promptEnhanceError || after.directorError
        if (error) return { ok: false, error, where: mode }
        return { ok: true, where: mode, generating: after.isGenerating }
      },
    },
    [],
  )

  useFrontendTool(
    {
      name: 'watch_queue',
      description: 'Посмотреть очередь Студии и Режиссёра: что сейчас считается и что уже готово.',
      parameters: {
        type: 'object',
        properties: {},
        additionalProperties: false,
      },
      handler: async () => {
        const [studio, director] = await Promise.all([
          fetchActiveJobs().catch(() => ({ jobs: [] })),
          fetchDirectorQueue().catch(() => null),
        ])
        const jobs = (studio.jobs || []).map(job => ({
          id: job.job_id,
          status: job.status,
          progress: job.progress ?? null,
        }))
        return {
          ok: true,
          studio_jobs: jobs,
          director_queue: director,
        }
      },
    },
    [],
  )

  useFrontendTool(
    {
      name: 'deliver_file',
      description: 'Найти последний готовый файл и отдать ссылку на скачивание.',
      parameters: {
        type: 'object',
        properties: {
          name: { type: 'string', description: 'Имя файла, если уже известно' },
        },
        additionalProperties: false,
      },
      handler: async ({ name }) => {
        const wanted = asString(name)
        const { outputs } = await fetchOutputs(12, 0)
        const match = wanted
          ? outputs.find(item => item.name === wanted || item.name?.includes(wanted))
          : outputs[0]
        if (!match) return { ok: false, error: 'Готового файла пока нет.' }
        const url = match.url || getFileUrl(match.name, match.workspace)
        return {
          ok: true,
          name: match.name,
          url,
          kind: match.type,
        }
      },
    },
    [],
  )

  useFrontendTool(
    {
      name: 'start_autopilot',
      description:
        'Автопилот: сам проходит весь рецепт и отдаёт готовый mp4. photo_to_film — ролик из фото ' +
        '(фон → 4К → JPEG → раскадровка → сцены Wan 2.2 → склейка 1080x1920). viral_remake — ремейк ролика по ссылке. ' +
        'one_prompt_film — ролик одной фразой (сценарий → доктор → активы → раскадровка → сцены → озвучка → музыка → ' +
        'субтитры → склейка); фразу передай в request. Прогресс и плеер чат показывает сам.',
      parameters: {
        type: 'object',
        properties: {
          recipe: { type: 'string', enum: ['photo_to_film', 'viral_remake', 'one_prompt_film'] },
          request: { type: 'string', description: 'Задача словами человека' },
          total_seconds: { type: 'number', description: 'Длина ролика, с. Фото: по умолчанию 60, одна фраза: 30; «2–3 минуты» = 150' },
          aspect: { type: 'string', enum: ['9:16', '16:9', '1:1'] },
          remove_background: { type: 'boolean', description: 'false для пейзажей и интерьеров' },
          quality: { type: 'string', enum: ['draft', 'final'], description: 'draft = 480p, final = 720p' },
          photos: { type: 'array', items: { type: 'string' }, description: 'Имена загруженных фото; по умолчанию все прикреплённые' },
          source_url: { type: 'string', description: 'Ссылка на ролик для viral_remake' },
          replace_photo: { type: 'string', description: 'Фото героя/продукта для замены в viral_remake' },
        },
        required: ['recipe'],
        additionalProperties: false,
      },
      handler: async args => {
        const recipe = asString(args.recipe) || 'photo_to_film'
        const photos = Array.isArray(args.photos) && args.photos.length
          ? args.photos.map(String)
          : attachments
        const body: Record<string, unknown> = { ...args, recipe, photos }
        if (recipe === 'viral_remake' && !body.replace_photo && attachments.length) body.replace_photo = attachments[0]
        if (recipe === 'photo_to_film' && !photos.length) {
          return { ok: false, error: 'Нет фото. Попросите прикрепить фото кнопкой «Фото» в чате.' }
        }
        const run = await startAutopilot(body)
        onAutopilot(run.id)
        return { ok: true, run_id: run.id, note: 'Автопилот запущен; прогресс и готовый ролик чат покажет сам.' }
      },
    },
    [attachments, onAutopilot],
  )

  useFrontendTool(
    {
      name: 'regenerate_scene',
      description: 'Переснять одну сцену готового ролика «Одной фразой» (можно с новым промптом); остальное не пересобирается.',
      parameters: {
        type: 'object',
        properties: {
          run_id: { type: 'string' },
          index: { type: 'number', description: 'Номер сцены, с 1' },
          prompt: { type: 'string', description: 'Новый промпт сцены для Wan 2.2 (по желанию)' },
        },
        required: ['run_id', 'index'],
        additionalProperties: false,
      },
      handler: async ({ run_id, index, prompt }) => {
        const run = await regenerateScene(asString(run_id), asNumber(index) ?? 1, asString(prompt))
        onAutopilot(run.id)
        return { ok: true, status: run.status }
      },
    },
    [onAutopilot],
  )

  useFrontendTool(
    {
      name: 'search_knowledge',
      description:
        'Поиск по памяти знаний (товарка, правила Beautyart, рецепты, rules.md, slash-команды): 1–5 узлов с путями. ' +
        'Потом read_knowledge только нужных файлов.',
      parameters: {
        type: 'object',
        properties: { query: { type: 'string' } },
        required: ['query'],
        additionalProperties: false,
      },
      handler: async ({ query }) => ({ ok: true, ...(await searchKnowledge(asString(query))) }),
    },
    [],
  )

  useFrontendTool(
    {
      name: 'read_knowledge',
      description: 'Прочитать один файл памяти знаний по пути из search_knowledge.',
      parameters: {
        type: 'object',
        properties: { path: { type: 'string' } },
        required: ['path'],
        additionalProperties: false,
      },
      handler: async ({ path }) => ({ ok: true, ...(await readKnowledge(asString(path))) }),
    },
    [],
  )

  useFrontendTool(
    {
      name: 'open_ref_image',
      description: 'Показать картинку-референс из products/refs (для наших товаров — только products/refs/ours).',
      parameters: {
        type: 'object',
        properties: { path: { type: 'string' }, caption: { type: 'string' } },
        required: ['path'],
        additionalProperties: false,
      },
      handler: async ({ path, caption }) => {
        const url = refImageUrl(asString(path))
        const response = await fetch(url)  // the ref route is GET-only
        if (!response.ok) return { ok: false, error: 'Нет такой картинки.' }
        onImage(url, asString(caption) || asString(path))
        return { ok: true, url }
      },
    },
    [onImage],
  )

  useFrontendTool(
    {
      name: 'autopilot_status',
      description: 'Узнать, на каком шаге автопилот и готов ли ролик.',
      parameters: {
        type: 'object',
        properties: { run_id: { type: 'string' } },
        required: ['run_id'],
        additionalProperties: false,
      },
      handler: async ({ run_id }) => {
        const run = await fetchAutopilot(asString(run_id))
        return { ok: true, status: run.status, label: run.label, progress: run.progress, output: run.output, error: run.error }
      },
    },
    [],
  )

  useFrontendTool(
    {
      name: 'cancel_autopilot',
      description: 'Остановить автопилот.',
      parameters: {
        type: 'object',
        properties: { run_id: { type: 'string' } },
        required: ['run_id'],
        additionalProperties: false,
      },
      handler: async ({ run_id }) => {
        const run = await cancelAutopilot(asString(run_id))
        return { ok: true, status: run.status }
      },
    },
    [],
  )

  return null
}
