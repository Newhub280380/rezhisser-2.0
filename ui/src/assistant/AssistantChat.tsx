import { useCallback, useEffect, useRef, useState } from 'react'
import { Paperclip, Sparkles, X } from 'lucide-react'
import { uploadImage } from '../api/client'
import { AssistantTools } from './AssistantTools'
import { AutopilotCard } from './AutopilotCard'
import { matchCommands, useKnowledge, type AssistantCategory } from './knowledge'
import { callFrontendTool, frontendToolsAsOpenAI } from './useFrontendTool'

type ChatRole = 'user' | 'assistant' | 'system'
type ChatMessage = { role: ChatRole; content: string }

type AssistantStatus = {
  ready: boolean
  model: string
  fallback_model: string
  key_set: boolean
}

type ToolCall = {
  id?: string
  type?: string
  function?: { name?: string; arguments?: string }
}

async function readApiError(response: Response): Promise<string> {
  try {
    const body = await response.json()
    return body.detail || body.error || `Ошибка ${response.status}`
  } catch {
    return `Ошибка ${response.status}`
  }
}

function toolResultContent(result: unknown): string {
  try {
    return typeof result === 'string' ? result : JSON.stringify(result)
  } catch {
    return '{"ok":false}'
  }
}

export function AssistantChat({ onClose }: { onClose: () => void }) {
  const knowledge = useKnowledge()
  const [category, setCategory] = useState<AssistantCategory | null>(null)
  const [attachments, setAttachments] = useState<Array<{ filename: string; url: string }>>([])
  const [uploading, setUploading] = useState(false)
  const [runIds, setRunIds] = useState<string[]>([])
  const attachInputRef = useRef<HTMLInputElement | null>(null)
  const onAutopilot = useCallback((runId: string) => setRunIds(current => [...current, runId]), [])
  const [status, setStatus] = useState<AssistantStatus | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content: 'Выберите, что нужно сделать, и напишите своими словами. Можно сразу прислать фото. Я сам открою экран, выставлю настройки и запущу генерацию.',
    },
  ])
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const listRef = useRef<HTMLDivElement | null>(null)
  const historyRef = useRef<Array<Record<string, unknown>>>([])

  useEffect(() => {
    void fetch('/api/v1/assistant/status')
      .then(async response => {
        if (!response.ok) throw new Error(await readApiError(response))
        return response.json()
      })
      .then(setStatus)
      .catch(() => setStatus({ ready: false, model: '', fallback_model: '', key_set: false }))
  }, [])

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, busy])

  async function sendConversation(pending: Array<Record<string, unknown>>) {
    const tools = frontendToolsAsOpenAI()
    const response = await fetch('/api/v1/assistant/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages: pending,
        tools,
        // Knowledge (recipes, slash commands, rules) is added on the server from docs/assistant-knowledge.
        context: { category },
      }),
    })
    if (!response.ok) throw new Error(await readApiError(response))
    return response.json() as Promise<{
      message: {
        role?: string
        content?: string | null
        tool_calls?: ToolCall[]
      }
      model_used?: string
      used_fallback?: boolean
    }>
  }

  async function runTurn(userText: string) {
    const visible: ChatMessage[] = [...messages, { role: 'user', content: userText }]
    setMessages(visible)
    setBusy(true)
    setError(null)

    const attached = attachments.length
      ? `\n[Прикреплено фото: ${attachments.length} (${attachments.map(item => item.filename).join(', ')})]`
      : ''
    historyRef.current.push({ role: 'user', content: userText + attached })

    try {
      for (let step = 0; step < 8; step += 1) {
        const data = await sendConversation(historyRef.current)
        const message = data.message || {}
        const toolCalls = message.tool_calls || []
        historyRef.current.push(message as Record<string, unknown>)

        if (toolCalls.length) {
          const notes: string[] = []
          for (const call of toolCalls) {
            const name = call.function?.name || ''
            let args: Record<string, unknown> = {}
            try {
              args = JSON.parse(call.function?.arguments || '{}')
            } catch {
              args = {}
            }
            const result = await callFrontendTool(name, args)
            notes.push(name)
            historyRef.current.push({
              role: 'tool',
              tool_call_id: call.id,
              content: toolResultContent(result),
            })
          }
          setMessages(current => [
            ...current,
            { role: 'assistant', content: `Делаю: ${notes.join(', ')}` },
          ])
          continue
        }

        const text = (message.content || '').trim() || 'Готово.'
        setMessages(current => [...current, { role: 'assistant', content: text }])
        return
      }
      setMessages(current => [
        ...current,
        { role: 'assistant', content: 'Слишком много шагов подряд. Напишите, с чего продолжить.' },
      ])
    } catch (err) {
      const text = err instanceof Error ? err.message : 'Не получилось связаться с помощником.'
      setError(text)
      setMessages(current => [...current, { role: 'assistant', content: text }])
    } finally {
      setBusy(false)
    }
  }

  async function attachFiles(files: FileList | null) {
    if (!files?.length) return
    setUploading(true)
    setError(null)
    try {
      const uploaded: Array<{ filename: string; url: string }> = []
      for (const file of Array.from(files)) {
        const result = await uploadImage(file)
        uploaded.push({ filename: result.filename, url: result.url })
      }
      setAttachments(current => [...current, ...uploaded])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось загрузить фото.')
    } finally {
      setUploading(false)
      if (attachInputRef.current) attachInputRef.current.value = ''
    }
  }

  const suggestions = matchCommands(draft, knowledge?.commands || [])

  function onSubmit(event: React.FormEvent) {
    event.preventDefault()
    const text = draft.trim()
    if (!text || busy) return
    setDraft('')
    void runTurn(text)
  }

  return (
    <aside
      className="flex h-full w-full max-w-md flex-col border-l border-border bg-bg-primary shadow-xl"
      aria-label="Помощник Режиссёра"
    >
      <AssistantTools
        category={category}
        fileInputRef={fileInputRef}
        attachments={attachments.map(item => item.filename)}
        onAutopilot={onAutopilot}
      />
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        aria-hidden="true"
      />

      <header className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <Sparkles size={16} className="text-accent-blue" />
          <div>
            <p className="text-sm font-semibold text-text-primary">Помощник</p>
            <p className="text-[11px] text-text-muted">
              {status?.key_set
                ? `Модель: ${status.model}`
                : 'Нужен ключ OpenRouter в Настройках → Integrations → Cloud'}
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-md p-1 text-text-muted hover:bg-bg-hover hover:text-text-primary"
          aria-label="Закрыть помощника"
        >
          <X size={16} />
        </button>
      </header>

      <div className="flex flex-wrap gap-2 border-b border-border px-4 py-3">
        {(knowledge?.categories || []).map(preset => (
          <button
            key={preset.id}
            type="button"
            title={preset.short}
            aria-pressed={category === preset.id}
            onClick={() => setCategory(preset.id)}
            className={`rounded-full px-3 py-1 text-[11px] transition-colors ${
              category === preset.id
                ? 'bg-toggle-active text-white'
                : 'bg-bg-tertiary text-text-secondary hover:bg-bg-hover hover:text-text-primary'
            }`}
          >
            {preset.title}
          </button>
        ))}
      </div>

      <div ref={listRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
        {messages.map((message, index) => (
          <div
            key={`${message.role}-${index}`}
            className={`max-w-[92%] rounded-xl px-3 py-2 text-sm leading-relaxed ${
              message.role === 'user'
                ? 'ml-auto bg-toggle-active text-white'
                : 'bg-bg-tertiary text-text-primary'
            }`}
          >
            {message.content}
          </div>
        ))}
        {runIds.map(id => <AutopilotCard key={id} runId={id} />)}
        {busy && <p className="text-xs text-text-muted">Думаю и нажимаю кнопки…</p>}
      </div>

      {error && (
        <p className="px-4 pb-2 text-xs text-red-400">{error}</p>
      )}

      <form onSubmit={onSubmit} className="relative border-t border-border p-3">
        {suggestions.length > 0 && (
          <ul aria-label="Команды" className="absolute bottom-full left-3 right-3 mb-1 max-h-64 overflow-y-auto rounded-lg border border-border bg-bg-secondary shadow-lg">
            {suggestions.map(command => (
              <li key={command.command}>
                <button
                  type="button"
                  onClick={() => setDraft(`${command.command} `)}
                  className="block w-full px-3 py-1.5 text-left text-xs text-text-primary hover:bg-bg-hover"
                >
                  <span className="font-medium">{command.command}</span>{' '}
                  <span className="text-text-muted">{command.title}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        {attachments.length > 0 && (
          <div className="mb-2 flex flex-wrap gap-1.5" aria-label="Прикреплённые фото">
            {attachments.map(item => (
              <span key={item.filename} className="relative">
                <img src={item.url} alt={item.filename} className="h-12 w-12 rounded-md object-cover" />
                <button
                  type="button"
                  aria-label={`Убрать ${item.filename}`}
                  onClick={() => setAttachments(current => current.filter(other => other.filename !== item.filename))}
                  className="absolute -right-1 -top-1 rounded-full bg-bg-primary p-0.5 text-text-muted hover:text-text-primary"
                >
                  <X size={10} />
                </button>
              </span>
            ))}
          </div>
        )}
        <input
          ref={attachInputRef}
          type="file"
          accept="image/*"
          multiple
          className="hidden"
          aria-label="Прикрепить фото"
          onChange={event => void attachFiles(event.target.files)}
        />
        <textarea
          value={draft}
          onChange={event => setDraft(event.target.value)}
          onKeyDown={event => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              onSubmit(event)
            }
          }}
          rows={3}
          placeholder="Например: вот 5 фото, сделай мини-ролик на 2–3 минуты. «/» — команды"
          className="mb-2 w-full resize-none rounded-lg border border-border bg-bg-tertiary px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-blue"
          disabled={busy}
        />
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => attachInputRef.current?.click()}
            disabled={uploading}
            className="flex items-center gap-1 rounded-lg border border-border px-3 py-2 text-sm text-text-secondary hover:bg-bg-hover disabled:opacity-50"
          >
            <Paperclip size={14} />
            {uploading ? 'Загружаю…' : 'Фото'}
          </button>
          <button
            type="submit"
            disabled={busy || !draft.trim()}
            className="flex-1 rounded-lg bg-toggle-active px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            Отправить
          </button>
        </div>
      </form>
    </aside>
  )
}
