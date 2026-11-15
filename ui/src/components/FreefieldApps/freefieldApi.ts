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

// ---------------------------------------------------------------- Руководитель (app/services/chief.py)

export type ChiefStep = {
  id: string
  label: string
  kind: 'free' | 'paid'
  app: string | null
  status: 'pending' | 'running' | 'done' | 'skipped' | 'failed'
  detail: string
  file: string | null
  price_usd: number | null
  price_text: string | null
}
export type ChiefJob = {
  id: string
  chain: string
  chain_name: string
  app: string | null
  text: string
  status: 'planning' | 'awaiting_confirmation' | 'running' | 'done' | 'failed' | 'cancelled' | 'soon'
  steps: ChiefStep[]
  cost: { items: Array<{ step: string; label: string; usd: number | null; text: string }>; total_usd: number | null; catalog_only: string[] } | null
  warnings: string[]
  notes: string[]
  output: { filename: string; url: string; kind: string } | null
  error: string | null
}
export type ChiefChain = { id: string; name: string; status: 'ready' | 'soon'; summary: string; needs?: string }
export type ChiefRequest = { text: string; video_url?: string; video?: string; photo?: string; resolution?: string }

export const fetchChiefChains = () => send<{ chains: ChiefChain[]; fal_ready: boolean }>('/api/v1/chief/chains')
export const planChief = (request: ChiefRequest) => send<ChiefJob>('/api/v1/chief/plan', post(request))
export const fetchChiefJob = (id: string) => send<ChiefJob>(`/api/v1/chief/jobs/${encodeURIComponent(id)}`)
export const confirmChief = (id: string) => send<ChiefJob>(`/api/v1/chief/jobs/${encodeURIComponent(id)}/confirm`, post({ confirm: true }))
export const cancelChief = (id: string) => send<ChiefJob>(`/api/v1/chief/jobs/${encodeURIComponent(id)}/cancel`, post({}))
export const chiefFileUrl = (id: string, name: string) => `/api/v1/chief/jobs/${encodeURIComponent(id)}/files/${encodeURIComponent(name)}`
