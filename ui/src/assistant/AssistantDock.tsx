import { useState } from 'react'
import { Sparkles } from 'lucide-react'
import { AssistantChat } from './AssistantChat'

export function AssistantDock() {
  const [open, setOpen] = useState(false)

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed bottom-4 right-4 z-40 flex items-center gap-2 rounded-full bg-toggle-active px-4 py-2 text-sm font-medium text-white shadow-lg hover:opacity-95"
        aria-label="Открыть помощника"
      >
        <Sparkles size={16} />
        Помощник
      </button>
    )
  }

  return (
    <div className="fixed inset-y-0 right-0 z-40 w-full max-w-md">
      <AssistantChat onClose={() => setOpen(false)} />
    </div>
  )
}
