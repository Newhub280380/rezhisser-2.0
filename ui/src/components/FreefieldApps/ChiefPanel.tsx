import { useEffect, useState } from 'react'
import { uploadImage } from '../../api/client'
import {
  cancelChief, chiefFileUrl, confirmChief, fetchChiefChains, fetchChiefJob, planChief,
  type ChiefChain, type ChiefJob, type ChiefStep,
} from './freefieldApi'

/** Руководитель: one request -> plan from Freefield apps + helper steps -> price -> confirmation -> run.
 *  Nothing paid starts before the person presses the button with the price on it. */
export function ChiefPanel() {
  const [chains, setChains] = useState<ChiefChain[]>([])
  const [falReady, setFalReady] = useState(true)
  const [text, setText] = useState('')
  const [videoUrl, setVideoUrl] = useState('')
  const [video, setVideo] = useState('')
  const [photo, setPhoto] = useState('')
  const [resolution, setResolution] = useState('480p')
  const [job, setJob] = useState<ChiefJob | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    fetchChiefChains().then(r => { setChains(r.chains); setFalReady(r.fal_ready) }).catch(e => setError(String(e.message || e)))
  }, [])

  useEffect(() => {
    if (!job || (job.status !== 'planning' && job.status !== 'running')) return
    const timer = setInterval(() => { fetchChiefJob(job.id).then(setJob).catch(e => setError(String(e.message || e))) }, 1500)
    return () => clearInterval(timer)
  }, [job])

  const act = async (fn: () => Promise<ChiefJob>) => {
    setError(''); setBusy(true)
    try { setJob(await fn()) } catch (e) { setError(String((e as Error).message || e)) }
    setBusy(false)
  }
  const makePlan = () => act(() => planChief({
    text, resolution, ...(videoUrl.trim() ? { video_url: videoUrl.trim() } : video ? { video } : {}), ...(photo ? { photo } : {}),
  }))
  const total = job?.cost?.total_usd
  const confirm = () => {
    const price = total != null ? `≈ $${total.toFixed(2)}` : 'по каталогу'
    const extra = job?.cost?.catalog_only.length ? ` + по каталогу: ${job.cost.catalog_only.join(', ')}` : ''
    if (!window.confirm(`Запустить платные шаги в облаке fal? Сумма ${price}${extra}.`)) return
    act(() => confirmChief(job!.id))
  }

  if (job) {
    return (
      <div className="mx-auto max-w-2xl space-y-3">
        <button type="button" onClick={() => { setJob(null); setError('') }} disabled={job.status === 'running'}
          className="text-xs text-text-secondary hover:text-text-primary disabled:opacity-50">← Новая просьба</button>
        <div>
          <h3 className="text-base font-semibold text-text-primary">{job.chain_name}</h3>
          <p className="text-xs text-text-secondary">«{job.text || 'без текста'}» · {STATUS[job.status]}</p>
          {job.notes.length > 0 && <p className="text-[11px] text-text-muted">База знаний: {job.notes.join(' · ')}</p>}
        </div>
        {job.status === 'soon' && (
          <p className="rounded-lg border border-dashed border-border p-3 text-sm text-amber-300/90">Скоро. {job.warnings.join(' ')}</p>
        )}
        {job.steps.length > 0 && (
          <ol className="space-y-1.5" aria-label="Шаги">
            {job.steps.map((step, i) => <StepRow key={step.id} n={i + 1} step={step} jobId={job.id} />)}
          </ol>
        )}
        {job.status !== 'soon' && job.warnings.length > 0 && (
          <ul className="text-[11px] text-amber-300/90">{job.warnings.map(w => <li key={w}>⚠ {w}</li>)}</ul>
        )}
        {job.cost && (job.status === 'awaiting_confirmation' || job.status === 'failed') && (
          <div className="rounded-lg border border-border p-3 text-sm" aria-label="Цена">
            <p className="mb-1 font-medium text-text-primary">Платные вызовы fal</p>
            <ul className="space-y-0.5 text-xs text-text-secondary">
              {job.cost.items.map(item => (
                <li key={item.step}>{item.label}: {item.usd != null ? `$${item.usd.toFixed(item.usd < 0.01 ? 4 : 2)}` : `по каталогу — ${item.text}`}</li>
              ))}
            </ul>
            <p className="mt-1 text-sm text-text-primary">Итого: {total != null ? `≈ $${total.toFixed(2)}` : 'по каталогу'}</p>
          </div>
        )}
        {error && <p className="text-sm text-red-400">{error}</p>}
        {job.error && <p className="text-sm text-red-400">Ошибка: {job.error}</p>}
        <div className="flex flex-wrap gap-2">
          {(job.status === 'awaiting_confirmation' || (job.status === 'failed' && job.cost)) && (
            <button type="button" onClick={confirm} disabled={busy || !falReady} title={!falReady ? 'Нет ключа fal' : undefined}
              className="rounded-lg bg-toggle-active px-3 py-1.5 text-sm font-medium text-white hover:opacity-95 disabled:opacity-50">
              {job.status === 'failed' ? 'Повторить с места ошибки' : 'Подтвердить и запустить'}
              {total != null ? ` — ≈ $${total.toFixed(2)}` : ''} (платно, fal)
            </button>
          )}
          {(job.status === 'awaiting_confirmation' || job.status === 'running' || job.status === 'planning') && (
            <button type="button" onClick={() => act(() => cancelChief(job.id))} disabled={busy}
              className="rounded-lg border border-border px-3 py-1.5 text-sm text-text-primary hover:bg-bg-hover disabled:opacity-50">
              Отменить
            </button>
          )}
        </div>
        {!falReady && job.status === 'awaiting_confirmation' && (
          <p className="text-[11px] text-amber-300">Ключ fal не задан — запуск недоступен (Settings → Integrations → Cloud).</p>
        )}
        {job.status === 'done' && job.output && (
          <div className="space-y-2 rounded-lg border border-border p-2">
            <p className="text-sm text-emerald-300">Готово: {job.output.filename} (в галерее)</p>
            {job.output.kind === 'video' && <video src={job.output.url} controls className="max-h-96 w-full rounded" />}
            {job.output.kind === 'image' && <img src={job.output.url} alt="Результат" className="max-h-96 rounded" />}
            {job.output.kind === 'audio' && <audio src={job.output.url} controls className="w-full" />}
          </div>
        )}
      </div>
    )
  }

  const box = 'w-full rounded-lg border border-border bg-bg-primary px-2 py-1.5 text-sm text-text-primary'
  return (
    <div className="mx-auto max-w-2xl space-y-3">
      <div>
        <h3 className="text-base font-semibold text-text-primary">Руководитель</h3>
        <p className="text-xs text-text-secondary">
          Напишите просьбу и дайте видео и фото. Руководитель составит план из готовых приложений, бесплатно подготовит
          файлы, покажет цену и запустит платные шаги только после вашего подтверждения.
        </p>
      </div>
      <label className="block">
        <span className="mb-1 block text-xs text-text-secondary">Что сделать *</span>
        <textarea rows={2} className={box} value={text} onChange={e => setText(e.target.value)}
          placeholder="Замени человека в этом клипе на меня" />
      </label>
      <label className="block">
        <span className="mb-1 block text-xs text-text-secondary">Ссылка на видео</span>
        <input type="url" className={box} value={videoUrl} onChange={e => setVideoUrl(e.target.value)} placeholder="https://www.youtube.com/watch?v=…" />
      </label>
      <Upload label="или видео файлом" accept="video/*" onDone={setVideo} />
      <Upload label="Фото (кого ставим в клип)" accept="image/*" onDone={setPhoto} />
      <label className="block">
        <span className="mb-1 block text-xs text-text-secondary">Качество Recast</span>
        <select className={box} value={resolution} onChange={e => setResolution(e.target.value)}>
          <option value="480p">480p — $0.04/с</option>
          <option value="580p">580p — $0.06/с</option>
          <option value="720p">720p — $0.08/с</option>
        </select>
      </label>
      {error && <p className="text-sm text-red-400">{error}</p>}
      <button type="button" onClick={makePlan} disabled={busy || !text.trim()}
        className="rounded-lg bg-toggle-active px-3 py-1.5 text-sm font-medium text-white hover:opacity-95 disabled:opacity-50">
        {busy ? 'Составляю…' : 'Составить план (бесплатно)'}
      </button>
      {chains.length > 0 && (
        <div className="pt-2">
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-text-muted">Что умеет руководитель</p>
          <ul className="space-y-1">
            {chains.map(chain => (
              <li key={chain.id} className="text-xs text-text-secondary">
                <span className={`mr-1 rounded px-1.5 py-0.5 text-[10px] ${chain.status === 'ready' ? 'bg-emerald-500/15 text-emerald-300' : 'bg-bg-tertiary text-text-muted'}`}>
                  {chain.status === 'ready' ? 'работает' : 'скоро'}
                </span>
                <b className="text-text-primary">{chain.name}.</b> {chain.summary}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

const STATUS: Record<ChiefJob['status'], string> = {
  planning: 'готовлю бесплатно…', awaiting_confirmation: 'ждёт подтверждения цены', running: 'выполняется…',
  done: 'готово', failed: 'ошибка', cancelled: 'отменено', soon: 'скоро',
}
const MARK: Record<ChiefStep['status'], string> = { pending: '○', running: '⟳', done: '✓', skipped: '—', failed: '✕' }
const MARK_COLOR: Record<ChiefStep['status'], string> = {
  pending: 'text-text-muted', running: 'text-sky-300', done: 'text-emerald-300', skipped: 'text-text-muted', failed: 'text-red-400',
}
const STEP_STATUS: Record<ChiefStep['status'], string> = {
  pending: 'ждёт', running: 'идёт', done: 'готово', skipped: 'не нужно', failed: 'ошибка',
}

function StepRow({ n, step, jobId }: { n: number; step: ChiefStep; jobId: string }) {
  const url = step.file ? chiefFileUrl(jobId, step.file) : ''
  return (
    <li className="rounded-lg border border-border bg-bg-primary/60 px-2 py-1.5 text-sm">
      <div className="flex items-start gap-2">
        <span className={`w-4 shrink-0 text-center ${MARK_COLOR[step.status]}`} aria-label={STEP_STATUS[step.status]}>{MARK[step.status]}</span>
        <div className="min-w-0 flex-1">
          <span className="text-text-primary">{n}. {step.label}</span>
          <span className={`ml-2 rounded px-1 text-[10px] ${step.kind === 'paid' ? 'bg-amber-500/15 text-amber-300' : 'bg-bg-tertiary text-text-muted'}`}>
            {step.kind === 'paid' ? 'платно, fal' : 'бесплатно'}
          </span>
          {step.detail && <p className="text-[11px] text-text-secondary">{step.detail}</p>}
          {url && /\.(png|jpe?g|webp)$/i.test(step.file!) && <img src={url} alt={step.label} className="mt-1 max-h-32 rounded" />}
          {url && /\.mp4$/i.test(step.file!) && <video src={url} controls className="mt-1 max-h-40 rounded" />}
        </div>
      </div>
    </li>
  )
}

function Upload({ label, accept, onDone }: { label: string; accept: string; onDone: (name: string) => void }) {
  const [state, setState] = useState('')
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-text-secondary">{label}</span>
      <input type="file" accept={accept} className="block text-xs text-text-secondary"
        onChange={async event => {
          const file = event.target.files?.[0]
          if (!file) return
          setState('Загружаю…')
          try { onDone((await uploadImage(file)).filename); setState(`${file.name} — загружено`) } catch { onDone(''); setState('Не удалось загрузить') }
        }} />
      {state && <span className="text-[11px] text-text-muted">{state}</span>}
    </label>
  )
}
