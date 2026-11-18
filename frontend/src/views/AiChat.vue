<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, shallowRef, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ChatLineRound, Refresh, ArrowDown } from '@element-plus/icons-vue'
import AppNav from '@/components/AppNav.vue'
import ChatComposer from '@/components/chat/ChatComposer.vue'
import ChatHistoryPanel from '@/components/chat/ChatHistoryPanel.vue'
import ChatSources from '@/components/chat/ChatSources.vue'
import ChatDraft from '@/components/chat/ChatDraft.vue'
import type { ChatMessage, TurnState } from '@/components/chat/types'
import { useChatScroll } from '@/composables/useChatScroll'
import { useChatStream } from '@/composables/useChatStream'
import { useChatHistory } from '@/composables/useChatHistory'
import { useUserStore } from '@/store/user'
import { renderMdLite } from '@/utils/md'

const userStore = useUserStore()
const route = useRoute()
const sessionId = shallowRef(crypto.randomUUID().replace(/-/g, ''))
const text = shallowRef('')
const initializing = shallowRef(true)
const historyTarget = shallowRef('')
const historyOpen = shallowRef(false)
const GREETING = '你好，我是青莲。想读哪首诗，或聊哪句词，我都在。'
const greeting = (): ChatMessage => ({ id: crypto.randomUUID(), role: 'ai', text: GREETING })
const msgs = ref<ChatMessage[]>([greeting()])
const listRef = shallowRef<HTMLElement | null>(null)
const { showLatest, onScroll, contentChanged, jumpToLatest } = useChatScroll(listRef)
const history = useChatHistory(() => userStore.token, () => userStore.userId)
const { conversations, loading, error: historyError, loadingMessages, messageError } = history
const savedKey = () => `ql_session_${userStore.userId ?? 0}`
function updateSession(id: string) { sessionId.value = id; localStorage.setItem(savedKey(), id) }
const { pending, responseId, start, stop } = useChatStream({ token: () => userStore.token, session: () => sessionId.value, updateSession, contentChanged })
const historyBusy = computed(() => initializing.value || loadingMessages.value)
const currentResponse = computed(() => msgs.value.find(m => m.id === responseId.value))
const phaseLabels: Partial<Record<TurnState, string>> = { waiting: '正在等待青莲回复…', researching: '正在查阅资料与处理工具…', streaming: '正在接收回复…' }
const phaseText = computed(() => pending.value ? phaseLabels[currentResponse.value?.state || 'waiting'] || '正在处理本轮…' : '青莲 · 诗词助手')
const suggestions = ['怎样读懂一首诗的意象？', '聊聊李白诗里的月亮', '帮我起草一篇诗词赏析帖子']
const poemTitle = computed(() => String(route.query.poemTitle || ''))
const poemId = computed(() => String(route.query.poemId || ''))
const poemPrompt = computed(() => poemTitle.value ? `请赏析《${poemTitle.value}》${poemId.value ? `（诗词 ID：${poemId.value}）` : ''}，谈谈诗中的意象与情感。` : '')
watch(poemPrompt, prompt => { if (prompt && !text.value.trim()) text.value = prompt }, { immediate: true })
let alive = true

async function switchConversation(id: string) {
  if (pending.value || loadingMessages.value) return
  historyTarget.value = id
  const rows = await history.loadMessages(id)
  if (!rows || !alive) return
  msgs.value = rows.length ? rows : [greeting()]
  updateSession(id)
  await jumpToLatest()
}
function newConversation() {
  if (pending.value || historyBusy.value) return
  updateSession(crypto.randomUUID().replace(/-/g, ''))
  msgs.value = [greeting()]
  history.addConversation(sessionId.value)
  void jumpToLatest()
}
async function run(response: ChatMessage) {
  await start(response)
  if (alive) void history.loadConversations()
}
async function send() {
  const question = text.value.trim()
  if (!question || pending.value || historyBusy.value) return
  updateSession(sessionId.value)
  msgs.value.push({ id: crypto.randomUUID(), role: 'me', text: question })
  const response = reactive<ChatMessage>({ id: crypto.randomUUID(), role: 'ai', text: '', question, requestSessionId: sessionId.value })
  msgs.value.push(response)
  text.value = ''
  void jumpToLatest()
  await run(response)
}
function retry(response: ChatMessage) {
  if (pending.value || historyBusy.value || !response.question) return
  void jumpToLatest()
  void run(response)
}
function questionFor(message: ChatMessage) {
  if (message.question) return message.question
  const index = msgs.value.indexOf(message)
  for (let i = index - 1; i >= 0; i--) if (msgs.value[i].role === 'me') return msgs.value[i].text
  return ''
}
onMounted(async () => {
  await history.loadConversations()
  if (!alive) return
  const saved = localStorage.getItem(savedKey())
  const target = saved && conversations.value.some(c => c.sessionId === saved) ? saved : conversations.value[0]?.sessionId
  if (target) await switchConversation(target)
  if (alive) initializing.value = false
})
onBeforeUnmount(() => { alive = false })
</script>

<template>
  <div class="chat-page">
    <AppNav />
    <main class="wrap chat-wrap">
      <header class="page-head">
        <div><p class="page-kicker">和诗词多聊一会儿</p><h1 class="page-title">AI 诗友</h1><p class="page-subtitle">青莲陪你读诗、查资料，也能帮你起草诗坛帖子。</p></div>
        <div class="head-icon" aria-hidden="true"><ChatLineRound /></div>
      </header>
      <div class="ai-chat">
        <ChatHistoryPanel :conversations="conversations" :selected="sessionId" :loading="loading" :error="historyError"
          :disabled="pending || historyBusy" @new="newConversation" @select="switchConversation" @refresh="history.loadConversations" @modal-change="historyOpen = $event" />
        <section class="chat-main" aria-label="与青莲对话" :inert="historyOpen ? true : undefined">
          <div class="chat-toolbar"><span class="assistant-status"><span class="status-dot" aria-hidden="true" />{{ phaseText }}</span><span class="toolbar-note">{{ pending ? '可随时停止接收' : '回答请结合原诗核对' }}</span></div>
          <div v-if="loadingMessages" class="history-message-status" role="status">正在恢复对话…</div>
          <div v-if="messageError" class="history-message-error" role="alert">{{ messageError }}<button type="button" :disabled="pending || historyBusy" @click="switchConversation(historyTarget)">重试对话</button></div>
          <div ref="listRef" class="msg-list" aria-label="对话消息" tabindex="0" @scroll="onScroll">
            <article v-for="m in msgs" :key="m.id" :class="['msg', m.role]">
              <div class="msg-wrap">
                <div class="who">{{ m.role === 'me' ? '我' : '青莲' }}</div>
                <div class="bubble">
                  <div v-if="m.role === 'ai' && m.text" class="md" v-html="renderMdLite(m.text)" />
                  <div v-else-if="m.role === 'me'" class="user-text">{{ m.text }}</div>
                  <p v-else-if="m.state === 'waiting' || m.state === 'researching'" class="turn-waiting"><span class="waiting-dot" aria-hidden="true" />{{ phaseLabels[m.state] }}</p>
                  <span v-if="m.state === 'streaming' && pending" class="stream-cursor" aria-hidden="true" />
                  <ChatDraft v-if="m.draft" v-model="m.draft" :receiving="pending" />
                </div>
                <div v-if="m.state === 'failed'" class="turn-error" role="alert"><p>{{ m.error || '本轮回复失败，请重试' }}</p><button type="button" :disabled="pending || historyBusy" @click="retry(m)"><Refresh aria-hidden="true" />重试本轮</button></div>
                <p v-if="m.state === 'stopped'" class="turn-stopped" role="status">已停止接收，已收到的内容已保留。<button type="button" :disabled="pending || historyBusy" @click="retry(m)">重新生成</button></p>
                <ChatSources v-if="m.role === 'ai' && (m.source || m.trace || m.toolCalls?.length)" :message="m" :session-id="sessionId" :question="questionFor(m)" :token="userStore.token" />
              </div>
            </article>
            <div v-if="msgs.length === 1 && !pending" class="suggestions"><p class="suggestions-label">试着从这里开始</p><button v-for="prompt in suggestions" :key="prompt" type="button" class="suggestion" @click="text = prompt">{{ prompt }}</button></div>
          </div>
          <div class="latest-row"><button v-if="showLatest" type="button" class="jump-latest" @click="jumpToLatest"><ArrowDown aria-hidden="true" />查看最新回复</button></div>
          <p v-if="poemTitle && msgs.length === 1" class="poem-context">来自《{{ poemTitle }}》 · 提示草稿可编辑，发送后开始对话</p>
          <ChatComposer v-model="text" :generating="pending" :loading-history="historyBusy" @send="send" @stop="stop" />
          <span class="sr-only" role="status">{{ pending ? phaseText : currentResponse?.state === 'complete' ? '本轮回复已完成' : '' }}</span>
        </section>
      </div>
    </main>
  </div>
</template>

<style scoped>
.chat-wrap { max-width: 1320px; }
.page-head { display: flex; align-items: center; justify-content: space-between; gap: 24px; margin-bottom: 24px; }
.page-kicker { margin: 0 0 8px; font-size: 13px; color: var(--md-primary); font-weight: 500; }
.page-title { margin: 0; font-size: clamp(28px, 3vw, 36px); font-weight: 500; color: var(--md-on-surface); line-height: 1.3; }
.page-subtitle { margin: 12px 0 0; color: var(--md-on-surface-variant); font-size: 14px; line-height: 1.6; }
.head-icon { display: grid; place-items: center; flex: none; width: 64px; height: 64px; border-radius: 24px; color: var(--md-on-primary-container); background: var(--md-primary-container); }
.head-icon svg { width: 32px; height: 32px; }
.ai-chat { position: relative; display: flex; min-height: 560px; height: min(760px, calc(100dvh - 200px)); overflow: hidden; border: 1px solid var(--md-outline); border-radius: 24px; background: var(--md-surface); }
.chat-main { display: flex; flex-direction: column; flex: 1; min-width: 0; min-height: 0; }
.chat-toolbar { min-height: 64px; padding: 12px 24px; display: flex; justify-content: space-between; align-items: center; gap: 12px; border-bottom: 1px solid var(--md-outline); }
.assistant-status { display: inline-flex; align-items: center; gap: 8px; color: var(--md-on-surface); font-size: 13px; font-weight: 500; }
.status-dot { width: 7px; height: 7px; background: var(--md-primary); border-radius: 50%; }
.toolbar-note { font-size: 12px; color: var(--md-on-surface-variant); }
.msg-list { flex: 1; min-height: 0; overflow-y: auto; overscroll-behavior: contain; padding: 24px; }
.msg-list:focus-visible { outline: 2px solid var(--md-primary); outline-offset: -2px; }
.msg { display: flex; margin-bottom: 24px; }
.msg.me { justify-content: flex-end; }
.msg-wrap { min-width: 0; width: fit-content; max-width: 90%; }
.msg.me .msg-wrap { max-width: 80%; }
.who { color: var(--md-on-surface-variant); font-size: 12px; font-weight: 500; margin-bottom: 8px; }
.msg.me .who { text-align: right; }
.bubble { font-size: 15px; line-height: 1.8; color: var(--md-on-surface); overflow-wrap: anywhere; }
.msg.me .bubble { padding: 12px 18px; border-radius: 20px 20px 4px 20px; background: var(--md-primary-container); color: var(--md-on-primary-container); }
.user-text { white-space: pre-wrap; }
.turn-waiting { display: flex; align-items: center; gap: 8px; margin: 0; color: var(--md-on-surface-variant); font-size: 14px; }
.waiting-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--md-primary); animation: breathe 1.2s infinite; }
.stream-cursor { display: inline-block; width: 3px; height: 16px; margin-left: 4px; background: var(--md-primary); animation: breathe 1s infinite; }
@keyframes breathe { 50% { opacity: .3; } }
.md :deep(p) { margin: 0 0 10px; }
.md :deep(p:last-child) { margin-bottom: 0; }
.md :deep(strong) { font-weight: 600; color: var(--md-on-surface); }
.md :deep(em) { color: var(--md-on-surface-variant); }
.md :deep(code) { padding: 2px 5px; border-radius: 6px; background: var(--md-surface-container); font-family: ui-monospace, Consolas, monospace; font-size: 13px; }
.md :deep(.md-h) { margin: 20px 0 8px; font-size: 17px; font-weight: 500; color: var(--md-on-surface); }
.md :deep(.md-ul), .md :deep(.md-ol) { padding-left: 24px; margin: 8px 0; }
.md :deep(li) { margin: 4px 0; }
.md :deep(.md-quote) { border-left: 3px solid var(--md-primary); padding: 8px 16px; margin: 12px 0; background: var(--md-surface-container); }
.turn-error, .history-message-error { border: 1px solid var(--md-error); border-radius: 16px; padding: 12px 16px; color: var(--md-error); font-size: 13px; line-height: 1.6; margin-top: 12px; }
.turn-error p { margin: 0; }
.turn-error button, .turn-stopped button, .history-message-error button { display: inline-flex; align-items: center; gap: 6px; min-height: 44px; background: transparent; color: var(--md-primary); font: inherit; border: 0; border-radius: 999px; padding: 0 12px; cursor: pointer; }
.turn-error svg { width: 16px; height: 16px; }
.turn-error button:disabled, .turn-stopped button:disabled, .history-message-error button:disabled { opacity: .5; cursor: default; }
.turn-stopped { color: var(--md-on-surface-variant); font-size: 12px; line-height: 1.6; margin: 8px 0; }
.history-message-status { color: var(--md-on-surface-variant); font-size: 13px; padding: 12px 24px; }
.history-message-error { margin: 12px 20px 0; }
.suggestions { margin: 24px 0 0; display: flex; flex-wrap: wrap; gap: 8px; }
.suggestions-label { flex-basis: 100%; color: var(--md-on-surface-variant); margin: 0 0 4px; font-size: 12px; }
.suggestion { min-height: 44px; border: 1px solid var(--md-outline); background: var(--md-surface-container); color: var(--md-on-surface); border-radius: 16px; padding: 10px 14px; font: inherit; font-size: 13px; text-align: left; cursor: pointer; }
.suggestion:hover { background: var(--md-primary-container); color: var(--md-on-primary-container); }
.latest-row { position: relative; height: 12px; flex: none; }
.jump-latest { position: absolute; z-index: 2; left: 50%; bottom: 8px; transform: translateX(-50%); display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; padding: 0 16px; min-height: 44px; border: 1px solid var(--md-outline); border-radius: 999px; background: var(--md-primary-container); color: var(--md-on-primary-container); font: inherit; font-size: 13px; cursor: pointer; box-shadow: 0 2px 8px rgb(0 0 0 / .1); }
.jump-latest svg { width: 16px; height: 16px; }
.poem-context { color: var(--md-on-surface-variant); margin: 0 24px 8px; font-size: 12px; line-height: 1.5; }
.suggestion:focus-visible, .jump-latest:focus-visible, .turn-error button:focus-visible, .turn-stopped button:focus-visible, .history-message-error button:focus-visible { outline: 3px solid var(--md-primary); outline-offset: 2px; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
@media (max-width: 980px) { .ai-chat { min-height: 620px; height: min(820px, calc(100dvh - 190px)); } .chat-toolbar { padding-top: 64px; min-height: 112px; } }
@media (max-width: 600px) {
  .page-head { margin-bottom: 20px; } .head-icon { width: 48px; height: 48px; border-radius: 16px; } .head-icon svg { width: 24px; height: 24px; }
  .page-subtitle { font-size: 13px; } .ai-chat { min-height: 520px; height: calc(100dvh - 220px); border-radius: 20px; }
  .chat-toolbar { padding-left: 16px; padding-right: 16px; } .toolbar-note { display: none; } .msg-list { padding: 20px 16px; }
  .msg-wrap { max-width: 100%; } .msg.me .msg-wrap { max-width: 90%; } .bubble { font-size: 14px; } .poem-context { margin-left: 16px; margin-right: 16px; }
}
@media (prefers-reduced-motion: reduce) { .waiting-dot, .stream-cursor { animation: none; } }
</style>
