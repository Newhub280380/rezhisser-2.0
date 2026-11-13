import { useEffect, useId, useState } from 'react'
import { fetchCloudConfig, updateCloudConfig, type CloudConfig } from '../../api/client'
import { ApiKeyField } from './ApiKeyField'

const LABELS: Record<string, string> = {
  local: 'Local models (this PC)',
  minimax: 'Cloud · MiniMax API',
  fal: 'Cloud · fal',
  muapi: 'Cloud · MuAPI',
}
const KEY_OF: Record<string, string> = { minimax: 'MINIMAX_API_KEY', fal: 'FAL_KEY', muapi: 'MUAPI_API_KEY' }

/** Generation backend picker shared by Studio, Director and Settings.
 *  `full` adds the API key and cloud LLM fields (Settings). */
export function CloudEngineControl({ full = false }: { full?: boolean }) {
  const id = useId()
  const [config, setConfig] = useState<CloudConfig | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    // An older or offline backend must never break the surrounding Studio/Director panel.
    fetchCloudConfig().then(c => setConfig(validConfig(c))).catch(() => setConfig(null))
  }, [])

  const save = async (partial: Record<string, string>) => {
    setError('')
    try {
      setConfig(validConfig(await updateCloudConfig(partial)))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      throw err
    }
  }

  if (!config) return null
  const missingKey = config.provider !== 'local' && !config.providers.find(p => p.name === config.provider)?.ready

  return (
    <div className="space-y-2">
      <label htmlFor={id} className="text-[11px] text-text-muted uppercase tracking-wider block">Generation backend</label>
      <select
        id={id}
        value={config.provider}
        onChange={e => void save({ CLOUD_PROVIDER: e.target.value }).catch(() => {})}
        className="w-full bg-bg-tertiary border border-border rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent-blue"
      >
        {['local', ...config.providers.map(p => p.name)].map(name => (
          <option key={name} value={name}>{LABELS[name] || name}</option>
        ))}
      </select>
      {missingKey && (
        <p role="status" className="text-xs text-amber-400">API key for this provider is not set — Settings → Services → Cloud.</p>
      )}
      {full && (
        <>
          {config.providers.map(p => (
            <ApiKeyField
              key={p.name}
              label={`${LABELS[p.name] || p.name} key`}
              maskedValue="••••••••"
              isSet={config.keys[KEY_OF[p.name]]}
              onSave={value => save({ [KEY_OF[p.name]]: value })}
            />
          ))}
          <TextSetting label="Cloud LLM URL (OpenAI-compatible)" value={config.llm_base_url}
            placeholder="https://api.minimax.io/v1" onSave={v => save({ LLM_BASE_URL: v })} />
          <TextSetting label="Cloud LLM model" value={config.llm_model}
            placeholder="MiniMax-M2" onSave={v => save({ LLM_MODEL: v })} />
          <ApiKeyField label="Cloud LLM key" maskedValue="••••••••" isSet={config.keys.LLM_API_KEY}
            onSave={value => save({ LLM_API_KEY: value })} />
          <p className="text-[10px] text-text-muted">
            Keys are stored in .env. With a cloud backend selected, Director and Studio planners use the cloud LLM
            when the LLM provider above is Local.
          </p>
        </>
      )}
      {error && <p role="alert" className="text-xs text-red-400">{error}</p>}
    </div>
  )
}

function validConfig(value: unknown): CloudConfig | null {
  const c = value as CloudConfig | null
  return c && typeof c.provider === 'string' && Array.isArray(c.providers) && c.keys && typeof c.keys === 'object'
    ? c : null
}

function TextSetting({ label, value, placeholder, onSave }: {
  label: string; value: string; placeholder: string; onSave: (value: string) => Promise<void>
}) {
  const id = useId()
  const [draft, setDraft] = useState(value)
  useEffect(() => setDraft(value), [value])
  return (
    <div>
      <label htmlFor={id} className="text-[11px] text-text-muted uppercase tracking-wider mb-1.5 block">{label}</label>
      <input
        id={id}
        type="text"
        value={draft}
        placeholder={placeholder}
        onChange={e => setDraft(e.target.value)}
        onBlur={() => { if (draft !== value) void onSave(draft).catch(() => {}) }}
        className="w-full bg-bg-tertiary border border-border rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent-blue"
      />
    </div>
  )
}
