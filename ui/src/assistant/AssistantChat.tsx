import { useEffect, useRef, useState } from 'react'
import { Sparkles, X } from 'lucide-react'
import { AssistantTools } from './AssistantTools'
import {
  KNOWLEDGE_PRESETS,
  knowledgeForPrompt,
  type AssistantCategory,
} from './knowledge'
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
  const [category, setCategory] = useState<AssistantCategory | null>(null)
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
        context: {
          category,
          knowledge: knowledgeForPrompt(),
        },
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

    const knowledgeNote = category
      ? `Выбранная категория: ${category}. Библиотека знаний:\n${knowledgeForPrompt()}`
      : `Библиотека знаний:\n${knowledgeForPrompt()}`

    if (historyRef.current.length === 0) {
      historyRef.current.push({ role: 'user', content: `${knowledgeNote}\n\n${userText}` })
    } else {
      historyRef.current.push({ role: 'user', content: userText })
    }

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
      <AssistantTools category={category} fileInputRef={fileInputRef} />
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
                : 'Нужен ключ OpenRouter в Настройках → Services → Cloud'}
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
        {KNOWLEDGE_PRESETS.map(preset => (
          <button
            key={preset.id}
            type="button"
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
        {busy && <p className="text-xs text-text-muted">Думаю и нажимаю кнопки…</p>}
      </div>

      {error && (
        <p className="px-4 pb-2 text-xs text-red-400">{error}</p>
      )}

      <form onSubmit={onSubmit} className="border-t border-border p-3">
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
          placeholder="Например: вот фото, сделай из него 5-секундный ролик"
          className="mb-2 w-full resize-none rounded-lg border border-border bg-bg-tertiary px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-blue"
          disabled={busy}
        />
        <button
          type="submit"
          disabled={busy || !draft.trim()}
          className="w-full rounded-lg bg-toggle-active px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          Отправить
        </button>
      </form>
    </aside>
  )
}
