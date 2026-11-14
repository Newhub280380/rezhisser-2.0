/** Server-side autopilot (app/services/autopilot.py): start a recipe run, poll its progress. */

export type AutopilotRun = {
  id: string
  recipe: string
  status: 'running' | 'done' | 'failed' | 'cancelled'
  step: string
  label: string
  progress: number
  log: string[]
  scenes: number
  warnings: string[]
  output: { filename: string; url: string } | null
  error: string | null
  /** one_prompt_film only */
  script?: { title: string; hook: string; grade?: string | null; issues?: string[] }
  scenes_detail?: Array<{ index: number; seconds: number; prompt: string; voiceover?: string; product?: boolean }>
}

async function send(url: string, init?: RequestInit): Promise<AutopilotRun> {
  const response = await fetch(url, init)
  if (!response.ok) {
    let detail = `Ошибка ${response.status}`
    try {
      detail = (await response.json()).detail || detail
    } catch {
      // keep the status text
    }
    throw new Error(detail)
  }
  return response.json()
}

export function startAutopilot(body: Record<string, unknown>): Promise<AutopilotRun> {
  return send('/api/v1/assistant/autopilot', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function fetchAutopilot(id: string): Promise<AutopilotRun> {
  return send(`/api/v1/assistant/autopilot/${encodeURIComponent(id)}`)
}

/** One-prompt films: re-shoot one scene (optionally with a new prompt); the rest of the film is reused. */
export function regenerateScene(id: string, index: number, prompt = ''): Promise<AutopilotRun> {
  return send(`/api/v1/assistant/autopilot/${encodeURIComponent(id)}/scene/${index}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt }),
  })
}

export type KnowledgeNode = { path: string; title: string; group: string; description: string; links: string[]; images: string[] }

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url)
  if (!response.ok) throw new Error(`Ошибка ${response.status}`)
  return response.json()
}

export function searchKnowledge(query: string): Promise<{ nodes: KnowledgeNode[] }> {
  return getJson(`/api/v1/assistant/knowledge/search?q=${encodeURIComponent(query)}`)
}

export function readKnowledge(path: string): Promise<{ path: string; text: string; truncated?: boolean }> {
  return getJson(`/api/v1/assistant/knowledge/read?path=${encodeURIComponent(path)}`)
}

export function refImageUrl(path: string): string {
  const clean = path.replace(/^products\//, '').split('/').map(encodeURIComponent).join('/')
  return `/api/v1/assistant/knowledge/ref/${clean}`
}

export function cancelAutopilot(id: string): Promise<AutopilotRun> {
  return send(`/api/v1/assistant/autopilot/${encodeURIComponent(id)}/cancel`, { method: 'POST' })
}
