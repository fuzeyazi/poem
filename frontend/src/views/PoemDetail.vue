<script setup lang="ts">
import { shallowRef, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import AppNav from '@/components/AppNav.vue'
import PoemCardModal from '@/components/card/PoemCardModal.vue'
import AllusionCard from '@/components/allusion/AllusionCard.vue'
import { getContentById, getPoemByTitle } from '@/api/poetry'
import { collectPoem, uncollectPoem, getCollectIds, bookShow, bookAddPoem } from '@/api/user'
import { useUserStore } from '@/store/user'
import { matchAllusions } from '@/utils/allusionMatcher'
import { ALLUSION_SEEDS, type Allusion } from '@/utils/allusionSeed'
import request from '@/utils/request'
import type { Poem, UserBook } from '@/api/types'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const poem = shallowRef<Poem | null>(null)
const loading = shallowRef(true)
const loadError = shallowRef('')
const collectedIds = shallowRef(new Set<number>())
const collecting = shallowRef(false)
const collectionOverrides = new Map<number, boolean>()
const collected = computed(() => !!poem.value?.id && collectedIds.value.has(poem.value.id))
const allusionDict = shallowRef<Allusion[]>(ALLUSION_SEEDS)
const activeAllusion = shallowRef<string | null>(null)
const verseLines = computed(() => (poem.value?.content || '').replace(/<br\s*\/?>/gi, '\n').replace(/\r\n/g, '\n').trim().split('\n').filter(Boolean).map(line => matchAllusions(line, allusionDict.value)))
const cardModalVisible = shallowRef(false)
const cardPoemData = computed(() => ({ title: poem.value?.title || '无题', dynasty: poem.value?.dynasty || '', writer: poem.value?.writer || '佚名', type: poem.value?.type || '', content: poem.value?.content || '' }))
let poemEpoch = 0
const loadPoem = async () => {
  const epoch = ++poemEpoch
  loading.value = true; loadError.value = ''; poem.value = null; activeAllusion.value = null
  try {
    const id = Number(route.query.id) || 0
    const result = id ? await getContentById(id) : (await getPoemByTitle(String(route.params.title)))?.records?.[0]
    if (epoch === poemEpoch) poem.value = result?.title ? result : null
  } catch { if (epoch === poemEpoch) loadError.value = '诗词加载失败，请重试。' }
  finally { if (epoch === poemEpoch) loading.value = false }
}
watch(() => [route.params.title, route.query.id], loadPoem, { immediate: true })
const backToList = () => {
  const source = typeof route.query.from === 'string' && /^\/poetry(?:\?|$)/.test(route.query.from) ? route.query.from : '/poetry'
  if (router.options.history.state.back === source) router.back()
  else void router.push(source)
}
const toggleCollect = async () => {
  const id = poem.value?.id
  if (!id || collecting.value) return
  const shouldCollect = !collectedIds.value.has(id)
  collecting.value = true
  try {
    if (shouldCollect) await collectPoem({ poemid: id })
    else await uncollectPoem({ poemid: id })
    collectionOverrides.set(id, shouldCollect)
    const next = new Set(collectedIds.value)
    if (shouldCollect) next.add(id)
    else next.delete(id)
    collectedIds.value = next
    ElMessage.success(shouldCollect ? '已收入书架' : '已移出书架')
  } catch { /* The request layer owns error notifications. */ }
  finally { collecting.value = false }
}
const askAi = () => {
  if (poem.value) void router.push({ name: 'ai', query: { poemTitle: poem.value.title, poemId: poem.value.id ? String(poem.value.id) : undefined } })
}
const closeAllusion = (event: Event) => {
  if (!(event.target as HTMLElement).closest('.allusion-mark, .allusion-popper-m3')) activeAllusion.value = null
}

const bookDlg = shallowRef(false)
const books = shallowRef<UserBook[]>([])
const booksLoading = shallowRef(false)
const booksError = shallowRef('')
const pickedBook = shallowRef<number | null>(null)
const adding = shallowRef(false)
let booksEpoch = 0
const loadBooks = async () => {
  const epoch = ++booksEpoch
  booksLoading.value = true; booksError.value = ''
  try { const list = await bookShow(); if (epoch === booksEpoch) books.value = list || [] }
  catch { if (epoch === booksEpoch) booksError.value = '诗集加载失败，请重试。' }
  finally { if (epoch === booksEpoch) booksLoading.value = false }
}
const openBookPicker = () => { pickedBook.value = null; bookDlg.value = true; void loadBooks() }
const addToBook = async () => {
  if (!pickedBook.value || !poem.value?.id || adding.value) return
  adding.value = true
  try { await bookAddPoem({ bookid: pickedBook.value, poemid: poem.value.id }); ElMessage.success('已加入诗集'); bookDlg.value = false }
  catch { /* The request layer owns error notifications. */ }
  finally { adding.value = false }
}
onMounted(async () => {
  document.addEventListener('pointerdown', closeAllusion)
  await Promise.allSettled([
    ...(userStore.token ? [getCollectIds().then(ids => {
      const next = new Set(ids || [])
      for (const [id, saved] of collectionOverrides) {
        if (saved) next.add(id)
        else next.delete(id)
      }
      collectedIds.value = next
    })] : []),
    request.get<Allusion[], Allusion[]>('/user/allusion/list').then(list => { if (Array.isArray(list) && list.length) allusionDict.value = list }),
  ])
})
onBeforeUnmount(() => { poemEpoch++; booksEpoch++; document.removeEventListener('pointerdown', closeAllusion) })
</script>

<template>
  <div class="detail-page">
    <AppNav />
    <main class="reader-content" :aria-busy="loading">
      <button type="button" class="back-button" data-testid="reader-back" @click="backToList">← 返回诗词</button>
      <p v-if="loading" class="reader-status" role="status">正在加载诗词…</p>
      <div v-else-if="loadError" class="reader-error" role="alert">{{ loadError }}<button type="button" class="back-button" @click="loadPoem">重试</button></div>
      <article v-else-if="poem" class="sheet">
        <header class="sheet-head"><div class="kicker">诗词 · {{ poem.dynasty }}</div><h1>{{ poem.title }}</h1><div class="author">{{ poem.dynasty }} · {{ poem.writer }}<span v-if="poem.type"> · {{ poem.type }}</span></div></header>
        <div class="verse">
          <div v-for="(tokens, lineIndex) in verseLines" :key="lineIndex" class="vline">
            <template v-for="(token, tokenIndex) in tokens" :key="tokenIndex">
              <el-popover v-if="token.type === 'allusion' && token.allusion" :visible="activeAllusion === `${lineIndex}-${tokenIndex}`" trigger="click" :width="360" :popper-style="{ width: 'min(360px, calc(100vw - 32px))', maxWidth: 'calc(100vw - 32px)', maxHeight: 'calc(100dvh - 32px)', overflowY: 'auto' }" popper-class="allusion-popper-m3" placement="top" :fallback-placements="['bottom', 'right', 'left']">
                <template #reference><span class="allusion-reference"><button type="button" class="allusion-mark" :aria-expanded="activeAllusion === `${lineIndex}-${tokenIndex}`" :aria-label="`${token.content}：查看典故`" @click="activeAllusion = activeAllusion === `${lineIndex}-${tokenIndex}` ? null : `${lineIndex}-${tokenIndex}`" @keydown.esc.stop.prevent="activeAllusion = null">{{ token.content }}</button></span></template>
                <AllusionCard :allusion="token.allusion" />
              </el-popover>
              <template v-else>{{ token.content }}</template>
            </template>
          </div>
        </div>
        <section v-if="poem.translation" class="dsec"><h2 class="lab">译注</h2><p class="ct">{{ poem.translation }}</p></section>
        <section v-if="poem.shangxi" class="dsec"><h2 class="lab">赏析</h2><p class="ct">{{ poem.shangxi }}</p></section>
        <div class="sheet-foot">
          <button type="button" class="collect" data-testid="collect" :class="{ on: collected }" :aria-pressed="collected" :disabled="collecting || !poem.id" @click="toggleCollect">{{ collecting ? '正在保存…' : collected ? '♥ 已在书架' : '♡ 收入书架' }}</button>
          <button type="button" class="ask" @click="askAi">请诗友讲析</button>
          <button type="button" class="collect card-btn" @click="cardModalVisible = true">生成诗词卡片</button>
          <button type="button" class="collect" data-testid="book-picker" :disabled="!poem.id" @click="openBookPicker">＋ 加入诗集</button>
        </div>
        <el-dialog v-model="bookDlg" title="加入诗集" width="min(420px, calc(100vw - 32px))" align-center :close-on-click-modal="!adding" :close-on-press-escape="!adding" :show-close="!adding">
          <p v-if="booksLoading" role="status">正在加载诗集…</p>
          <div v-else-if="booksError" class="reader-error" role="alert">{{ booksError }}<button type="button" class="back-button" data-testid="books-retry" @click="loadBooks">重试</button></div>
          <p v-else-if="!books.length" class="muted">还没有诗集，去「我的 → 诗集本」先建一本吧。</p>
          <el-radio-group v-else v-model="pickedBook" class="book-pick" :disabled="adding" aria-label="选择诗集"><el-radio v-for="book in books" :key="book.bookid" :value="book.bookid!" class="book-item">《{{ book.bookname }}》<span class="muted">{{ book.sum || 0 }} 首</span></el-radio></el-radio-group>
          <template #footer><el-button :disabled="adding" @click="bookDlg = false">取消</el-button><el-button type="primary" :disabled="!pickedBook || booksLoading || !!booksError" :loading="adding" @click="addToBook">加入</el-button></template>
        </el-dialog>
        <PoemCardModal v-model:visible="cardModalVisible" :poem="cardPoemData" />
      </article>
      <el-empty v-else description="未找到该诗" />
    </main>
  </div>
</template>

<style scoped>
.detail-page { min-height: 100vh; color: var(--md-on-surface); }.reader-content { max-width: 960px; margin: auto; padding: 24px 32px 48px; }.back-button { display: inline-flex; align-items: center; min-height: 48px; padding: 12px 16px; margin-bottom: 16px; border: 0; border-radius: 999px; color: var(--md-primary); background: transparent; font: inherit; cursor: pointer; }.back-button:hover { background: var(--md-primary-container); }.reader-status { padding: 32px 16px; color: var(--md-on-surface-variant); }.reader-error { padding: 16px; color: var(--md-error); border: 1px solid var(--md-error); border-radius: 16px; }
.sheet { background: var(--md-surface); border: 1px solid var(--md-outline); border-radius: 24px; padding: 48px 56px; }.sheet-head { text-align: center; padding-bottom: 24px; border-bottom: 1px solid var(--md-outline); }.kicker { font-size: 14px; color: var(--md-primary); }.sheet-head h1 { font-size: clamp(28px, 4vw, 40px); font-weight: 500; line-height: 1.5; margin: 12px 0; overflow-wrap: anywhere; }.author { font-size: 14px; line-height: 1.8; color: var(--md-on-surface-variant); }.verse { margin: 32px 0; }.vline { text-align: center; font-family: var(--f-serif); font-size: 22px; line-height: 2.3; color: var(--md-on-surface); overflow-wrap: anywhere; }
.allusion-mark { color: var(--md-primary); background: transparent; border: 0; border-bottom: 1.5px dashed var(--md-primary); border-radius: 4px; min-height: 44px; padding: 0 2px; font: inherit; line-height: inherit; cursor: pointer; }.allusion-mark:hover, .allusion-mark[aria-expanded="true"] { background: var(--md-primary-container); color: var(--md-on-primary-container); }
.dsec { margin-top: 24px; padding-top: 24px; border-top: 1px solid var(--md-outline); }.lab { font-size: 18px; font-weight: 500; color: var(--md-on-surface); margin: 0 0 12px; }.ct { font-size: 16px; color: var(--md-on-surface-variant); line-height: 2; white-space: pre-line; margin: 0; overflow-wrap: anywhere; }
.sheet-foot { margin-top: 32px; display: flex; flex-wrap: wrap; justify-content: center; gap: 12px; }.collect, .ask { min-height: 48px; padding: 12px 20px; border-radius: 999px; font: inherit; font-size: 14px; cursor: pointer; transition: background 150ms; }.collect { border: 1px solid var(--md-outline); color: var(--md-primary); background: var(--md-surface); }.collect:hover, .collect.on { background: var(--md-primary-container); color: var(--md-on-primary-container); border-color: var(--md-primary); }.ask { background: var(--md-primary); border: 0; color: var(--md-on-primary); }.book-pick { display: flex; align-items: stretch; flex-direction: column; gap: 8px; width: 100%; }.book-item { height: auto; min-height: 44px; margin-right: 0; white-space: normal; }.book-item :deep(.el-radio__label) { white-space: normal; overflow-wrap: anywhere; }.muted { color: var(--md-on-surface-variant); line-height: 1.8; }.book-item .muted { margin-left: 8px; font-size: 13px; }
button:focus-visible { outline: 3px solid var(--md-primary); outline-offset: 3px; }button:disabled { opacity: .5; cursor: default; }
@media (max-width: 720px) { .reader-content { padding: 16px 16px 32px; }.sheet { padding: 28px 20px; }.vline { font-size: 19px; line-height: 2.2; }.sheet-foot { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }.collect, .ask { padding: 12px 8px; }.ct { font-size: 15px; } }
@media (prefers-reduced-motion: reduce) { .collect, .ask { transition: none; } }
</style>
