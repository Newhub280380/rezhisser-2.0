/** Freefield apps (app/services/freefield_apps.py): catalog, free dry-run, paid run on fal, run status. */

export type FFInput = {
  id: string
  type: 'image' | 'video' | 'audio' | 'text' | 'textarea' | 'select' | 'slider' | 'number' | 'toggle' | 'seed'
  label: string
  required: boolean
  default?: string | number | boolean
  options?: Array<string | number>
  min?: number
  max?: number
  step?: number
  help?: string
}

export type FFApp = {
  id: string
  name: string
  section: string
  summary: string
  freefield_app: string
  models: string
  status: 'ready' | 'soon'
  inputs: FFInput[]
  endpoint: string | null
  price: string | null
  output: 'video' | 'image' | 'audio'
  needs: string | null
  priority: boolean
  alt_of: string | null
}

export type FFCatalog = { checked: string; sections: Array<{ id: string; label: string }>; apps: FFApp[]; fal_ready: boolean }
export type FFPlan = { app: string; endpoint: string; url: string; body: Record<string, unknown>; price: string; submitted: false }
export type FFRun = {
  id: string
  app: string
  name: string
  endpoint: string
  status: 'running' | 'done' | 'failed'
  output: { filename: string; url: string; kind: string } | null
  error: string | null
}

async function send<T>(url: string, init?: RequestInit): Promise<T> {
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

const post = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const fetchFreefieldCatalog = () => send<FFCatalog>('/api/v1/freefield/apps')
export const dryRunFreefield = (id: string, inputs: Record<string, unknown>) =>
  send<FFPlan>(`/api/v1/freefield/apps/${encodeURIComponent(id)}/dry-run`, post({ inputs }))
export const runFreefield = (id: string, inputs: Record<string, unknown>) =>
  send<FFRun>(`/api/v1/freefield/apps/${encodeURIComponent(id)}/run`, post({ inputs }))
export const fetchFreefieldRun = (id: string) => send<FFRun>(`/api/v1/freefield/runs/${encodeURIComponent(id)}`)
