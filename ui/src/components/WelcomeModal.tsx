import { useState } from 'react'
import { Sparkles, Cloud, Wand2, ShieldAlert, X } from 'lucide-react'

const SEEN_KEY = 'maestro_welcome_seen_v2'

/**
 * WelcomeModal — a one-time first-run intro. Sets the expectations that
 * most surprise new users (model weights download on first use, not at
 * install; Director is planned by a local LLM; mature mode is an opt-in
 * in Settings). Shown once ever, tracked in localStorage.
 *
 * Deliberately not tied to any backend call — it's pure orientation, so
 * it can render instantly on first paint.
 */
export function WelcomeModal() {
  const [open, setOpen] = useState(() => localStorage.getItem(SEEN_KEY) !== '1')

  if (!open) return null

  const dismiss = () => {
    localStorage.setItem(SEEN_KEY, '1')
    setOpen(false)
  }

  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/60 p-4" onClick={dismiss}>
      <div
        className="bg-bg-secondary border border-border rounded-2xl shadow-2xl w-[520px] max-w-[94vw] max-h-[88vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 pt-6 pb-4 flex items-start gap-3">
          <div className="w-11 h-11 rounded-xl bg-accent-blue/15 flex items-center justify-center shrink-0">
            <Sparkles size={22} className="text-accent-blue" />
          </div>
          <div className="flex-1">
            <h2 className="text-base font-semibold text-text-primary">Добро пожаловать в Режиссёр 2.0</h2>
            <p className="text-xs text-text-muted mt-0.5">
              Студия видео, картинок и музыки. Режим «Режиссёр» по одной фразе
              продумывает целый клип или короткий фильм.
            </p>
          </div>
          <button onClick={dismiss} className="p-1 rounded text-text-muted hover:text-text-primary" aria-label="Закрыть">
            <X size={16} />
          </button>
        </div>

        {/* Points */}
        <div className="px-6 pb-2 space-y-3.5">
          <Row icon={<Cloud size={16} className="text-accent-blue" />} title="Видео делается в облаке (Wan 2.2)">
            Ролики генерируются через облако fal на модели Wan 2.2 — по умолчанию
            по <span className="text-text-secondary">5 секунд</span>, это дешевле всего. Ключ облака
            вписывается один раз: Settings → Integrations → Cloud.
          </Row>
          <Row icon={<Wand2 size={16} className="text-accent-blue" />} title="Режиссёр и помощник">
            Опишите идею одной фразой — Режиссёр разложит её на сцены, а помощник
            ответит на вопросы. Для этого нужен облачный ключ текстовой модели (там же, в настройках).
          </Row>
          <Row icon={<ShieldAlert size={16} className="text-red-400" />} title="Взрослый режим выключен">
            Откровенный контент включается только вручную, с предупреждением,
            в Settings → Services. Если не включать, всё остаётся в рамках 16+.
          </Row>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 flex items-center justify-end gap-3">
          <button
            onClick={dismiss}
            className="px-5 py-2 text-xs bg-accent-blue text-white rounded-lg hover:bg-accent-blue-hover transition-colors font-medium"
          >
            Начать
          </button>
        </div>
      </div>
    </div>
  )
}

function Row({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3">
      <div className="w-8 h-8 rounded-lg bg-bg-tertiary/60 flex items-center justify-center shrink-0 mt-0.5">
        {icon}
      </div>
      <div className="flex-1">
        <div className="text-xs font-medium text-text-primary">{title}</div>
        <div className="text-[11px] text-text-muted mt-0.5 leading-relaxed">{children}</div>
      </div>
    </div>
  )
}
