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
}: {
  category: AssistantCategory | null
  fileInputRef: React.RefObject<HTMLInputElement | null>
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
            enum: ['face_swap', 'photo_to_video', 'text_to_video'],
            description: 'Категория из библиотеки знаний',
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
        useStore.setState(current => {
          const nextParams = { ...current.params } as Record<string, unknown>
          if (duration) nextParams.video_length = duration
          if (asString(args.resolution)) nextParams.resolution = asString(args.resolution)
          return {
            prompt: prompt || current.prompt,
            params: nextParams as typeof current.params,
          }
        })
        return {
          ok: true,
          prompt: prompt || useStore.getState().prompt,
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

  return null
}
