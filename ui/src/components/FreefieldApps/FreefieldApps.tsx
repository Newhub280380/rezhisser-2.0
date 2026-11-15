import { useEffect, useMemo, useState } from 'react'
import { LayoutGrid, X } from 'lucide-react'
import { uploadImage } from '../../api/client'
import {
  dryRunFreefield, fetchFreefieldCatalog, fetchFreefieldRun, runFreefield,
  type FFApp, type FFCatalog, type FFInput, type FFPlan, type FFRun,
} from './freefieldApi'
import { ChiefPanel } from './ChiefPanel'

/** Freefield-style app catalog: one app per function. Ready apps run on fal (paid, confirmed);
 *  «скоро» apps show what they still need and have no action buttons. */
export function FreefieldAppsDock() {
  const [open, setOpen] = useState(false)
  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed bottom-16 right-4 z-40 flex items-center gap-2 rounded-full border border-border bg-bg-secondary px-4 py-2 text-sm font-medium text-text-primary shadow-lg hover:bg-bg-hover"
        aria-label="Открыть приложения"
      >
        <LayoutGrid size={16} />
        Приложения
      </button>
    )
  }
  return <FreefieldAppsPanel onClose={() => setOpen(false)} />
}

function FreefieldAppsPanel({ onClose }: { onClose: () => void }) {
  const [catalog, setCatalog] = useState<FFCatalog | null>(null)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<FFApp | null>(null)
  const [tab, setTab] = useState<'chief' | 'apps'>('chief')

  useEffect(() => {
    fetchFreefieldCatalog().then(setCatalog).catch(e => setError(String(e.message || e)))
  }, [])

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-3" role="dialog" aria-label="Приложения" translate="no">
      <div className="flex h-full max-h-[92vh] w-full max-w-5xl flex-col overflow-hidden rounded-xl border border-border bg-bg-secondary shadow-2xl">
        <header className="flex items-center justify-between border-b border-border px-4 py-3">
          <div>
            <h2 className="text-sm font-semibold text-text-primary">Приложения (как во Freefield)</h2>
            <p className="text-[11px] text-text-muted">
              «Работает» — запускается в облаке fal, цена указана на карточке. «Скоро» — ещё не подключено, кнопок нет.
            </p>
          </div>
          <div className="ml-auto mr-2 flex gap-1" role="tablist">
            {(['chief', 'apps'] as const).map(id => (
              <button key={id} type="button" role="tab" aria-selected={tab === id} onClick={() => setTab(id)}
                className={`rounded-lg px-3 py-1.5 text-xs ${tab === id ? 'bg-toggle-active text-white' : 'text-text-secondary hover:bg-bg-hover'}`}>
                {id === 'chief' ? 'Руководитель' : 'Все приложения'}
              </button>
            ))}
          </div>
          <button type="button" onClick={onClose} aria-label="Закрыть" className="rounded-lg p-2 text-text-secondary hover:bg-bg-hover">
            <X size={18} />
          </button>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          {tab === 'chief' && <ChiefPanel />}
          {tab === 'apps' && error && <p className="text-sm text-red-400">{error}</p>}
          {tab === 'apps' && !catalog && !error && <p className="text-sm text-text-muted">Загружаю…</p>}
          {tab === 'apps' && catalog && selected && (
            <AppForm app={selected} falReady={catalog.fal_ready} onBack={() => setSelected(null)} />
          )}
          {tab === 'apps' && catalog && !selected && <Catalog catalog={catalog} onOpen={setSelected} />}
        </div>
      </div>
    </div>
  )
}

function Catalog({ catalog, onOpen }: { catalog: FFCatalog; onOpen: (app: FFApp) => void }) {
  return (
    <div className="space-y-5">
      {!catalog.fal_ready && (
        <p className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-2 text-xs text-amber-300">
          Ключ fal не задан — запуск недоступен (Settings → Integrations → Cloud). Проверка запроса работает.
        </p>
      )}
      {catalog.sections.map(section => {
        const apps = catalog.apps
          .filter(app => app.section === section.id)
          .sort((a, b) => Number(b.priority) - Number(a.priority) || Number(b.status === 'ready') - Number(a.status === 'ready'))
        if (!apps.length) return null
        return (
          <section key={section.id}>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-muted">{section.label}</h3>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {apps.map(app => <AppCard key={app.id} app={app} onOpen={onOpen} />)}
            </div>
          </section>
        )
      })}
      <p className="text-[10px] text-text-muted">Цены — со страниц fal, проверено {catalog.checked}.</p>
    </div>
  )
}

function AppCard({ app, onOpen }: { app: FFApp; onOpen: (app: FFApp) => void }) {
  const ready = app.status === 'ready'
  const body = (
    <>
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-medium text-text-primary">{app.name}</span>
        <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] ${ready ? 'bg-emerald-500/15 text-emerald-300' : 'bg-bg-tertiary text-text-muted'}`}>
          {ready ? 'работает' : 'скоро'}
        </span>
      </div>
      <p className="mt-1 text-xs text-text-secondary">{app.summary}</p>
      <p className="mt-1 text-[11px] text-text-muted">{app.models}</p>
      {ready ? (
        <p className="mt-1 text-[11px] text-text-muted">{app.price}</p>
      ) : (
        <p className="mt-1 text-[11px] text-amber-300/90">Нужно: {app.needs}</p>
      )}
    </>
  )
  if (!ready) {
    return <div className="rounded-lg border border-dashed border-border bg-bg-primary/40 p-3 opacity-80">{body}</div>
  }
  return (
    <button type="button" onClick={() => onOpen(app)} className="rounded-lg border border-border bg-bg-primary p-3 text-left hover:border-toggle-active">
      {body}
    </button>
  )
}

function initialValues(app: FFApp): Record<string, unknown> {
  const values: Record<string, unknown> = {}
  for (const input of app.inputs) if (input.default !== undefined) values[input.id] = input.default
  return values
}

function AppForm({ app, falReady, onBack }: { app: FFApp; falReady: boolean; onBack: () => void }) {
  const [values, setValues] = useState<Record<string, unknown>>(() => initialValues(app))
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [plan, setPlan] = useState<FFPlan | null>(null)
  const [run, setRun] = useState<FFRun | null>(null)
  const set = (id: string, value: unknown) => { setValues(v => ({ ...v, [id]: value })); setPlan(null) }
  const missing = useMemo(
    () => app.inputs.filter(i => i.required && (values[i.id] === undefined || values[i.id] === '')).map(i => i.label),
    [app, values],
  )

  useEffect(() => {
    if (!run || run.status !== 'running') return
    const timer = setInterval(() => {
      fetchFreefieldRun(run.id).then(setRun).catch(e => setError(String(e.message || e)))
    }, 4000)
    return () => clearInterval(timer)
  }, [run])

  const check = async () => {
    setError(''); setBusy('check')
    try { setPlan(await dryRunFreefield(app.id, values)) } catch (e) { setError(String((e as Error).message || e)) }
    setBusy('')
  }

  const start = async () => {
    if (!window.confirm(`Запустить «${app.name}» в облаке fal? Это платно: ${app.price}.`)) return
    setError(''); setBusy('run')
    try { setRun(await runFreefield(app.id, values)) } catch (e) { setError(String((e as Error).message || e)) }
    setBusy('')
  }

  return (
    <div className="mx-auto max-w-2xl space-y-3">
      <button type="button" onClick={onBack} className="text-xs text-text-secondary hover:text-text-primary">← Все приложения</button>
      <div>
        <h3 className="text-base font-semibold text-text-primary">{app.name}</h3>
        <p className="text-xs text-text-secondary">{app.summary}</p>
        <p className="mt-1 text-[11px] text-text-muted">Модель: {app.models} · fal: {app.endpoint}</p>
        <p className="text-[11px] text-text-muted">Цена: {app.price}</p>
      </div>
      {app.inputs.map(input => (
        <Field key={input.id} input={input} value={values[input.id]} onChange={v => set(input.id, v)} />
      ))}
      {error && <p className="text-sm text-red-400">{error}</p>}
      <div className="flex flex-wrap gap-2">
        <button
          type="button" onClick={check} disabled={!!busy || missing.length > 0}
          className="rounded-lg border border-border px-3 py-1.5 text-sm text-text-primary hover:bg-bg-hover disabled:opacity-50"
        >
          {busy === 'check' ? 'Проверяю…' : 'Проверить запрос (бесплатно)'}
        </button>
        <button
          type="button" onClick={start} disabled={!!busy || missing.length > 0 || !falReady || run?.status === 'running'}
          title={!falReady ? 'Нет ключа fal' : undefined}
          className="rounded-lg bg-toggle-active px-3 py-1.5 text-sm font-medium text-white hover:opacity-95 disabled:opacity-50"
        >
          {busy === 'run' ? 'Отправляю…' : 'Запустить (платно, fal)'}
        </button>
      </div>
      {missing.length > 0 && <p className="text-[11px] text-text-muted">Заполните: {missing.join(', ')}</p>}
      {plan && (
        <pre className="max-h-64 overflow-auto rounded-lg bg-bg-primary p-2 text-[11px] text-text-secondary">
          {`Ничего не отправлено. Запрос, который уйдёт в fal:\nPOST ${plan.url}\n${JSON.stringify(plan.body, null, 2)}`}
        </pre>
      )}
      {run && (
        <div className="rounded-lg border border-border p-2 text-sm">
          {run.status === 'running' && <p className="text-text-secondary">Генерация в облаке… (можно закрыть окно, результат попадёт в галерею)</p>}
          {run.status === 'failed' && <p className="text-red-400">Ошибка: {run.error}</p>}
          {run.status === 'done' && run.output && (
            <div className="space-y-2">
              <p className="text-emerald-300">Готово: {run.output.filename}</p>
              {run.output.kind === 'video' && <video src={run.output.url} controls className="max-h-80 w-full rounded" />}
              {run.output.kind === 'image' && <img src={run.output.url} alt="" className="max-h-80 rounded" />}
              {run.output.kind === 'audio' && <audio src={run.output.url} controls className="w-full" />}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

const ACCEPT: Record<string, string> = { image: 'image/*', video: 'video/*', audio: 'audio/*,video/*' }

function Field({ input, value, onChange }: { input: FFInput; value: unknown; onChange: (v: unknown) => void }) {
  const [uploading, setUploading] = useState(false)
  const [fileLabel, setFileLabel] = useState('')
  const label = (
    <span className="mb-1 block text-xs text-text-secondary">
      {input.label}{input.required ? ' *' : ''}{input.help ? <span className="text-text-muted"> — {input.help}</span> : null}
    </span>
  )
  const box = 'w-full rounded-lg border border-border bg-bg-primary px-2 py-1.5 text-sm text-text-primary'

  if (input.type === 'image' || input.type === 'video' || input.type === 'audio') {
    return (
      <label className="block">
        {label}
        <input
          type="file" accept={ACCEPT[input.type]} disabled={uploading} className="block text-xs text-text-secondary"
          onChange={async event => {
            const file = event.target.files?.[0]
            if (!file) return
            setUploading(true)
            try {
              const uploaded = await uploadImage(file)
              onChange(uploaded.filename)
              setFileLabel(`${file.name} — загружено`)
            } catch {
              onChange('')
              setFileLabel('Не удалось загрузить')
            }
            setUploading(false)
          }}
        />
        {(uploading || fileLabel) && <span className="text-[11px] text-text-muted">{uploading ? 'Загружаю…' : fileLabel}</span>}
      </label>
    )
  }
  if (input.type === 'textarea') {
    return <label className="block">{label}<textarea rows={3} className={box} value={String(value ?? '')} onChange={e => onChange(e.target.value)} /></label>
  }
  if (input.type === 'select') {
    return (
      <label className="block">
        {label}
        <select className={box} value={String(value ?? '')} onChange={e => onChange(e.target.value)}>
          {(input.options || []).map(option => <option key={String(option)} value={String(option)}>{String(option)}</option>)}
        </select>
      </label>
    )
  }
  if (input.type === 'toggle') {
    return (
      <label className="flex items-center gap-2 text-xs text-text-secondary">
        <input type="checkbox" checked={Boolean(value)} onChange={e => onChange(e.target.checked)} />
        {input.label}
      </label>
    )
  }
  if (input.type === 'slider') {
    return (
      <label className="block">
        {label}
        <div className="flex items-center gap-2">
          <input type="range" className="flex-1" min={input.min} max={input.max} step={input.step ?? 1}
            value={Number(value ?? input.min ?? 0)} onChange={e => onChange(Number(e.target.value))} />
          <span className="w-10 text-right text-xs text-text-primary">{String(value ?? '')}</span>
        </div>
      </label>
    )
  }
  if (input.type === 'seed' || input.type === 'number') {
    return <label className="block">{label}<input type="number" className={box} value={String(value ?? '')} onChange={e => onChange(e.target.value === '' ? '' : Number(e.target.value))} /></label>
  }
  return <label className="block">{label}<input type="text" className={box} value={String(value ?? '')} onChange={e => onChange(e.target.value)} /></label>
}
