export type TurnState = 'waiting' | 'researching' | 'streaming' | 'complete' | 'stopped' | 'failed'
export interface ToolCall { tool: string; args?: unknown; status?: string; durationMs?: number | null }
export interface ChatDraft { title: string; content: string; tag?: string }
export interface ChatMessage {
  id: string
  role: 'me' | 'ai'
  text: string
  question?: string
  requestSessionId?: string
  state?: TurnState
  error?: string
  source?: string
  toolCalls?: ToolCall[]
  trace?: Record<string, any>
  draft?: ChatDraft
}
export interface Conversation { sessionId: string; preview?: string; updatedAt?: string; summarized?: boolean }
