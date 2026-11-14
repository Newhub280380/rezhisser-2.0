import { useEffect, useState } from 'react'
import { cancelAutopilot, fetchAutopilot, type AutopilotRun } from './autopilotApi'

/** Live progress of one autopilot run (progress_labels from recipes.json), then the finished mp4. */
export function AutopilotCard({ runId }: { runId: string }) {
  const [run, setRun] = useState<AutopilotRun | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    let timer: ReturnType<typeof setTimeout> | undefined
    const tick = async () => {
      try {
        const next = await fetchAutopilot(runId)
        if (!alive) return
        setRun(next)
        if (next.status === 'running') timer = setTimeout(tick, 2000)
      } catch (err) {
        if (alive) setError(err instanceof Error ? err.message : 'Нет связи с автопилотом.')
      }
    }
    void tick()
    return () => {
      alive = false
      if (timer) clearTimeout(timer)
    }
  }, [runId])

  if (error) return <div role="alert" className="rounded-xl bg-bg-tertiary px-3 py-2 text-sm text-red-400">{error}</div>
  if (!run) return <div className="rounded-xl bg-bg-tertiary px-3 py-2 text-sm text-text-muted">Запускаю автопилот…</div>

  return (
    <section aria-label="Автопилот" className="max-w-[92%] space-y-2 rounded-xl bg-bg-tertiary px-3 py-2 text-sm text-text-primary">
      <div className="flex items-center justify-between gap-2">
        <p className="font-medium" aria-live="polite">{run.status === 'running' ? run.label || 'Начинаю…' : run.label}</p>
        {run.status === 'running' && (
          <button type="button" onClick={() => void cancelAutopilot(runId).then(setRun).catch(() => {})}
            className="rounded-md px-2 py-0.5 text-[11px] text-text-muted hover:bg-bg-hover hover:text-text-primary">
            Остановить
          </button>
        )}
      </div>
      <div role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={run.progress}
        aria-label="Прогресс автопилота" className="h-1.5 w-full overflow-hidden rounded-full bg-bg-hover">
        <div className="h-full bg-toggle-active transition-all" style={{ width: `${run.progress}%` }} />
      </div>
      {run.log.length > 1 && (
        <ol className="space-y-0.5 text-[11px] text-text-muted">
          {run.log.slice(-4, -1).map((line, index) => <li key={`${index}-${line}`}>✓ {line}</li>)}
        </ol>
      )}
      {run.warnings.map(warning => <p key={warning} className="text-[11px] text-amber-400">{warning}</p>)}
      {run.status === 'failed' && <p role="alert" className="text-xs text-red-400">{run.error}</p>}
      {run.status === 'cancelled' && <p className="text-xs text-text-muted">Остановлено.</p>}
      {run.output && (
        <div className="space-y-1">
          <video src={run.output.url} controls playsInline className="max-h-80 w-full rounded-lg bg-black" />
          <a href={run.output.url} download={run.output.filename} className="text-xs text-accent-blue underline">
            Скачать {run.output.filename}
          </a>
        </div>
      )}
    </section>
  )
}
