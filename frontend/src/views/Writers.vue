<template>
  <div>
    <AppNav />
    <div class="wrap">
      <div class="page-head">
        <span class="labbtn">诗 人</span>
        <span class="muted">共 {{ count }} 位 · 随机展示 5 位</span>
        <el-button class="shuffle" size="small" @click="onDynasty(dynasty)">换一批 ↻</el-button>
      </div>

      <AgeTabs :dynasties="dynasties" v-model="dynasty" @change="onDynasty" />

      <!-- 朝代筛选时前端切片分页(全量数据80ms一次到位,翻页零延迟) -->
      <div class="writers-grid" v-loading="loading">
        <div v-for="w in pagedList" :key="w.name" class="writer-card" @click="openWriter(w.name || '')">
          <div class="avatar">
            <img v-if="w.headImageUrl" :src="w.headImageUrl" :alt="w.name" @error="onErr" />
            <span v-else class="ph">{{ (w.name||'').slice(0,1) }}</span>
          </div>
          <div class="w-name">{{ w.name }}</div>
          <div class="w-intro ell2">{{ w.simpleIntro || '—' }}</div>
        </div>
      </div>
      <div v-if="!loading && !list.length" class="empty-state muted">无名可寻</div>
      <div class="pager-row" v-if="dynasty && list.length > pageSize">
        <el-pagination layout="prev, pager, next, total" :total="list.length" :page-size="pageSize"
          v-model:current-page="page" background @current-change="onPageChange" />
      </div>
    </div>

    <!-- 诗人弹窗 -->
    <el-dialog v-model="showDlg" :title="current" width="min(640px, calc(100vw - 32px))" align-center>
      <div v-if="currentWriter">
        <img v-if="currentWriter.headImageUrl" :src="currentWriter.headImageUrl" class="dlg-avatar" />
        <p class="muted" v-if="currentWriter.simpleIntro">{{ currentWriter.simpleIntro }}</p>
        <div class="detail-section" v-if="parsedDetail['介绍']"><div class="lab">简 · 介</div><div class="ct">{{ parsedDetail['介绍'] }}</div></div><div class="detail-section" v-if="parsedDetail['词风简介']"><div class="lab">词 · 风</div><div class="ct">{{ parsedDetail['词风简介'] }}</div></div><div class="detail-section" v-if="parsedDetail['生卒年考']"><div class="lab">生 · 平</div><div class="ct">{{ parsedDetail['生卒年考'] }}</div></div>
        <div class="poems-list">
          <div class="lab">作 · 品</div>
          <div v-for="p in poems" :key="p.id" class="mini-poem" @click="goPoem(p)">{{ p.title }}</div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppNav from '@/components/AppNav.vue'
import AgeTabs from '@/components/AgeTabs.vue'
import { getWriterCount, getAllDynasties, getRandomWriters, getWritersByDynastyFull, getImageAndSimpleIntro, getDetailIntro, getPoemsByWriter } from '@/api/writer'
import type { WriterVo } from '@/api/types'
import type { Poem } from '@/api/types'

const router = useRouter()
const count = ref(0)
const dynasties = ref<string[]>([])
const dynasty = ref('')
const list = ref<WriterVo[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = 24
const pagedList = computed(() => {
  if (!dynasty.value) return list.value          // "全部"仍是随机5位,无需分页
  return list.value.slice((page.value - 1) * pageSize, page.value * pageSize)
})
const onPageChange = () => { window.scrollTo({ top: 0, behavior: 'smooth' }) }

// 弹窗
const showDlg = ref(false)
const current = ref('')
const currentWriter = ref<WriterVo | null>(null)
const detail = ref('')
const parsedDetail = computed(() => { try { return JSON.parse(detail.value) } catch { return {} } })
const poems = ref<Poem[]>([])

const onErr = (e: Event) => { (e.target as HTMLImageElement).style.display = 'none' }
const onDynasty = async (d: string) => {
  loading.value = true
  try {
    // 2026-10-25 backend代改: 原270次逐个画像请求(N+1)致Promise.all死锁卡死,改单次批量接口
    if (d) { page.value = 1; list.value = await getWritersByDynastyFull(d) }
    else { list.value = await getRandomWriters() }
  } catch { list.value = [] } finally { loading.value = false }
}
const openWriter = async (name: string) => {
  current.value = name; showDlg.value = true
  currentWriter.value = null; detail.value = ''; poems.value = []
  try { currentWriter.value = await getImageAndSimpleIntro(name) } catch {}
  try { detail.value = await getDetailIntro(name) } catch {}
  try { poems.value = (await getPoemsByWriter(name)) || [] } catch {}
}
const goPoem = (p: any) => { showDlg.value = false; router.push({ name: 'poem-detail', params: { title: p.title }, query: { id: p.id } }) }

onMounted(async () => {
  try { count.value = await getWriterCount() } catch {}
  try { dynasties.value = await getAllDynasties() } catch {}
  await onDynasty('')
})
</script>

<style scoped>
.page-head { display: flex; align-items: center; gap: 18px; margin-bottom: 20px;  flex-wrap: wrap; }
.labbtn { font-size: 28px; letter-spacing: normal; color: var(--md-on-surface); border-left: 3px solid var(--md-primary); padding-left: 12px;  border: none;  padding: 0; }
.shuffle { margin-left: 4px; }
.writers-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px,1fr)); gap: 16px; margin-top: 24px; }
.writer-card { padding: 24px 16px; background: var(--md-surface-container-lowest); border: 1px solid var(--md-outline-variant); border-radius: 24px; cursor: pointer; text-align: center; box-shadow: var(--shadow-sm); transition: background 150ms, border-color 150ms, box-shadow 150ms; }
.writer-card:hover { transform: translateY(-3px); box-shadow: var(--shadow-sm); border-color: var(--md-primary); }
.avatar { width: 76px; height: 76px; margin: 0 auto 12px; border-radius: 50%; overflow: hidden; background: var(--md-surface-container-low); display:flex; align-items:center; justify-content:center; border: 1px solid var(--md-outline); }
.avatar img { width: 100%; height: 100%; object-fit: cover; }
.avatar .ph { font-size: 30px; color: var(--md-on-surface-variant); }
.w-name { font-size: 18px; letter-spacing: normal; color: var(--md-on-surface); margin-bottom: 8px; }
.w-intro { font-size: 14px; color: var(--md-on-surface-variant); line-height: 1.8; }
.ell2 { display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }
/* dialog inner */
.dlg-avatar { width: 100px; height: 100px; border-radius: 50%; object-fit: cover; display:block; margin: 0 auto 16px; border:1px solid var(--md-outline); }
.poems-list { margin-top: 20px; }
.poems-list .lab { font-size: 13px; letter-spacing: normal; color: var(--md-primary); margin-bottom: 8px; }
.mini-poem { padding: 8px 0; border-bottom: 1px dashed var(--md-outline-variant); cursor: pointer; letter-spacing: normal; }
.mini-poem:hover { color: var(--md-primary); }
:deep(.el-dialog) { border-radius: 12px; }
:deep(.el-dialog__header) { padding: 20px 24px; text-align: center; }
.ct { white-space: pre-line; line-height: 2; }
:deep(.el-dialog__title) { font-family: var(--f-sans); letter-spacing: normal; font-size: 20px; }

.pager-row { display: flex; justify-content: center; margin: 28px 0 8px; }

:deep(.el-button) { min-height: 44px; border-radius: 999px; font-family: var(--f-sans); letter-spacing: normal; }
:deep(.el-input__wrapper) { min-height: 48px; border-radius: 12px; }
:deep(.el-textarea__inner) { border-radius: 12px; font-size: 15px; }
:deep(.el-tabs__item) { min-height: 48px; font-family: var(--f-sans); letter-spacing: normal; }
:deep(.el-dialog) { max-width: calc(100vw - 32px); border-radius: 28px; }
.form-error { font-size: 14px; line-height: 1.5; color: var(--md-error); background: var(--md-error-container); border-radius: 12px; padding: 12px 16px; }

</style>

