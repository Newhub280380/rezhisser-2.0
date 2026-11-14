import { useEffect, useState } from 'react'
import { cancelAutopilot, fetchAutopilot, regenerateScene, type AutopilotRun } from './autopilotApi'

/** Live progress of one autopilot run (progress_labels from recipes.json), then the finished mp4.
 *  One-prompt films also list their scenes with a per-scene re-shoot. */
export function AutopilotCard({ runId }: { runId: string }) {
  const [run, setRun] = useState<AutopilotRun | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [round, setRound] = useState(0)  // bumped after a re-shoot so polling starts again

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
  }, [runId, round])

  async function reshoot(index: number) {
    try {
      setError(null)
      setRun(await regenerateScene(runId, index))
      setRound(value => value + 1)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось переснять сцену.')
    }
  }

  if (!run) {
    return error
      ? <div role="alert" className="rounded-xl bg-bg-tertiary px-3 py-2 text-sm text-red-400">{error}</div>
      : <div className="rounded-xl bg-bg-tertiary px-3 py-2 text-sm text-text-muted">Запускаю автопилот…</div>
  }

  return (
    <section aria-label="Автопилот" className="max-w-[92%] space-y-2 rounded-xl bg-bg-tertiary px-3 py-2 text-sm text-text-primary">
      {run.script?.title && (
        <p className="text-[11px] text-text-muted">
          Сценарий: {run.script.title}{run.script.grade ? ` · оценка доктора ${run.script.grade}` : ''}
        </p>
      )}
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
      {error && <p role="alert" className="text-xs text-red-400">{error}</p>}
      {run.output && (
        <div className="space-y-1">
          <video key={run.output.url} src={run.output.url} controls playsInline className="max-h-80 w-full rounded-lg bg-black" />
          <a href={run.output.url} download={run.output.filename} className="text-xs text-accent-blue underline">
            Скачать {run.output.filename}
          </a>
        </div>
      )}
      {run.status !== 'running' && run.scenes_detail && run.scenes_detail.length > 0 && (
        <details className="text-[11px]">
          <summary className="cursor-pointer text-text-muted">Сцены ({run.scenes_detail.length}) — переснять одну</summary>
          <ol className="mt-1 space-y-1">
            {run.scenes_detail.map(scene => (
              <li key={scene.index} className="flex items-start justify-between gap-2">
                <span className="text-text-secondary">
                  {scene.index}. {scene.voiceover || scene.prompt}{scene.product ? ' · реальное фото товара' : ''}
                </span>
                <button type="button" onClick={() => void reshoot(scene.index)}
                  className="shrink-0 rounded-md border border-border px-2 py-0.5 text-text-muted hover:bg-bg-hover hover:text-text-primary">
                  Переснять
                </button>
              </li>
            ))}
          </ol>
        </details>
      )}
    </section>
  )
}
