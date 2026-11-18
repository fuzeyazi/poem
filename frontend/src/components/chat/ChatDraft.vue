<script setup lang="ts">
import { computed, onBeforeUnmount, shallowRef } from 'vue'
import { useRouter } from 'vue-router'
import { postBlog } from '@/api/forum'
import type { ChatDraft } from './types'

const draft = defineModel<ChatDraft>({ required: true })
const props = defineProps<{ receiving: boolean }>()
const router = useRouter()
const publishing = shallowRef(false)
const published = shallowRef(false)
const error = shallowRef('')
const title = computed({ get: () => draft.value.title, set: value => { draft.value = { ...draft.value, title: value } } })
const content = computed({ get: () => draft.value.content, set: value => { draft.value = { ...draft.value, content: value } } })
const categories = ['诗词创作', '诗词赏析', '诗词学习', '诗词活动', '诗词资源', '诗词杂谈']
let timer: ReturnType<typeof setTimeout> | undefined
let disposed = false
async function publish() {
  if (publishing.value || published.value || props.receiving) return
  if (!title.value.trim() || !content.value.trim()) { error.value = '请填写帖子标题和正文'; return }
  error.value = ''
  publishing.value = true
  try {
    await postBlog({ title: title.value, content: content.value, type: categories.includes(draft.value.tag ?? '') ? draft.value.tag! : '诗词杂谈' })
    if (disposed) return
    published.value = true
    timer = setTimeout(() => { void router.push('/forum') }, 900)
  } catch { if (!disposed) error.value = '发布失败，草稿已保留，请修改或重试' }
  finally { if (!disposed) publishing.value = false }
}
onBeforeUnmount(() => { disposed = true; if (timer) clearTimeout(timer) })
</script>

<template>
  <section class="draft-card" aria-label="审阅帖子草稿">
    <div class="draft-heading"><span>帖子草稿</span><span class="draft-tag">{{ draft.tag || '诗词杂谈' }}</span></div>
    <template v-if="!published">
      <label class="draft-label">帖子标题<input v-model="title" aria-label="帖子标题" class="draft-title-input" maxlength="50" :disabled="publishing" /></label>
      <label class="draft-label">帖子正文<textarea v-model="content" aria-label="帖子正文" class="draft-content-input" rows="6" maxlength="2000" :disabled="publishing" /></label>
      <p class="draft-help">审阅并编辑后发布到诗坛。{{ receiving ? '正在接收，请等待本轮结束。' : '' }}</p>
      <p v-if="error" class="draft-error" role="alert">{{ error }}</p>
      <button type="button" class="draft-publish" :disabled="publishing || receiving" @click="publish">{{ publishing ? '正在发布…' : '发布到诗坛' }}</button>
    </template>
    <template v-else><h3 class="draft-title">{{ draft.title }}</h3><p class="draft-content">{{ draft.content }}</p><p class="draft-help" role="status">已发布到诗坛，正在前往…</p></template>
  </section>
</template>

<style scoped>
.draft-card { border: 1px solid var(--md-outline); background: var(--md-surface-container); padding: 16px; margin-top: 16px; border-radius: 20px; }
.draft-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; font-size: 14px; font-weight: 500; }
.draft-tag { font-size: 12px; color: var(--md-on-primary-container); background: var(--md-primary-container); padding: 4px 10px; border-radius: 8px; }
.draft-label { display: block; color: var(--md-on-surface-variant); font-size: 12px; margin-top: 12px; }
.draft-title-input, .draft-content-input { display: block; width: 100%; margin-top: 4px; padding: 12px; border: 1px solid var(--md-outline); background: var(--md-surface); color: var(--md-on-surface); border-radius: 12px; font: inherit; font-size: 14px; line-height: 1.6; }
.draft-content-input { resize: vertical; min-height: 120px; max-height: 320px; }
.draft-title-input:focus, .draft-content-input:focus { outline: 2px solid var(--md-primary); outline-offset: 1px; }
.draft-help { font-size: 12px; color: var(--md-on-surface-variant); margin: 12px 0; }
.draft-error { color: var(--md-error); font-size: 13px; }
.draft-publish { min-height: 44px; border: 0; border-radius: 999px; padding: 0 18px; background: var(--md-primary); color: var(--md-on-primary); font: inherit; font-size: 14px; cursor: pointer; }
.draft-publish:disabled { opacity: .5; cursor: default; }
.draft-publish:focus-visible { outline: 3px solid var(--md-primary); outline-offset: 3px; }
.draft-title { font-size: 16px; font-weight: 500; }
.draft-content { white-space: pre-wrap; font-size: 14px; line-height: 1.7; max-height: 240px; overflow: auto; }
</style>
