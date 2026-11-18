<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, shallowRef } from 'vue'
import { Clock, Close, Plus } from '@element-plus/icons-vue'
import type { Conversation } from './types'

defineProps<{ conversations: readonly Conversation[]; selected: string; loading: boolean; error: string; disabled: boolean }>()
const emit = defineEmits<{ select: [id: string]; refresh: []; new: []; modalChange: [open: boolean] }>()
const open = shallowRef(false)
const panel = shallowRef<HTMLElement | null>(null)
const trigger = shallowRef<HTMLButtonElement | null>(null)
let previousOverflow = ''
let desktop: MediaQueryList | null = null
function close() {
  if (!open.value) return
  open.value = false
  document.body.style.overflow = previousOverflow
  emit('modalChange', false)
  trigger.value?.focus()
}
async function show() {
  if (open.value) return
  previousOverflow = document.body.style.overflow
  document.body.style.overflow = 'hidden'
  open.value = true
  emit('modalChange', true)
  await nextTick()
  panel.value?.querySelector<HTMLButtonElement>('.history-close')?.focus()
}
function keydown(event: KeyboardEvent) {
  if (!open.value) return
  if (event.key === 'Escape') { event.preventDefault(); close() }
  if (event.key !== 'Tab') return
  const controls = Array.from(panel.value?.querySelectorAll<HTMLButtonElement>('button:not(:disabled)') || [])
  const first = controls[0], last = controls[controls.length - 1]
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
}
function select(id: string) { emit('select', id); if (open.value) close() }
function newConversation() { emit('new'); if (open.value) close() }
function desktopChanged(event: MediaQueryListEvent) { if (event.matches) close() }
onMounted(() => {
  if (!window.matchMedia) return
  desktop = window.matchMedia('(min-width: 981px)')
  desktop.addEventListener('change', desktopChanged)
})
onBeforeUnmount(() => { close(); desktop?.removeEventListener('change', desktopChanged) })
</script>

<template>
  <div class="history-toggle-row">
    <button ref="trigger" type="button" class="history-toggle" :aria-expanded="open" aria-controls="chat-history" @click="show"><Clock aria-hidden="true" />历史对话</button>
  </div>
  <button v-if="open" class="history-backdrop" type="button" tabindex="-1" aria-label="关闭历史对话" @click="close" />
  <aside id="chat-history" ref="panel" class="history-panel" :class="{ 'is-open': open }"
    :role="open ? 'dialog' : undefined" :aria-modal="open ? 'true' : undefined" aria-labelledby="history-heading" @keydown="keydown">
    <div class="history-heading-row">
      <h2 id="history-heading" class="history-heading">历史对话</h2>
      <button type="button" class="history-close" aria-label="关闭历史对话" @click="close"><Close aria-hidden="true" /></button>
    </div>
    <button type="button" class="new-conversation" :disabled="disabled" @click="newConversation"><Plus aria-hidden="true" />新对话</button>
    <div class="history-list">
      <p v-if="loading" class="history-state" role="status">正在加载历史…</p>
      <div v-if="error" class="history-state history-error" role="alert">{{ error }}<button type="button" class="history-retry" @click="emit('refresh')">重试历史</button></div>
      <p v-else-if="!loading && !conversations.length" class="history-state">还没有历史对话。从一首喜欢的诗开始吧。</p>
      <button v-for="cv in conversations" :key="cv.sessionId" type="button" class="conv-item" :class="{ active: cv.sessionId === selected }"
        :aria-pressed="cv.sessionId === selected" :disabled="disabled" @click="select(cv.sessionId)">
        <span class="conv-preview">{{ cv.preview || '新对话' }}</span>
        <span class="conv-meta"><span>{{ cv.updatedAt || '刚刚' }}</span><span v-if="cv.summarized" class="conv-tag">已摘要</span></span>
      </button>
    </div>
  </aside>
</template>

<style scoped>
.history-toggle-row, .history-backdrop, .history-close { display: none; }
.history-panel { width: 248px; flex: none; padding: 20px 12px; display: flex; flex-direction: column; background: var(--md-surface-container); border-right: 1px solid var(--md-outline); }
.history-heading-row { display: flex; align-items: center; justify-content: space-between; padding: 0 8px; }
.history-heading { font-size: 16px; font-weight: 500; margin: 0 0 16px; color: var(--md-on-surface); }
.new-conversation, .history-toggle { display: inline-flex; align-items: center; justify-content: center; gap: 8px; min-height: 44px; padding: 0 18px; border: 0; border-radius: 999px; color: var(--md-on-primary-container); background: var(--md-primary-container); font: inherit; font-size: 14px; font-weight: 500; cursor: pointer; }
.new-conversation svg, .history-toggle svg, .history-close svg { width: 20px; height: 20px; }
.history-list { margin-top: 20px; overflow: auto; flex: 1; }
.history-state { color: var(--md-on-surface-variant); font-size: 13px; line-height: 1.7; padding: 8px; }
.history-error { color: var(--md-error); }
.history-retry { display: block; min-height: 44px; margin-top: 4px; background: transparent; color: var(--md-primary); border: 0; padding: 0 8px; font: inherit; cursor: pointer; }
.conv-item { display: block; text-align: left; width: 100%; padding: 12px; margin-bottom: 4px; border: 0; border-radius: 16px; background: transparent; color: var(--md-on-surface); font: inherit; cursor: pointer; }
.conv-item:hover { background: color-mix(in srgb, var(--md-primary) 8%, transparent); }
.conv-item.active { background: var(--md-primary-container); color: var(--md-on-primary-container); }
.conv-preview { display: block; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; font-size: 14px; }
.conv-meta { display: flex; align-items: center; justify-content: space-between; gap: 8px; font-size: 11px; color: var(--md-on-surface-variant); margin-top: 6px; }
.conv-tag { border: 1px solid var(--md-outline); border-radius: 6px; padding: 1px 5px; }
.new-conversation:disabled, .conv-item:disabled { opacity: .5; cursor: default; }
.new-conversation:focus-visible, .history-toggle:focus-visible, .history-close:focus-visible, .history-retry:focus-visible, .conv-item:focus-visible { outline: 3px solid var(--md-primary); outline-offset: 2px; }
@media (max-width: 980px) {
  .history-toggle-row { display: block; position: absolute; top: 12px; left: 12px; z-index: 1; }
  .history-toggle { background: var(--md-surface-container); color: var(--md-on-surface-variant); }
  .history-panel { display: none; }
  .history-panel.is-open { display: flex; position: fixed; inset: 0 auto 0 0; width: min(320px, 88vw); z-index: 2101; border: 0; border-radius: 0 24px 24px 0; box-shadow: 8px 0 32px rgb(0 0 0 / .18); }
  .history-backdrop { display: block; position: fixed; inset: 0; z-index: 2100; background: rgb(0 0 0 / .38); border: 0; }
  .history-close { display: inline-flex; align-items: center; justify-content: center; width: 44px; height: 44px; background: transparent; color: var(--md-on-surface); border: 0; cursor: pointer; border-radius: 50%; }
  .history-heading { margin: 0; }
  .history-heading-row { margin-bottom: 16px; }
}
</style>
