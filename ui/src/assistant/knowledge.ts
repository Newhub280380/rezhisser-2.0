import { useEffect, useState } from 'react'

/** Knowledge base lives in docs/assistant-knowledge; the server serves it at /api/v1/assistant/knowledge. */

export type AssistantCategory = string

export type KnowledgeCategory = {
  id: string
  title: string
  short: string
  steps: string[]
  progress_labels: string[]
  prompt_template: string
  autopilot: boolean
}

export type SlashCommand = {
  command: string
  title: string
  result?: string | null
  fields?: string[] | null
  templates?: string[] | null
  substitute?: string | null
}

export type Knowledge = { categories: KnowledgeCategory[]; commands: SlashCommand[] }

export type KnowledgePreset = {
  id: string
  title: string
  screen: 'director' | 'studio' | 'editor'
  defaultParams: Record<string, string | number>
  promptTemplate: string
}

let cache: Knowledge | null = null
let pending: Promise<Knowledge> | null = null

export function loadKnowledge(): Promise<Knowledge> {
  if (cache) return Promise.resolve(cache)
  pending ??= fetch('/api/v1/assistant/knowledge')
    .then(async response => {
      if (!response.ok) throw new Error(`knowledge ${response.status}`)
      const data = (await response.json()) as Knowledge
      cache = { categories: data.categories || [], commands: data.commands || [] }
      return cache
    })
    .catch(error => {
      pending = null
      throw error
    })
  return pending
}

export function useKnowledge(): Knowledge | null {
  const [knowledge, setKnowledge] = useState<Knowledge | null>(cache)
  useEffect(() => {
    let alive = true
    loadKnowledge().then(data => { if (alive) setKnowledge(data) }).catch(() => {})
    return () => { alive = false }
  }, [])
  return knowledge
}

/** Recipe as the set_params tool needs it: a prompt template plus draft defaults (rules.md: 5 s, 480p first). */
export function findPreset(id?: string | null): KnowledgePreset | undefined {
  const category = cache?.categories.find(item => item.id === id)
  if (!category) return undefined
  return {
    id: category.id,
    title: category.title,
    screen: category.id === 'text_to_video' ? 'director' : 'studio',
    defaultParams: { duration_seconds: 5, resolution: '480p' },
    promptTemplate: category.prompt_template || '{scene}',
  }
}

export function matchCommands(draft: string, commands: SlashCommand[]): SlashCommand[] {
  const typed = draft.trimStart()
  if (!typed.startsWith('/') || /\s/.test(typed)) return []
  const query = typed.toLowerCase()
  return commands.filter(command => command.command.toLowerCase().startsWith(query)).slice(0, 8)
}
