<script setup lang="ts">
import { computed, onBeforeUnmount, shallowRef, watch } from 'vue'
import { ArrowDown, ArrowUp, CircleCheck, Warning } from '@element-plus/icons-vue'
import type { ChatMessage } from './types'

const props = defineProps<{ message: ChatMessage; sessionId: string; question: string; token: string }>()
const expanded = shallowRef(false)
const feedback = shallowRef<'' | 'up' | 'down'>('')
const submitting = shallowRef(false)
const feedbackError = shallowRef('')
let feedbackController: AbortController | null = null
let disposed = false
const toolLabels: Record<string, string> = { query_poem: '查诗词', query_poet: '查诗人', query_dynasty_poems: '查朝代' }
const routeLabels: Record<string, string> = { knowledge: '知识类', business: '业务类', ruling: '判定类', complaint: '投诉类', chitchat: '闲聊类', other: '其他类' }
const sources: Record<string, string> = {
  preset: '来源：固定话术（未调用模型）', fallback: '来源：检索证据不足 · 兜底答复', tool: '来源：诗词资料库（MySQL）工具查询',
  rag: '来源：知识库检索（BGE-M3 + Milvus）', llm: '来源：模型自身知识（可能不准确）',
}
const sourceText = computed(() => sources[props.message.source ?? ''] || '来源：本轮处理记录')
const tools = computed(() => props.message.toolCalls || [])
const toolLabel = (name: string) => toolLabels[name] || name
const argsText = (args: unknown) => !args ? '-' : typeof args === 'string' ? args : typeof args === 'object' ? Object.entries(args).map(([k, v]) => `${k}=${String(v)}`).join(', ') : String(args)
const traceRows = computed<[string, string][]>(() => {
  const trace = props.message.trace || {}
  const route = trace.route || ''
  const knowledge = route === 'knowledge'
  const doneTools = tools.value.filter(c => c.status !== 'calling')
  const diverged: Record<string, string> = {
    agent_error: '未完成 · 模型调用失败，已兜底', max_iter: `ReAct ${trace.iters || 0} 圈 · 触迭代上限，强制作答`, max_tokens: `ReAct ${trace.iters || 0} 圈 · 触 token 上限，强制作答`,
  }
  const agentText = route === 'complaint' || route === 'chitchat' ? '未进入 · 预设话术直接收尾'
    : trace.gate === 'insufficient' ? '未进入 · 证据不足已兜底'
    : diverged[trace.fallbackReason] || `ReAct ${trace.iters || 0} 圈${doneTools.length ? ' · ' + doneTools.map(c => toolLabel(c.tool)).join(' + ') : ' · 无工具调用'}`
  return [
    ['指代消解', trace.queryChanged ? '已改写 · 结合上轮指代' : '透传 · 未改写'],
    ['意图识别', `${trace.intent || '-'}${trace.confidence != null ? ' · conf ' + Number(trace.confidence).toFixed(2) : ''}`],
    ['意图分流', `${routeLabels[route] || '-'} · 硬编码查表`],
    ['判定子流程', trace.subflowKind ? `${trace.subflowKind === 'meter' ? '格律合规' : '校勘核对'} · 条款 ${trace.policyCount || 0} 条` : '未进入'],
    ['知识检索', knowledge ? `${trace.retrievedCount || 0} 条 · top ${trace.score == null ? '-' : Number(trace.score).toFixed(4)}` : '跳过 · 不预检索'],
    ['置信度闸', knowledge ? trace.gate === 'pass' ? 'pass · 证据充足' : 'insufficient · 已走兜底' : '跳过'],
    ['主力 Agent', agentText],
    ['日志记录', `落 messages 表 · ${trace.tokens || 0} tokens${trace.elapsedMs != null ? ' · ' + trace.elapsedMs + 'ms' : ''}`],
  ]
})
async function sendFeedback(rating: 'up' | 'down') {
  if (submitting.value || feedback.value === rating) return
  submitting.value = true
  feedbackError.value = ''
  const controller = new AbortController()
  feedbackController = controller
  try {
    const resp = await fetch(rating === 'down' ? '/agent/feedback/negative' : '/agent/feedback', {
      method: 'POST', headers: { token: props.token, 'Content-Type': 'application/json' },
      body: JSON.stringify({ sessionId: props.sessionId, message: props.question, rating }), signal: controller.signal,
    })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    if (!disposed && feedbackController === controller) feedback.value = rating
  } catch (cause) { if (!disposed && feedbackController === controller && !controller.signal.aborted) feedbackError.value = `反馈提交失败：${cause instanceof Error ? cause.message : '请重试'}` }
  finally { if (feedbackController === controller && !disposed) submitting.value = false }
}
watch(() => props.message.state, state => {
  if (state === 'waiting') { feedbackController?.abort(); feedbackController = null; submitting.value = false; feedback.value = ''; feedbackError.value = ''; expanded.value = false }
})
onBeforeUnmount(() => { disposed = true; feedbackController?.abort() })
</script>

<template>
  <div class="sources">
    <button type="button" class="source-toggle" :aria-expanded="expanded" :aria-controls="`source-${message.id}`" @click="expanded = !expanded">
      <span class="source-mark" aria-hidden="true" />{{ sourceText }}<ArrowUp v-if="expanded" aria-hidden="true" /><ArrowDown v-else aria-hidden="true" />
    </button>
    <section v-if="expanded" :id="`source-${message.id}`" class="source-panel" aria-label="来源与处理轨迹">
      <template v-if="message.trace"><h3 class="source-heading">编排轨迹</h3><ol class="trace-list"><li v-for="(row, index) in traceRows" :key="row[0]" class="trace-row"><span class="trace-index">{{ index + 1 }}</span><span class="trace-node">{{ row[0] }}</span><span class="trace-value">{{ row[1] }}</span></li></ol></template>
      <div v-for="(tool, index) in tools" :key="index" class="tool-row"><b>{{ toolLabel(tool.tool) }}</b><span>状态：{{ tool.status === 'calling' ? '处理中' : tool.status || '已返回' }}</span><span>参数：{{ argsText(tool.args) }}</span><span>耗时：{{ tool.durationMs != null ? tool.durationMs + 'ms' : '-' }}</span></div>
    </section>
    <div v-if="message.source && message.state !== 'waiting' && message.state !== 'researching' && message.state !== 'streaming'" class="feedback-row">
      <button type="button" class="feedback-button" aria-label="这条回答有帮助" :aria-pressed="feedback === 'up'" :disabled="submitting || feedback === 'up'" @click="sendFeedback('up')"><CircleCheck aria-hidden="true" />有帮助</button>
      <button type="button" class="feedback-button" aria-label="这条回答需要改进" :aria-pressed="feedback === 'down'" :disabled="submitting || feedback === 'down'" @click="sendFeedback('down')"><Warning aria-hidden="true" />需改进</button>
      <span v-if="submitting" class="feedback-note" role="status">正在提交…</span><span v-else-if="feedback" class="feedback-note" role="status">已反馈，感谢你的意见</span>
    </div>
    <p v-if="feedbackError" class="feedback-error" role="alert">{{ feedbackError }}</p>
  </div>
</template>

<style scoped>
.sources { margin-top: 8px; }
.source-toggle { display: inline-flex; align-items: center; text-align: left; gap: 8px; min-height: 44px; padding: 6px 8px; border: 0; border-radius: 12px; background: transparent; color: var(--md-on-surface-variant); font: inherit; font-size: 12px; cursor: pointer; }
.source-toggle:hover, .feedback-button:hover:not(:disabled) { background: color-mix(in srgb, var(--md-primary) 8%, transparent); }
.source-toggle svg { width: 14px; flex: none; }
.source-mark { width: 6px; height: 6px; flex: none; border-radius: 50%; background: var(--md-primary); }
.source-panel { padding: 16px; margin: 4px 0 8px; border: 1px solid var(--md-outline); border-radius: 20px; background: var(--md-surface-container); color: var(--md-on-surface-variant); font-size: 12px; }
.source-heading { font-size: 14px; font-weight: 500; margin: 0 0 12px; color: var(--md-on-surface); }
.trace-list { list-style: none; margin: 0; padding: 0; }
.trace-row { display: grid; grid-template-columns: 22px 74px minmax(0, 1fr); gap: 8px; align-items: start; margin: 8px 0; line-height: 1.6; }
.trace-index { display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px; background: var(--md-primary-container); color: var(--md-on-primary-container); border-radius: 50%; }
.trace-node { color: var(--md-on-surface); }
.trace-value { overflow-wrap: anywhere; }
.tool-row { display: flex; flex-direction: column; gap: 4px; border-top: 1px solid var(--md-outline); padding-top: 12px; margin-top: 12px; overflow-wrap: anywhere; }
.feedback-row { display: flex; align-items: center; flex-wrap: wrap; gap: 4px; }
.feedback-button { display: inline-flex; align-items: center; gap: 6px; min-height: 44px; padding: 0 12px; border-radius: 999px; border: 0; background: transparent; color: var(--md-on-surface-variant); font: inherit; font-size: 12px; cursor: pointer; }
.feedback-button svg { width: 16px; height: 16px; }
.feedback-button[aria-pressed="true"] { background: var(--md-primary-container); color: var(--md-on-primary-container); }
.feedback-button:disabled { cursor: default; }
.feedback-note { font-size: 12px; color: var(--md-on-surface-variant); padding: 0 8px; }
.feedback-error { font-size: 12px; color: var(--md-error); padding: 0 8px; }
.source-toggle:focus-visible, .feedback-button:focus-visible { outline: 3px solid var(--md-primary); outline-offset: 2px; }
@media (max-width: 600px) { .trace-row { grid-template-columns: 22px minmax(0, 1fr); } .trace-value { grid-column: 2; } }
</style>
