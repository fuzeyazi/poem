<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, shallowRef, watch } from 'vue'
import { onBeforeRouteLeave, RouterLink, useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import AppNav from '@/components/AppNav.vue'
import AgeTabs from '@/components/AgeTabs.vue'
import { getPoetryCount, getAllDynasty, getVeryGoodPoem, getSearchSuggest, getHotSearch } from '@/api/poetry'
import { getWriterCount } from '@/api/writer'
import { getRhesisCount, getRandomRhesis } from '@/api/rhesis'
import { collectPoem, uncollectPoem, getCollectIds } from '@/api/user'
import type { Poem, Rhesis } from '@/api/types'
import { useUserStore } from '@/store/user'
import { usePoetrySearch } from '@/composables/usePoetrySearch'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const queryText = (value: unknown) => typeof value === 'string' ? value.trim() : ''
const conditions = computed(() => {
  const q = queryText(route.query.q)
  const page = Number(route.query.page)
  return { q, dynasty: q ? '' : queryText(route.query.dynasty), page: Number.isFinite(page) ? Math.max(1, Math.floor(page) || 1) : 1 }
})
const { records, total, pending, error, loading, refreshing, retry, rememberScroll, restoredScroll } = usePoetrySearch(conditions)
const keyword = shallowRef(conditions.value.q)
const dynasties = shallowRef<string[]>([])
const dynasty = computed(() => conditions.value.dynasty)
const searching = computed(() => !!(conditions.value.q || dynasty.value))
const pageNum = computed(() => conditions.value.page)
const pageCount = computed(() => Math.max(1, Math.ceil(total.value / 4)))
const pagerList = computed(() => {
  const start = Math.max(1, Math.min(pageNum.value - 2, pageCount.value - 4))
  return Array.from({ length: Math.min(5, pageCount.value) }, (_, i) => start + i)
})
const commitSearch = async (q = keyword.value.trim(), d = '', page = 1) => {
  closeSuggestions()
  const query = { q: q || undefined, dynasty: d || undefined, page: page > 1 ? String(page) : undefined }
  if (conditions.value.q === q && dynasty.value === d && pageNum.value === page) return retry()
  await router.push({ name: 'poetry', query })
}
const onSearch = () => { if (!composing.value) void commitSearch() }
const onDynasty = (value: string) => { keyword.value = ''; void commitSearch('', value) }
const goPage = (page: number) => {
  if (page < 1 || page > pageCount.value || page === pageNum.value || pending.value) return
  void commitSearch(conditions.value.q, dynasty.value, page)
}

// Composition and suggestion focus belong to the input. Invalidate requests before debounce ends.
const suggests = shallowRef<string[]>([])
const showSuggest = shallowRef(false)
const activeSuggestion = shallowRef(-1)
const composing = shallowRef(false)
let suggestionEpoch = 0
let suggestTimer: ReturnType<typeof setTimeout> | undefined
let hideTimer: ReturnType<typeof setTimeout> | undefined
const closeSuggestions = () => {
  suggestionEpoch++; clearTimeout(suggestTimer)
  suggests.value = []; showSuggest.value = false; activeSuggestion.value = -1
}
const onKeywordInput = () => {
  closeSuggestions()
  const q = keyword.value.trim()
  if (!q || composing.value) return
  const epoch = suggestionEpoch
  suggestTimer = setTimeout(async () => {
    try {
      const result = await getSearchSuggest(q)
      if (epoch !== suggestionEpoch || composing.value) return
      suggests.value = result || []; showSuggest.value = suggests.value.length > 0
    } catch { if (epoch === suggestionEpoch) closeSuggestions() }
  }, 300)
}
const compositionStart = () => { composing.value = true; closeSuggestions() }
const compositionEnd = (event: CompositionEvent) => {
  composing.value = false; keyword.value = (event.target as HTMLInputElement).value; onKeywordInput()
}
const pickSuggest = (q: string) => { keyword.value = q; void commitSearch(q) }
const onSearchKey = (event: KeyboardEvent) => {
  if (composing.value || event.isComposing || event.keyCode === 229) return
  if (event.key === 'Escape') { event.preventDefault(); closeSuggestions() }
  else if ((event.key === 'ArrowDown' || event.key === 'ArrowUp') && suggests.value.length) {
    event.preventDefault(); showSuggest.value = true
    const step = event.key === 'ArrowDown' ? 1 : -1
    activeSuggestion.value = activeSuggestion.value < 0
      ? (step > 0 ? 0 : suggests.value.length - 1)
      : (activeSuggestion.value + step + suggests.value.length) % suggests.value.length
  } else if (event.key === 'Enter') {
    event.preventDefault()
    if (showSuggest.value && activeSuggestion.value >= 0) pickSuggest(suggests.value[activeSuggestion.value])
    else onSearch()
  }
}
const hideSuggestSoon = () => { hideTimer = setTimeout(closeSuggestions, 150) }
const showSuggestions = () => { clearTimeout(hideTimer); showSuggest.value = suggests.value.length > 0 }
watch(() => route.query, () => { keyword.value = conditions.value.q; closeSuggestions() })

const featured = shallowRef<Poem | null>(null)
const featurePending = shallowRef(false)
const featureError = shallowRef('')
const count = shallowRef(0), writerCount = shallowRef(0), rhesisCount = shallowRef(0)
const hotList = shallowRef<{ kw: string; score: number }[]>([])
const rhesisPool = shallowRef<Rhesis[]>([])
const rhesis = shallowRef<Rhesis | null>(null)
const collectedIds = shallowRef(new Set<number>())
const collecting = shallowRef(false)
const collectionOverrides = new Map<number, boolean>()
const collected = computed(() => !!featured.value?.id && collectedIds.value.has(featured.value.id))
const poemLines = (poem: Poem) => (poem.content || '').replace(/<br\s*\/?>/gi, '\n').split(/\r?\n/).filter(Boolean)
const previewLine = (line: string) => line.length > 60 ? `${line.slice(0, 60)}…` : line
const featuredLines = computed(() => featured.value ? poemLines(featured.value).slice(0, 4).map(previewLine) : [])
const cards = computed(() => records.value.map(poem => ({ poem, lines: poemLines(poem).slice(0, 2).map(previewLine) })))
const detailLocation = (poem: Poem) => ({ name: 'poem-detail', params: { title: poem.title }, query: { id: poem.id ? String(poem.id) : undefined, from: route.fullPath } })
const loadFeatured = async () => {
  if (featurePending.value) return
  featurePending.value = true; featureError.value = ''
  try { const result = await getVeryGoodPoem(); featured.value = result?.title ? result : null }
  catch { featureError.value = '推荐诗词加载失败' }
  finally { featurePending.value = false }
}
const toggleCollect = async () => {
  const id = featured.value?.id
  if (!id || collecting.value) return
  if (!userStore.token) { ElMessage.warning('登录后可收入书架'); return router.push({ name: 'login', query: { redirect: route.fullPath } }) }
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
  if (featured.value) void router.push({ name: 'ai', query: { poemTitle: featured.value.title, poemId: featured.value.id ? String(featured.value.id) : undefined } })
}
const rerollRhesis = () => {
  const choices = rhesisPool.value.filter(item => item.name !== rhesis.value?.name)
  if (choices.length) rhesis.value = choices[Math.floor(Math.random() * choices.length)]
}
onBeforeRouteLeave(() => rememberScroll(window.scrollY))
onMounted(async () => {
  await nextTick()
  window.scrollTo({ top: restoredScroll })
  await Promise.allSettled([
    loadFeatured(), getPoetryCount().then(value => { count.value = value }),
    getWriterCount().then(value => { writerCount.value = value }), getRhesisCount().then(value => { rhesisCount.value = value }),
    getAllDynasty().then(value => { dynasties.value = value || [] }), getHotSearch().then(value => { hotList.value = value || [] }),
    getRandomRhesis().then(value => { rhesisPool.value = value || []; rhesis.value = rhesisPool.value[0] || null }),
    ...(userStore.token ? [getCollectIds().then(value => {
      const next = new Set(value || [])
      for (const [id, saved] of collectionOverrides) {
        if (saved) next.add(id)
        else next.delete(id)
      }
      collectedIds.value = next
    })] : []),
  ])
})
onBeforeUnmount(() => { closeSuggestions(); clearTimeout(hideTimer) })
</script>

<template>
  <div class="poetry-page">
    <AppNav />
    <main class="poetry-content">
      <header class="page-head"><p class="eyebrow">古诗文 · 诗词馆藏</p><h1>找到一首与你相遇的诗</h1><p>检索标题，或按朝代慢慢读。</p></header>
      <section class="search-panel" aria-label="搜索诗词">
        <label class="search-label" for="poetry-search">诗词标题</label>
        <form class="searchline" role="search" @submit.prevent="onSearch">
          <input id="poetry-search" v-model="keyword" role="combobox" aria-autocomplete="list" aria-controls="poetry-suggestions" :aria-expanded="showSuggest" :aria-activedescendant="showSuggest && activeSuggestion >= 0 ? `suggestion-${activeSuggestion}` : undefined" placeholder="如：黄鹤楼、月下独酌" autocomplete="off" @input="onKeywordInput" @keydown="onSearchKey" @compositionstart="compositionStart" @compositionend="compositionEnd" @focus="showSuggestions" @blur="hideSuggestSoon" />
          <button type="submit" class="sbtn">搜索</button>
          <ul v-if="showSuggest && suggests.length" id="poetry-suggestions" class="suggest-pop" role="listbox" aria-label="搜索建议">
            <li v-for="(suggestion, index) in suggests" :id="`suggestion-${index}`" :key="suggestion" role="option" :aria-selected="activeSuggestion === index"><button class="sg-item" type="button" tabindex="-1" :class="{ active: activeSuggestion === index }" @mousedown.prevent @click="pickSuggest(suggestion)">{{ suggestion }}</button></li>
          </ul>
        </form>
        <div v-if="hotList.length" class="hotline"><span>热搜</span><button v-for="hot in hotList" :key="hot.kw" class="hot-item" type="button" @click="pickSuggest(hot.kw)">{{ hot.kw }}</button></div>
        <div class="dynline"><span class="filter-label">朝代</span><AgeTabs :dynasties="dynasties" :model-value="dynasty" @change="onDynasty" /></div>
      </section>
      <section class="results" aria-labelledby="results-heading" :aria-busy="pending">
        <div class="sec-head"><h2 id="results-heading">{{ searching ? '搜索结果' : '馆藏选读' }}</h2><button v-if="searching" class="text-button" type="button" @click="keyword = ''; commitSearch('', '')">清除筛选</button><span v-else class="result-count">共 {{ total }} 首</span></div>
        <p v-if="loading" class="status" role="status">正在加载诗词…</p><p v-else-if="refreshing" class="status" role="status">正在更新，仍可阅读上次结果…</p>
        <div v-if="error" class="error-state" role="alert"><span>{{ error }}</span><button type="button" class="text-button" data-testid="search-retry" @click="retry">重试</button></div>
        <div class="scrolls"><RouterLink v-for="card in cards" :key="`${card.poem.title}|${card.poem.writer}`" class="scroll" :to="detailLocation(card.poem)"><span class="card-meta">{{ card.poem.dynasty }} · {{ card.poem.writer }}</span><h3>{{ card.poem.title }}</h3><p class="sv"><span v-for="(line, index) in card.lines" :key="index">{{ line }}</span></p><span class="goto">阅读全文 →</span></RouterLink></div>
        <div v-if="!pending && !error && !records.length" class="empty-state">未找到相关诗词，可以换一个标题或朝代。</div>
        <nav v-if="total > 4" class="pager" aria-label="诗词分页"><button type="button" :disabled="pageNum <= 1 || pending" @click="goPage(pageNum - 1)">上一页</button><button v-for="page in pagerList" :key="page" type="button" :aria-current="page === pageNum ? 'page' : undefined" :disabled="pending" @click="goPage(page)">{{ page }}</button><button type="button" :disabled="pageNum >= pageCount || pending" @click="goPage(pageNum + 1)">下一页</button></nav>
      </section>
      <section class="featured" aria-labelledby="featured-heading">
        <div class="sec-head"><h2 id="featured-heading">今日共读</h2><button type="button" class="text-button" :disabled="featurePending" @click="loadFeatured">换一首</button></div>
        <p v-if="featurePending" role="status">正在寻找一首好诗…</p><p v-if="featureError" role="alert">{{ featureError }}，请点击“换一首”重试。</p>
        <template v-if="featured"><div class="feature-body"><div><span class="card-meta">{{ featured.dynasty }} · {{ featured.writer }}</span><h3>{{ featured.title }}</h3><p class="feature-verse"><span v-for="(line, index) in featuredLines" :key="index">{{ line }}</span></p></div><p v-if="featured.translation" class="feature-note">{{ featured.translation.slice(0, 100) }}{{ featured.translation.length > 100 ? '…' : '' }}</p></div><div class="hero-actions"><RouterLink class="primary-link" :to="detailLocation(featured)">阅读全文</RouterLink><button type="button" class="text-button" :disabled="collecting" :aria-pressed="collected" @click="toggleCollect">{{ collecting ? '正在保存…' : collected ? '已在书架' : '收入书架' }}</button><button type="button" class="text-button" @click="askAi">请诗友讲析</button></div></template>
      </section>
      <section v-if="rhesis" class="quote"><blockquote>{{ rhesis.name }}</blockquote><cite>{{ rhesis.fromm || '佚名' }}</cite><button class="text-button" type="button" @click="rerollRhesis">另觅佳句</button></section>
      <footer class="foot">诗库 {{ count }} 首 · 诗人 {{ writerCount }} 位 · 名句 {{ rhesisCount }} 句</footer>
    </main>
  </div>
</template>

<style scoped>
.poetry-page { min-height: 100vh; color: var(--md-on-surface); }
.poetry-content { max-width: 1160px; margin: auto; padding: 32px 32px 48px; }
.page-head { margin-bottom: 24px; }.page-head h1 { font-size: clamp(24px, 3vw, 36px); font-weight: 500; margin: 8px 0; line-height: 1.4; }.page-head p { color: var(--md-on-surface-variant); margin: 8px 0; }.eyebrow { color: var(--md-primary); font-size: 14px; }
.search-panel { background: var(--md-surface-container); border-radius: 24px; padding: 24px; }.search-label { display: block; font-size: 14px; margin-bottom: 8px; }.searchline { position: relative; display: flex; gap: 12px; }.searchline input { width: 0; flex: 1; min-width: 0; min-height: 56px; padding: 12px 20px; border: 1px solid var(--md-outline); border-radius: 28px; color: var(--md-on-surface); background: var(--md-surface); font: inherit; }.sbtn, .primary-link { min-height: 48px; padding: 12px 24px; border: 0; border-radius: 999px; background: var(--md-primary); color: var(--md-on-primary); font: inherit; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; text-decoration: none; }
.suggest-pop { position: absolute; top: calc(100% + 8px); left: 0; right: 100px; z-index: 20; padding: 8px; margin: 0; list-style: none; background: var(--md-surface-container); border: 1px solid var(--md-outline); border-radius: 20px; box-shadow: 0 4px 12px #0002; }.sg-item { width: 100%; text-align: left; border: 0; border-radius: 12px; background: transparent; color: var(--md-on-surface); padding: 12px 16px; min-height: 48px; font: inherit; cursor: pointer; }.sg-item:hover, .sg-item.active { background: var(--md-primary-container); color: var(--md-on-primary-container); }
.hotline { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-top: 12px; font-size: 14px; color: var(--md-on-surface-variant); }.hot-item, .text-button { border: 0; background: transparent; color: var(--md-primary); font: inherit; padding: 10px 16px; min-height: 44px; border-radius: 999px; cursor: pointer; }.text-button:hover, .hot-item:hover { background: var(--md-primary-container); }.dynline { display: flex; align-items: flex-start; gap: 16px; margin-top: 16px; }.filter-label { font-size: 14px; padding-top: 12px; flex-shrink: 0; }
.results { margin-top: 32px; }.sec-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 16px; }.sec-head h2 { font-size: 22px; font-weight: 500; margin: 0; }.result-count, .status, .card-meta { color: var(--md-on-surface-variant); font-size: 14px; }.scrolls { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }.scroll { display: flex; flex-direction: column; padding: 24px; min-height: 220px; border: 1px solid var(--md-outline); border-radius: 24px; background: var(--md-surface); color: var(--md-on-surface); text-decoration: none; transition: background 150ms, border-color 150ms; overflow-wrap: anywhere; }.scroll:hover { background: var(--md-surface-container); border-color: var(--md-primary); }.scroll h3, .featured h3 { font-size: 22px; font-weight: 500; margin: 12px 0; }.sv, .feature-verse { font-family: var(--f-serif); line-height: 2; margin: 0 0 16px; }.sv span, .feature-verse span { display: block; }.goto { color: var(--md-primary); margin-top: auto; font-size: 14px; }.error-state { display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; margin: 12px 0; color: var(--md-error); border: 1px solid var(--md-error); border-radius: 16px; }.empty-state { text-align: center; padding: 48px 16px; color: var(--md-on-surface-variant); }
.pager { display: flex; justify-content: center; flex-wrap: wrap; gap: 8px; margin-top: 24px; }.pager button { min-width: 44px; min-height: 44px; padding: 8px 12px; border-radius: 999px; border: 1px solid var(--md-outline); color: var(--md-on-surface); background: var(--md-surface); font: inherit; cursor: pointer; }.pager button[aria-current="page"] { background: var(--md-primary-container); color: var(--md-on-primary-container); border-color: var(--md-primary); }
.featured { margin-top: 40px; padding: 24px; border-radius: 24px; background: var(--md-primary-container); color: var(--md-on-primary-container); }.feature-body { display: grid; grid-template-columns: 1fr 1fr; gap: 32px; }.feature-note { font-size: 15px; line-height: 2; align-self: center; }.hero-actions { display: flex; flex-wrap: wrap; gap: 8px; }.quote { text-align: center; padding: 40px 16px 16px; }.quote blockquote { font-family: var(--f-serif); font-size: 24px; line-height: 1.8; margin: 0; }.quote cite { display: block; color: var(--md-on-surface-variant); font-size: 14px; margin: 12px 0; font-style: normal; }.foot { color: var(--md-on-surface-variant); border-top: 1px solid var(--md-outline); margin-top: 32px; padding-top: 24px; font-size: 14px; }
button:disabled { opacity: .5; cursor: default; }button:focus-visible, a:focus-visible, input:focus-visible { outline: 3px solid var(--md-primary); outline-offset: 3px; }
@media (max-width: 720px) { .poetry-content { padding: 24px 16px 32px; }.search-panel { padding: 16px; }.searchline { gap: 8px; }.searchline input { padding: 12px 16px; }.sbtn { padding: 12px 16px; }.suggest-pop { right: 80px; }.dynline { flex-direction: column; gap: 8px; }.filter-label { padding-top: 0; }.scrolls, .feature-body { grid-template-columns: 1fr; }.feature-body { gap: 8px; }.scroll { min-height: 200px; }.featured { padding: 20px; }.pager { gap: 4px; }.pager button { padding: 8px 10px; } }
@media (prefers-reduced-motion: reduce) { .scroll { transition: none; } }
</style>
