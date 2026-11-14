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

export function cancelAutopilot(id: string): Promise<AutopilotRun> {
  return send(`/api/v1/assistant/autopilot/${encodeURIComponent(id)}/cancel`, { method: 'POST' })
}
