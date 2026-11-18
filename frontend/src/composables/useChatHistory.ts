import { onBeforeUnmount, readonly, shallowRef } from 'vue'
import type { ChatMessage, Conversation } from '@/components/chat/types'

export function useChatHistory(token: () => string, userId: () => number | null) {
  const conversations = shallowRef<Conversation[]>([])
  const loading = shallowRef(false)
  const error = shallowRef('')
  const loadingMessages = shallowRef(false)
  const messageError = shallowRef('')
  let listController: AbortController | null = null
  let messageController: AbortController | null = null
  let disposed = false
  const userQuery = () => `userId=${encodeURIComponent(String(userId() ?? ''))}`

  async function loadConversations() {
    listController?.abort()
    const controller = new AbortController()
    listController = controller
    loading.value = true
    error.value = ''
    try {
      const resp = await fetch(`/api/conversations?${userQuery()}`, { headers: { token: token() }, signal: controller.signal })
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const rows = await resp.json()
      if (!Array.isArray(rows)) throw new Error('历史数据格式异常')
      if (controller === listController && !disposed) conversations.value = rows
    } catch (cause) {
      if (controller === listController && !disposed && !controller.signal.aborted) error.value = `历史加载失败：${cause instanceof Error ? cause.message : '请稍后重试'}`
    } finally { if (controller === listController) loading.value = false }
  }

  async function loadMessages(id: string): Promise<ChatMessage[] | null> {
    messageController?.abort()
    const controller = new AbortController()
    messageController = controller
    loadingMessages.value = true
    messageError.value = ''
    try {
      const resp = await fetch(`/api/conversations/${encodeURIComponent(id)}/messages?${userQuery()}`, { headers: { token: token() }, signal: controller.signal })
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const rows = await resp.json()
      if (!Array.isArray(rows)) throw new Error('消息数据格式异常')
      if (messageController !== controller || disposed) return null
      return rows.map((r: any) => ({ id: crypto.randomUUID(), role: r.role === 'user' || r.role === 'me' ? 'me' : 'ai', text: String(r.content ?? ''), source: r.source, trace: r.trace, toolCalls: r.toolCalls }))
    } catch (cause) {
      if (messageController === controller && !disposed && !controller.signal.aborted) messageError.value = `对话加载失败：${cause instanceof Error ? cause.message : '请稍后重试'}`
      return null
    } finally { if (messageController === controller) loadingMessages.value = false }
  }

  function addConversation(id: string) {
    conversations.value = [{ sessionId: id, preview: '新对话' }, ...conversations.value.filter(c => c.sessionId !== id)]
    messageError.value = ''
  }
  onBeforeUnmount(() => { disposed = true; listController?.abort(); messageController?.abort() })
  return { conversations: readonly(conversations), loading: readonly(loading), error: readonly(error), loadingMessages: readonly(loadingMessages), messageError: readonly(messageError), loadConversations, loadMessages, addConversation }
}
