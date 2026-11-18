<script setup lang="ts">
import { computed, shallowRef } from 'vue'
import { Position, VideoPause } from '@element-plus/icons-vue'
import { shouldSubmit } from '@/utils/chatInput'

const draft = defineModel<string>({ required: true })
const props = defineProps<{ generating: boolean; loadingHistory: boolean }>()
const emit = defineEmits<{ send: []; stop: [] }>()
const composing = shallowRef(false)
const canSend = computed(() => !!draft.value.trim() && !props.generating && !props.loadingHistory)
function submit() { if (canSend.value && !composing.value) emit('send') }
function keydown(event: KeyboardEvent) {
  if (!shouldSubmit(event, composing.value)) return
  event.preventDefault()
  submit()
}
</script>

<template>
  <form class="composer" aria-label="撰写消息" @submit.prevent="submit">
    <label for="chat-draft" class="composer-label">给青莲的消息</label>
    <textarea id="chat-draft" v-model="draft" class="composer-input" rows="3" aria-label="给青莲的消息"
      aria-describedby="composer-help" placeholder="聊聊诗句的意思，或请青莲起草一篇帖子…"
      @keydown="keydown" @compositionstart="composing = true" @compositionend="composing = false" />
    <div class="composer-footer">
      <span id="composer-help" class="composer-help">{{ generating ? '接收中，可继续编辑下一条消息' : 'Enter 发送 · Shift + Enter 换行' }}</span>
      <button v-if="generating" class="composer-stop" type="button" @click="emit('stop')"><VideoPause aria-hidden="true" />停止接收</button>
      <button v-else class="composer-send" type="submit" :disabled="!canSend"><Position aria-hidden="true" />发送</button>
    </div>
  </form>
</template>

<style scoped>
.composer { flex: none; margin: 0 20px 20px; padding: 16px; border: 1px solid var(--md-outline); border-radius: 24px; background: var(--md-surface); }
.composer:focus-within { border-color: var(--md-primary); box-shadow: 0 0 0 1px var(--md-primary); }
.composer-label { display: block; font-size: 12px; font-weight: 500; color: var(--md-primary); margin-bottom: 4px; }
.composer-input { display: block; width: 100%; min-height: 64px; max-height: 180px; resize: vertical; border: 0; padding: 4px 0; font: inherit; font-size: 15px; line-height: 1.6; color: var(--md-on-surface); background: transparent; outline: none; }
.composer-input::placeholder { color: var(--md-on-surface-variant); }
.composer-footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 8px; }
.composer-help { color: var(--md-on-surface-variant); font-size: 12px; }
.composer-send, .composer-stop { min-height: 44px; flex: none; display: inline-flex; align-items: center; justify-content: center; gap: 8px; border-radius: 999px; padding: 0 20px; border: 0; cursor: pointer; font: inherit; font-size: 14px; font-weight: 500; transition: filter .15s; }
.composer-send { background: var(--md-primary); color: var(--md-on-primary); }
.composer-stop { background: var(--md-primary-container); color: var(--md-on-primary-container); }
.composer-send svg, .composer-stop svg { width: 18px; height: 18px; }
.composer-send:disabled { opacity: .5; cursor: default; }
.composer-send:hover:not(:disabled), .composer-stop:hover { filter: brightness(.94); }
.composer-send:focus-visible, .composer-stop:focus-visible { outline: 3px solid var(--md-primary); outline-offset: 3px; }
@media (max-width: 980px) { .composer-footer { padding-right: 64px; } }
@media (max-width: 600px) { .composer { margin: 0 12px 12px; padding: 12px; } .composer-help { max-width: 180px; } }
@media (prefers-reduced-motion: reduce) { .composer-send, .composer-stop { transition: none; } }
</style>
