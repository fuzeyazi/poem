<template>
  <div>
    <AppNav />
    <div class="wrap">
      <div class="page-head">
        <h2 class="labbtn">今 日 复 习</h2>
        <span class="muted">按艾宾浩斯节奏，到期即温</span>
      </div>

      <div v-loading="loading">
        <div v-if="!loading && !groups.length" class="empty-state">
          <div class="muted">今天没有到期的复习，去诗集本添新诗吧</div>
        </div>

        <section v-for="g in groups" :key="g.bookid" class="book-group">
          <div class="g-head">
            <h3>{{ g.bookname }}</h3>
            <span class="muted">今日 {{ g.items.length }} 首</span>
          </div>
          <div
            v-for="it in g.items"
            :key="g.bookid + '-' + it.poemid"
            class="rev-row"
            :class="{ done: it.done }"
          >
            <div class="rev-main" @click="goDetail(it)">
              <span class="r-title">{{ it.title }}</span>
              <span class="r-author muted">{{ it.dynasty }}　{{ it.writer }}</span>
            </div>
            <div class="rev-right">
              <span v-if="it.done" class="done-tag">已复习 · {{ it.dueNext || '进入下一轮' }}</span>
              <span v-else class="due">{{ it.dueStage || '今日到期' }}</span>
              <button class="rev-btn" :disabled="it.done || it.doing" @click="review(it)">
                {{ it.doing ? '提交中…' : it.done ? '已完成' : '答对了，复习' }}
              </button>
            </div>
          </div>
        </section>

        <section v-if="logs.length" class="log-block">
          <div class="lab">近 七 日 复 习</div>
          <div class="log-rows">
            <div v-for="l in logs" :key="l.date" class="log-row">
              <span class="ld">{{ l.date }}</span>
              <span class="lc">{{ l.count }} 首</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import AppNav from '@/components/AppNav.vue'
import { bookShow, bookToday, getRemindLog } from '@/api/user'
import { poemReviewEnd } from '@/api/poetry'
import type { TodayReviewVo } from '@/api/types'

interface ReviewItem extends TodayReviewVo {
  done?: boolean
  doing?: boolean
  dueNext?: string
}
interface BookGroup {
  bookid: number
  bookname: string
  items: ReviewItem[]
}

const router = useRouter()
const loading = ref(true)
const groups = ref<BookGroup[]>([])
const logs = ref<{ date: string; count: number }[]>([])

const goDetail = (it: TodayReviewVo) =>
  router.push({ name: 'poem-detail', params: { title: it.title }, query: { id: String(it.poemid) } })

// 复习动作：答对触发 reviewCount+1 且 next_review_date 按 1/3/7/14/30 天推进（§3.1）
const review = async (it: ReviewItem) => {
  if (it.done || it.doing) return
  it.doing = true
  try {
    await poemReviewEnd(it.poemid)
    it.done = true
    ElMessage.success(`《${it.title}》复习完成，进入下一轮`)
  } catch { /* 请求层统一显示失败提示，保留当前复习状态供重试。 */ } finally { it.doing = false }
}

onMounted(async () => {
  loading.value = true
  try {
    const books = (await bookShow()) || []
    const merged = await Promise.all(
      books.map(async (b) => {
        try {
          const items = ((await bookToday(b.bookid!)) || []).map((it) => ({ ...it, done: false, doing: false }))
          return { bookid: b.bookid!, bookname: b.bookname || '未命名诗集', items }
        } catch { return { bookid: b.bookid!, bookname: b.bookname || '', items: [] as ReviewItem[] } }
      }),
    )
    groups.value = merged.filter((g) => g.items.length > 0)
  } catch { groups.value = [] } finally { loading.value = false }
  try { logs.value = (await getRemindLog()) || [] } catch {}
})
</script>

<style scoped>
.page-head { display: flex; align-items: baseline; gap: 18px; margin-bottom: 30px; }
.labbtn { font-family: var(--f-sans); font-weight: 500; font-size: 28px; letter-spacing: normal; color: var(--md-on-surface); margin: 0; }
.book-group { margin-bottom: 24px;  padding: 24px;  background: var(--md-surface-container-lowest);  border-radius: 24px;  border: 1px solid var(--md-outline-variant); }
.g-head { display: flex; align-items: baseline; gap: 16px; padding-bottom: 12px; border-bottom: 1px solid var(--md-outline); }
.g-head h3 { font-family: var(--f-sans); font-weight: 500; font-size: 19px; letter-spacing: normal; margin: 0; }
.rev-row {
  display: flex; align-items: center; justify-content: space-between; gap: 20px;
  padding: 18px 8px; border-bottom: 1px solid var(--md-outline-variant);
  transition: opacity .3s;
}
.rev-row.done { opacity: 1; }
.rev-main { display: flex; align-items: baseline; gap: 14px; cursor: pointer; min-width: 0; }
.r-title { font-family: var(--f-sans); font-weight: 500; font-size: 17px; letter-spacing: normal; color: var(--md-on-surface); }
.rev-main:hover .r-title { color: var(--md-primary); }
.rev-right { display: flex; align-items: center; gap: 16px; flex: none; }
.due { font-size: 13px; letter-spacing: normal; color: var(--md-on-surface-variant); }
.done-tag { font-size: 13px; letter-spacing: normal; color: var(--md-success); }
.rev-btn {
  height: 48px; padding: 0 18px; cursor: pointer;
  background: var(--md-primary); color: var(--md-on-primary); border: none;
  font-family: var(--f-sans); font-size: 13px; letter-spacing: normal;
  transition: background .2s;
 border-radius: 999px; }
.rev-btn:hover:not(:disabled) { background: var(--md-primary); }
.rev-btn:disabled { cursor: default; opacity: .7; }
.log-block { margin-top: 56px; padding-top: 24px; border-top: 1px solid var(--md-outline); }
.log-block .lab { font-size: 13px; letter-spacing: normal; color: var(--md-primary); margin-bottom: 16px; }
.log-row { display: flex; justify-content: space-between; max-width: 360px; padding: 8px 0; border-bottom: 1px dashed var(--md-outline-variant); font-size: 13px; }
.log-row .ld { color: var(--md-on-surface-variant); letter-spacing: normal; }
.log-row .lc { font-family: var(--f-sans); color: var(--md-on-surface); }

:deep(.el-button) { min-height: 44px; border-radius: 999px; font-family: var(--f-sans); letter-spacing: normal; }
:deep(.el-input__wrapper) { min-height: 48px; border-radius: 12px; }
:deep(.el-textarea__inner) { border-radius: 12px; font-size: 15px; }
:deep(.el-tabs__item) { min-height: 48px; font-family: var(--f-sans); letter-spacing: normal; }
:deep(.el-dialog) { max-width: calc(100vw - 32px); border-radius: 28px; }
.form-error { font-size: 14px; line-height: 1.5; color: var(--md-error); background: var(--md-error-container); border-radius: 12px; padding: 12px 16px; }

@media (max-width: 600px) { .page-head, .g-head, .rev-row, .rev-main, .rev-right { flex-wrap: wrap; gap: 12px; } .book-group { padding: 20px; } }
</style>
