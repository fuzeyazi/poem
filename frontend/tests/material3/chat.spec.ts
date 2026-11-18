import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import AiChat from '@/views/AiChat.vue'
import { useUserStore } from '@/store/user'

vi.mock('@/components/AppNav.vue', () => ({ default: { template: '<nav />' } }))
vi.mock('@/api/forum', () => ({ postBlog: vi.fn().mockResolvedValue({}) }))

type RequestRecord = { url: string; init?: RequestInit }
let requests: RequestRecord[]
let workflowResponses: Response[]
let historyResponse: Response
let feedbackResponse: Response
const wrappers: VueWrapper[] = []
const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })
function stream() {
  let controller!: ReadableStreamDefaultController<Uint8Array>
  const body = new ReadableStream<Uint8Array>({ start(value) { controller = value } })
  return {
    response: new Response(body),
    event(event: string, data: unknown) { controller.enqueue(new TextEncoder().encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`)) },
    close() { controller.close() },
  }
}
async function page(query = '') {
  const pinia = createPinia()
  setActivePinia(pinia)
  useUserStore().setLogin('chat-token', 7, '读诗人')
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/ai', component: AiChat }, { path: '/forum', component: { template: '<div />' } }] })
  await router.push(`/ai${query}`)
  await router.isReady()
  const wrapper = mount(AiChat, { attachTo: document.body, global: { plugins: [pinia, router], stubs: { 'el-input': true, 'el-tag': true, 'el-button': true } } })
  wrappers.push(wrapper)
  await flushPromises()
  return wrapper
}
const workflowCalls = () => requests.filter(r => r.url === '/agent/workflow')
const input = (w: VueWrapper) => w.find('textarea[aria-label="给青莲的消息"], .input-bar input')
const button = (w: VueWrapper, name: string) => w.findAll('button').find(b => b.text().replace(/\s/g, '').includes(name.replace(/\s/g, '')))!
async function send(w: VueWrapper, message = '解释静夜思') {
  await input(w).setValue(message)
  await button(w, '发送').trigger('click')
  await flushPromises()
}

beforeEach(() => {
  localStorage.clear()
  requests = []
  workflowResponses = []
  historyResponse = json([])
  feedbackResponse = json({ ok: true })
  vi.stubGlobal('fetch', async (url: string, init?: RequestInit) => {
    requests.push({ url: String(url), init })
    if (url === '/agent/workflow') return workflowResponses.shift() ?? json({}, 503)
    if (String(url).startsWith('/agent/feedback')) return feedbackResponse.clone()
    if (String(url).includes('/messages?')) return json([{ role: 'user', content: '旧问题' }, { role: 'assistant', content: '**旧回答**' }])
    return historyResponse.clone()
  })
})
afterEach(() => {
  wrappers.splice(0).forEach(w => w.unmount())
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

describe('Material 3 chat', () => {
  it('creates an editable poem prompt without submitting it', async () => {
    const w = await page('?poemTitle=静夜思&poemId=12')
    expect(input(w).exists()).toBe(true)
    expect((input(w).element as HTMLTextAreaElement).value).toContain('静夜思')
    await input(w).setValue('我想讨论这首诗的乡愁')
    expect(workflowCalls()).toHaveLength(0)
  })

  it('submits plain Enter but keeps Shift+Enter and Chinese composition in the draft', async () => {
    const pending = stream(); workflowResponses.push(pending.response)
    const w = await page()
    expect(input(w).exists()).toBe(true)
    await input(w).setValue('月光')
    await input(w).trigger('keydown', { key: 'Enter', shiftKey: true })
    await input(w).trigger('compositionstart')
    await input(w).trigger('keydown', { key: 'Enter', isComposing: false })
    await input(w).trigger('compositionend')
    await input(w).trigger('keydown', { key: 'Enter', isComposing: true })
    await input(w).trigger('keydown', { key: 'Enter', keyCode: 229 })
    expect(workflowCalls()).toHaveLength(0)
    await input(w).trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(workflowCalls()).toHaveLength(1)
    expect(JSON.parse(workflowCalls()[0].init!.body as string).message).toBe('月光')
    pending.event('done', { source: 'llm' }); pending.close()
  })

  it('stops browser reception, preserves partial output and the editable next draft', async () => {
    const pending = stream(); workflowResponses.push(pending.response)
    const w = await page()
    expect(input(w).exists()).toBe(true)
    await send(w)
    pending.event('token', { content: '床前明月光' }); await flushPromises()
    expect(input(w).attributes('disabled')).toBeUndefined()
    await input(w).setValue('下一条\n草稿')
    const signal = workflowCalls()[0].init!.signal!
    await button(w, '停止接收').trigger('click'); await flushPromises()
    expect(signal.aborted).toBe(true)
    expect(w.text()).toContain('床前明月光')
    expect(w.text()).toContain('已停止接收')
    expect((input(w).element as HTMLTextAreaElement).value).toBe('下一条\n草稿')
    expect(button(w, '发送').attributes('disabled')).toBeUndefined()
  })

  it('retries a failed turn without duplicating its user message and keeps the session header contract', async () => {
    workflowResponses.push(json({}, 503))
    const w = await page()
    expect(input(w).exists()).toBe(true)
    await send(w)
    expect(w.find('[role="alert"]').text()).toContain('503')
    const retry = stream(); workflowResponses.push(retry.response)
    await button(w, '重试本轮').trigger('click'); await flushPromises()
    retry.event('token', { content: '成功回答' }); retry.event('done', { source: 'llm' }); retry.close(); await flushPromises()
    expect(w.findAll('.msg.me')).toHaveLength(1)
    expect(w.text()).toContain('成功回答')
    const first = workflowCalls()[0].init!
    const second = workflowCalls()[1].init!
    expect(first.headers).toMatchObject({ token: 'chat-token', 'Content-Type': 'application/json' })
    expect(JSON.parse(second.body as string)).toEqual(JSON.parse(first.body as string))
  })

  it('shows the active phases when retrying an earlier failed turn after a later completed turn', async () => {
    workflowResponses.push(json({}, 503))
    const w = await page(); await send(w, '第一条问题')
    const later = stream(); workflowResponses.push(later.response)
    await send(w, '第二条问题')
    later.event('token', { content: '第二条的回答' }); later.event('done', { source: 'llm' }); later.close(); await flushPromises()
    const retried = stream(); workflowResponses.push(retried.response)
    await button(w, '重试本轮').trigger('click'); await flushPromises()
    expect(w.find('.assistant-status').text()).toContain('正在等待青莲回复')
    retried.event('tool_status', { tool: 'query_poem', status: 'calling', args: { title: '静夜思' } }); await flushPromises()
    expect(w.find('.assistant-status').text()).toContain('正在查阅资料与处理工具')
    retried.event('token', { content: '第一条重试的回答' }); await flushPromises()
    expect(w.find('.assistant-status').text()).toContain('正在接收回复')
    retried.event('done', { source: 'tool' }); retried.close(); await flushPromises()
    expect(w.text()).toContain('第二条的回答')
    expect(w.text()).toContain('第一条重试的回答')
    expect(w.findAll('.msg.me')).toHaveLength(2)
    expect(JSON.parse(workflowCalls()[2].init!.body as string)).toEqual(JSON.parse(workflowCalls()[0].init!.body as string))
  })

  it('keeps SSE error evidence even when the stream later sends done', async () => {
    const pending = stream(); workflowResponses.push(pending.response)
    const w = await page(); expect(input(w).exists()).toBe(true); await send(w)
    pending.event('token', { content: '部分回答' })
    pending.event('error', { message: '检索服务暂不可用' })
    pending.event('done', { source: 'fallback' }); pending.close(); await flushPromises()
    expect(w.find('[role="alert"]').text()).toContain('检索服务暂不可用')
    expect(w.text()).toContain('部分回答')
    expect(button(w, '重试本轮')).toBeDefined()
  })

  it('keeps an SSE failure visible when the user stops the remaining connection', async () => {
    const pending = stream(); workflowResponses.push(pending.response)
    const w = await page(); await send(w)
    pending.event('error', { message: '本轮工具调用失败' }); await flushPromises()
    await button(w, '停止接收').trigger('click'); await flushPromises()
    expect(w.find('.turn-error').exists()).toBe(true)
    expect(w.text()).toContain('本轮工具调用失败')
  })

  it('marks an interrupted stream as failed instead of claiming completion', async () => {
    const pending = stream(); workflowResponses.push(pending.response)
    const w = await page(); expect(input(w).exists()).toBe(true); await send(w)
    pending.event('token', { content: '未完成回答' }); pending.close(); await flushPromises()
    expect(w.find('[role="alert"]').exists()).toBe(true)
    expect(w.text()).toContain('未完成回答')
  })

  it('renders meta, trace, tool_status, action and done with keyboard source disclosure and editable forum draft', async () => {
    const pending = stream(); workflowResponses.push(pending.response)
    const w = await page(); expect(input(w).exists()).toBe(true); await send(w)
    pending.event('meta', { sessionId: 'server-session' })
    pending.event('trace', { route: 'knowledge', intent: '赏析', gate: 'pass', score: 0.9, retrievedCount: 2, iters: 1 })
    pending.event('tool_status', { tool: 'query_poem', status: 'calling', args: { title: '静夜思' } })
    pending.event('tool_status', { tool: 'query_poem', status: 'done', durationMs: 28 })
    pending.event('token', { content: '<img src=x onerror=alert(1)> **赏析**' })
    pending.event('action', { action: 'forum_draft', draft: { title: '月光与故乡', content: '初稿', tag: '诗词赏析' } })
    pending.event('done', { source: 'tool' }); pending.close(); await flushPromises()
    expect(w.find('.md img').exists()).toBe(false)
    expect(w.find('.md strong').text()).toBe('赏析')
    expect(localStorage.getItem('ql_session_7')).toBe('server-session')
    const source = button(w, '来源：')
    expect(source.attributes('aria-expanded')).toBe('false')
    await source.trigger('click')
    expect(source.attributes('aria-expanded')).toBe('true')
    expect(w.text()).toContain('查诗词')
    expect(w.text()).toContain('28ms')
    await w.find('input[aria-label="帖子标题"]').setValue('编辑后的标题')
    await w.find('textarea[aria-label="帖子正文"]').setValue('编辑后的正文')
    await button(w, '发布到诗坛').trigger('click'); await flushPromises()
    const { postBlog } = await import('@/api/forum')
    expect(postBlog).toHaveBeenCalledWith({ title: '编辑后的标题', content: '编辑后的正文', type: '诗词赏析' })
  })

  it('confirms feedback only after HTTP success and allows a failed submission to retry', async () => {
    const pending = stream(); workflowResponses.push(pending.response)
    const w = await page(); expect(input(w).exists()).toBe(true); await send(w)
    pending.event('token', { content: '回答' }); pending.event('done', { source: 'llm' }); pending.close(); await flushPromises()
    feedbackResponse = json({}, 500)
    await w.find('button[aria-label="这条回答有帮助"]').trigger('click'); await flushPromises()
    expect(w.text()).not.toContain('已反馈，感谢')
    expect(w.text()).toContain('反馈提交失败')
    feedbackResponse = json({ ok: true })
    await w.find('button[aria-label="这条回答有帮助"]').trigger('click'); await flushPromises()
    expect(w.text()).toContain('已反馈，感谢')
    await w.find('button[aria-label="这条回答需要改进"]').trigger('click'); await flushPromises()
    const negative = requests.find(r => r.url === '/agent/feedback/negative')!
    expect(negative.init!.headers).toMatchObject({ token: 'chat-token' })
    expect(JSON.parse(negative.init!.body as string)).toMatchObject({ message: '解释静夜思', rating: 'down' })
  })

  it('exposes history errors with retry and switches via a native selected button', async () => {
    historyResponse = json({}, 503)
    const w = await page()
    expect(w.text()).toContain('历史加载失败')
    historyResponse = json([{ sessionId: 'old-id', preview: '旧对话', updatedAt: '今天', summarized: true }])
    await button(w, '重试历史').trigger('click'); await flushPromises()
    const row = button(w, '旧对话')
    expect(row.element.tagName).toBe('BUTTON')
    await row.trigger('click'); await flushPromises()
    expect(row.attributes('aria-pressed')).toBe('true')
    expect(w.find('.msg.me').text()).toContain('旧问题')
    expect(w.find('.md strong').text()).toBe('旧回答')
    expect(localStorage.getItem('ql_session_7')).toBe('old-id')
  })

  it('does not pull old-message readers to the bottom and lets them jump to latest output', async () => {
    const pending = stream(); workflowResponses.push(pending.response)
    const w = await page(); expect(input(w).exists()).toBe(true); await send(w)
    const list = w.find('[aria-label="对话消息"]')
    const el = list.element as HTMLElement
    Object.defineProperties(el, { scrollHeight: { configurable: true, value: 1200 }, clientHeight: { configurable: true, value: 400 } })
    el.scrollTop = 200; await list.trigger('scroll')
    pending.event('token', { content: '新文字' }); await flushPromises()
    expect(el.scrollTop).toBe(200)
    await button(w, '查看最新回复').trigger('click'); await flushPromises()
    expect(el.scrollTop).toBe(1200)
    expect(button(w, '查看最新回复')).toBeUndefined()
    pending.event('done', { source: 'llm' }); pending.close()
  })

  it('makes the history drawer modal, traps keyboard focus and restores its trigger on Escape', async () => {
    const w = await page()
    const trigger = w.find('button[aria-controls="chat-history"]')
    await trigger.trigger('click'); await flushPromises()
    const drawer = w.find('[role="dialog"][aria-modal="true"]')
    expect(drawer.exists()).toBe(true)
    expect(w.find('[aria-label="与青莲对话"]').attributes('inert')).toBeDefined()
    expect(document.activeElement?.getAttribute('aria-label')).toBe('关闭历史对话')
    await drawer.find('button[aria-label="关闭历史对话"]').trigger('keydown', { key: 'Tab', shiftKey: true })
    expect(document.activeElement?.textContent).toContain('新对话')
    await drawer.trigger('keydown', { key: 'Escape' })
    expect(w.find('[role="dialog"]').exists()).toBe(false)
    expect(w.find('[aria-label="与青莲对话"]').attributes('inert')).toBeUndefined()
    expect(document.activeElement).toBe(trigger.element)
  })

  it('does not present a previous attempt forum draft as output of a retry', async () => {
    const pending = stream(); workflowResponses.push(pending.response)
    const w = await page(); await send(w)
    pending.event('action', { action: 'forum_draft', draft: { title: '旧草稿', content: '旧正文' } })
    pending.event('error', { message: '本轮中断' }); pending.close(); await flushPromises()
    expect(w.find('input[aria-label="帖子标题"]').exists()).toBe(true)
    const next = stream(); workflowResponses.push(next.response)
    await button(w, '重试本轮').trigger('click'); await flushPromises()
    next.event('token', { content: '这次只做赏析' }); next.event('done', { source: 'llm' }); next.close(); await flushPromises()
    expect(w.find('input[aria-label="帖子标题"]').exists()).toBe(false)
  })

  it('decodes split UTF-8 and CRLF SSE frames including a final frame without a blank line', async () => {
    const bytes = new TextEncoder().encode('event: token\r\ndata: {"content":"明月"}\r\n\r\nevent: done\r\ndata: {"source":"llm"}')
    let controller!: ReadableStreamDefaultController<Uint8Array>
    workflowResponses.push(new Response(new ReadableStream({ start(c) { controller = c } })))
    const w = await page(); await send(w)
    // Single-byte chunks cross both Chinese code point boundaries and CRLF separators.
    for (const byte of bytes) controller.enqueue(new Uint8Array([byte]))
    controller.close(); await flushPromises()
    expect(w.text()).toContain('明月')
    expect(w.find('.turn-error').exists()).toBe(false)
    expect(button(w, '停止接收')).toBeUndefined()
  })

  it('ignores a delayed response from a stopped request while a new turn is receiving', async () => {
    let resolveFirst!: (response: Response) => void
    const delayed = new Promise<Response>(resolve => { resolveFirst = resolve })
    const newer = stream()
    let count = 0
    vi.stubGlobal('fetch', async (url: string, init?: RequestInit) => {
      requests.push({ url: String(url), init })
      return url === '/agent/workflow' ? (++count === 1 ? delayed : newer.response) : json([])
    })
    const w = await page(); await send(w, '第一条')
    await button(w, '停止接收').trigger('click'); await flushPromises()
    await send(w, '第二条')
    const older = stream()
    older.event('token', { content: '过时回复' }); older.event('done', { source: 'llm' }); older.close()
    resolveFirst(older.response); await flushPromises()
    expect(w.text()).not.toContain('过时回复')
    expect(button(w, '停止接收')).toBeDefined()
    newer.event('token', { content: '第二条的回答' }); newer.event('done', { source: 'llm' }); newer.close(); await flushPromises()
    expect(w.text()).toContain('第二条的回答')
    expect(w.findAll('.msg.me')).toHaveLength(2)
    expect(w.text()).toContain('已停止接收')
  })
})
