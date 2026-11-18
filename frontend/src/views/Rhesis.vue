<template>
  <div>
    <AppNav />
    <div class="wrap">
      <div class="page-head">
        <h2 class="labbtn">名 句</h2>
        <span class="muted">共 {{ count }} 句</span>
      </div>

      <div class="searchbox">
        <input v-model="keyword" placeholder="搜索名句，如「明月」「江山」" @keyup.enter="onSearch" />
        <button class="btn" @click="onSearch">检 索</button>
      </div>

      <!-- 名句墙（后端接口已补 LIMIT；前端仍分片渲染防数据量反复） -->
      <div class="wall" v-loading="loading">
        <blockquote
          v-for="(r, i) in shownList"
          :key="r.id || i"
          v-reveal="(i % 3) * 70"
          class="qitem"
        >
          <p class="q">{{ r.name }}</p>
          <div class="q-foot">
            <p class="from">{{ r.fromm || '佚名' }}</p>
            <button class="make-card-btn" @click.stop="openQuoteCard(r)" title="将此名句制为古典卡片">
              🔖 制为卡片
            </button>
          </div>
        </blockquote>
        <div v-if="!loading && !list.length" class="empty-state muted">未觅得相关名句</div>
      </div>

      <!-- 诗词名句卡片生成弹窗 -->
      <PoemCardModal
        v-if="selectedQuote"
        v-model:visible="cardModalVisible"
        :poem="quoteCardData"
      />

      <div class="center" style="margin-top:40px">
        <button v-if="list.length > shown" class="rbtn" @click="shown += 60">
          再展六十 · 已见 {{ shown }}/{{ list.length }}
        </button>
        <button class="rbtn" @click="loadRandom">再掷一回 · 另觅佳句</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import AppNav from '@/components/AppNav.vue'
import PoemCardModal from '@/components/card/PoemCardModal.vue'
import { getRhesisCount, getRhesisByKey, getRandomRhesis } from '@/api/rhesis'
import type { Rhesis } from '@/api/types'

const count = ref(0)
const keyword = ref('')
const list = ref<Rhesis[]>([])
const loading = ref(false)
const searched = ref(false)
// 后端随机接口已补 LIMIT，前端仍分片渲染，点按钮继续加载
const shown = ref(60)
const shownList = computed(() => list.value.slice(0, shown.value))

const loadRandom = async () => { searched.value = false; shown.value = 60; try { list.value = (await getRandomRhesis()) || [] } catch {} }
const onSearch = async () => {
  if (!keyword.value.trim()) return
  loading.value = true; searched.value = true; shown.value = 60
  try { list.value = (await getRhesisByKey(keyword.value.trim())) || [] } finally { loading.value = false }
}

/* 诗词名句卡片生成器状态 */
const cardModalVisible = ref(false)
const selectedQuote = ref<Rhesis | null>(null)
const quoteCardData = computed(() => {
  if (!selectedQuote.value) {
    return { title: '名句', writer: '佚名', content: '' }
  }
  const rawFrom = selectedQuote.value.fromm || ''
  const titleMatch = rawFrom.match(/《([^》]+)》/)
  const title = titleMatch ? titleMatch[1] : (rawFrom ? rawFrom.slice(0, 10) : '名句集萃')
  const writer = rawFrom.replace(/《[^》]+》/g, '').replace(/[·\s]/g, '').trim() || '佚名'
  return {
    title,
    writer,
    content: selectedQuote.value.name || ''
  }
})

const openQuoteCard = (r: Rhesis) => {
  selectedQuote.value = r
  cardModalVisible.value = true
}

onMounted(async () => {
  try { count.value = await getRhesisCount() } catch {}
  await loadRandom()
})
</script>

<style scoped>
.page-head { display: flex; align-items: baseline; gap: 18px; margin-bottom: 10px; }
.labbtn { font-family: var(--f-sans); font-weight: 500; font-size: 28px; letter-spacing: normal; color: var(--md-on-surface); margin: 0; }
.wall { columns: 2 340px; column-gap: 24px; margin-top: 24px; }
.qitem {
  break-inside: avoid; margin: 0 0 16px; padding: 24px;
  border-top: 1px solid var(--md-outline-variant);
 background: var(--md-surface-container-lowest);  border: 1px solid var(--md-outline-variant);  border-radius: 24px; }
.qitem:nth-child(3n+2) { text-align: center; }
.qitem:nth-child(3n) { text-align: right; }
.q {
  font-family: var(--f-sans); font-weight: 500;
  font-size: 19px; line-height: 2; letter-spacing: normal;
  color: var(--md-on-surface); margin: 0;
}
.q-foot {
  margin: 12px 0 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.from { margin: 0; font-size: 13px; font-weight: 300; letter-spacing: normal; color: var(--md-on-surface-variant); }
.make-card-btn {
  background: transparent;
  border: 1px solid var(--md-outline-variant);
  color: var(--md-on-surface-variant);
  font-family: var(--f-sans);
  font-size: 13px;
  padding: 3px 10px;
  border-radius: 999px;
  cursor: pointer;
  letter-spacing: normal;
  opacity: 1;
  transition: all 0.2s;
 min-height: 44px; }
.make-card-btn:hover {
  opacity: 1;
  color: var(--md-primary);
  border-color: var(--md-primary);
}
.rbtn {
  padding: 10px 28px; background: transparent; border: 1px solid var(--md-outline); border-radius: 999px;
  font-family: var(--f-sans); font-size: 14px; letter-spacing: normal; color: var(--md-on-surface);
  cursor: pointer; transition: background 150ms, border-color 150ms, box-shadow 150ms; margin: 0 8px;
 min-height: 48px; }
.rbtn:hover { background: var(--md-primary); color: var(--md-on-primary); border-color: var(--md-on-surface); }

:deep(.el-button) { min-height: 44px; border-radius: 999px; font-family: var(--f-sans); letter-spacing: normal; }
:deep(.el-input__wrapper) { min-height: 48px; border-radius: 12px; }
:deep(.el-textarea__inner) { border-radius: 12px; font-size: 15px; }
:deep(.el-tabs__item) { min-height: 48px; font-family: var(--f-sans); letter-spacing: normal; }
:deep(.el-dialog) { max-width: calc(100vw - 32px); border-radius: 28px; }
.form-error { font-size: 14px; line-height: 1.5; color: var(--md-error); background: var(--md-error-container); border-radius: 12px; padding: 12px 16px; }

.q { font-family: var(--f-serif); } .q-foot { gap: 12px; flex-wrap: wrap; } .center { display: flex; justify-content: center; flex-wrap: wrap; gap: 12px; } .rbtn { margin: 0; }
</style>
