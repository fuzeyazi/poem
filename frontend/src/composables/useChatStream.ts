import { onBeforeUnmount, readonly, shallowRef } from 'vue'
import type { ChatMessage, ToolCall } from '@/components/chat/types'

interface StreamOptions {
  token: () => string
  session: () => string
  updateSession: (id: string) => void
  contentChanged: () => void
}
interface ActiveRequest {
  controller: AbortController
  reader?: ReadableStreamDefaultReader<Uint8Array>
  response: ChatMessage
}

export function useChatStream(options: StreamOptions) {
  const pending = shallowRef(false)
  const responseId = shallowRef<string | null>(null)
  let active: ActiveRequest | null = null
  let disposed = false

  function stop() {
    if (!active) return
    const run = active
    run.response.state = run.response.error ? 'failed' : 'stopped'
    run.controller.abort()
    void run.reader?.cancel().catch(() => {})
    active = null
    pending.value = false
  }

  async function start(response: ChatMessage) {
    if (pending.value || disposed || !response.question) return
    const run: ActiveRequest = { controller: new AbortController(), response }
    active = run
    responseId.value = response.id
    pending.value = true
    response.text = ''
    response.state = 'waiting'
    response.error = undefined
    response.source = undefined
    response.draft = undefined
    response.trace = undefined
    response.toolCalls = []
    response.requestSessionId ||= options.session()
    let completed = false

    function handleBlock(block: string) {
      let event = 'message'
      const dataLines: string[] = []
      for (const line of block.split(/\r?\n/)) {
        if (line.startsWith('data:')) dataLines.push(line.slice(5).replace(/^ /, ''))
        else if (line.startsWith('event:')) event = line.slice(6).trim()
      }
      if (!dataLines.length) return
      let data: Record<string, any>
      try { data = JSON.parse(dataLines.join('\n')) } catch { throw new Error('回复数据无法解析，请重试本轮') }
      if (!data || typeof data !== 'object') return
      if (event === 'meta' && typeof data.sessionId === 'string') {
        response.requestSessionId = data.sessionId
        options.updateSession(data.sessionId)
      } else if (event === 'token') {
        response.text += String(data.content ?? '')
        if (!response.error) response.state = 'streaming'
      } else if (event === 'tool_status') {
        const existing = response.toolCalls!.find(c => c.tool === data.tool)
        if (existing) Object.assign(existing, data)
        else response.toolCalls!.push(data as ToolCall)
        if (!response.text && !response.error) response.state = 'researching'
      } else if (event === 'trace') {
        response.trace = data
        if (!response.text && !response.error) response.state = 'researching'
      } else if (event === 'action' && data.action === 'forum_draft' && data.draft) {
        response.draft = { title: String(data.draft.title ?? ''), content: String(data.draft.content ?? ''), tag: data.draft.tag }
        if (!response.text) response.text = '我起草了一篇帖子，请审阅：'
      } else if (event === 'error') {
        response.error = String(data.message || 'Agent 处理失败，请重试本轮')
        response.state = 'failed'
      } else if (event === 'done') {
        completed = true
        response.source = data.source
        response.state = response.error ? 'failed' : 'complete'
      }
      options.contentChanged()
    }

    try {
      const resp = await fetch('/agent/workflow', {
        method: 'POST',
        headers: { token: options.token(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ sessionId: response.requestSessionId, message: response.question }),
        signal: run.controller.signal,
      })
      if (active !== run) { void resp.body?.cancel().catch(() => {}); return }
      if (!resp.ok || !resp.body) throw new Error(`服务请求失败（HTTP ${resp.status}），请重试本轮`)
      run.reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (active === run && !completed) {
        const { done, value } = await run.reader.read()
        if (active !== run) break
        buffer += done ? decoder.decode() : decoder.decode(value, { stream: true })
        let separator: RegExpMatchArray | null
        while ((separator = buffer.match(/\r?\n\r?\n/))) {
          const index = separator.index!
          handleBlock(buffer.slice(0, index))
          buffer = buffer.slice(index + separator[0].length)
          if (completed) break
        }
        if (done) {
          if (buffer.trim() && !completed) handleBlock(buffer)
          break
        }
      }
      if (active === run && !completed && !response.error) throw new Error('连接已中断，回复尚未完成，请重试本轮')
    } catch (cause) {
      if (active === run && !disposed) {
        response.error ||= cause instanceof Error ? cause.message : '接收失败，请重试本轮'
        response.state = 'failed'
      }
    } finally {
      if (run.reader) {
        try { await run.reader.cancel() } catch { /* The transport may already be closed. */ }
        run.reader.releaseLock()
      }
      if (active === run) {
        active = null
        pending.value = false
        options.contentChanged()
      }
    }
  }

  onBeforeUnmount(() => { disposed = true; stop() })
  return { pending: readonly(pending), responseId: readonly(responseId), start, stop }
}
