import { useEffect } from 'react'

/**
 * Local registry with the same idea as CopilotKit's useFrontendTool:
 * the model names a tool, the handler runs in the browser, the result
 * goes back into the chat. Copied in spirit from
 * CopilotKit/examples/showcases/generative-ui and examples/v2.
 * Official package wiring can replace this file later without changing tool names.
 */

export type JsonSchema = {
  type: 'object'
  properties: Record<string, Record<string, unknown>>
  required?: string[]
  additionalProperties?: boolean
}

export type FrontendTool = {
  name: string
  description: string
  parameters: JsonSchema
  handler: (args: Record<string, unknown>) => Promise<unknown> | unknown
}

const tools = new Map<string, FrontendTool>()
const listeners = new Set<() => void>()

function notify() {
  for (const listener of listeners) listener()
}

export function listFrontendTools(): FrontendTool[] {
  return [...tools.values()]
}

export function frontendToolsAsOpenAI() {
  return listFrontendTools().map(tool => ({
    type: 'function' as const,
    function: {
      name: tool.name,
      description: tool.description,
      parameters: tool.parameters,
    },
  }))
}

export async function callFrontendTool(name: string, args: Record<string, unknown>) {
  const tool = tools.get(name)
  if (!tool) {
    return { ok: false, error: `Инструмент ${name} не найден.` }
  }
  try {
    const result = await tool.handler(args || {})
    return result ?? { ok: true }
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Не получилось выполнить действие.'
    return { ok: false, error: message }
  }
}

export function useFrontendTool(tool: FrontendTool, deps: unknown[] = []) {
  useEffect(() => {
    tools.set(tool.name, tool)
    notify()
    return () => {
      const current = tools.get(tool.name)
      if (current === tool) tools.delete(tool.name)
      notify()
    }
    // Intentional: callers pass a stable tool identity plus deps, as in CopilotKit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
}
