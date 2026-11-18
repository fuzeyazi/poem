<template>
  <div>
    <AppNav />
    <div class="wrap">
      <el-tabs v-model="tab" class="uc-tabs">
        <!-- 个人信息 -->
        <el-tab-pane label="个人信息" name="info">
          <div class="inset uc-block" v-loading="infoLoading">
            <div class="uc-row"><span class="k">用户名</span><span class="v">{{ info.username || '—' }}</span></div>
            <div class="uc-row"><span class="k">昵称</span><span class="v">{{ info.name || '—' }}</span></div>
            <div class="uc-row"><span class="k">性别</span><span class="v">{{ info.sex || '—' }}</span></div>
            <div class="uc-row"><span class="k">邮箱</span><span class="v">{{ info.email || '—' }}</span></div>
            <div class="uc-row"><span class="k">手机</span><span class="v">{{ info.phone || '—' }}</span></div>
            <div class="uc-row"><span class="k">学历</span><span class="v">{{ info.degree || '—' }}</span></div>
            <el-button class="edit-btn" @click="openEdit">编 辑</el-button>
          </div>
        </el-tab-pane>

        <!-- 收藏 -->
        <el-tab-pane label="我的收藏" name="collect">
          <div class="sub-tabs">
            <button type="button" :class="{on: ctab==='poem'}" :aria-pressed="ctab==='poem'" @click="ctab='poem'">诗词 ({{ poems.length }})</button>
            <button type="button" :class="{on: ctab==='rhesis'}" :aria-pressed="ctab==='rhesis'" @click="ctab='rhesis'">名句 ({{ rhesis.length }})</button>
          </div>
          <div v-loading="collectLoading">
            <template v-if="ctab==='poem'">
              <div v-for="p in poems" :key="p.id" class="poem-card" @click="$router.push({name:'poem-detail',params:{title:p.title},query:{id:p.id}})">
                <div class="pt">{{ p.title }}</div>
                <div class="pmeta"><span class="dy">{{ p.dynasty }}</span> · {{ p.writer }}</div>
                <div class="pcontent">{{ clean(p.content) }}</div>
              </div>
              <div v-if="!poems.length" class="hint">尚无收藏诗词</div>
            </template>
            <template v-else>
              <blockquote v-for="r in rhesis" :key="r.id" class="rhesis-item">
                <p class="r-name">{{ r.name }}</p><p class="muted r-from">— {{ r.fromm || '佚名' }}</p>
              </blockquote>
              <div v-if="!rhesis.length" class="hint">尚无收藏名句</div>
            </template>
          </div>
        </el-tab-pane>

        <!-- 诗集本 -->
        <el-tab-pane label="诗集本" name="book">
          <div class="book-bar">
            <el-button @click="showAddBook=true">＋ 新建诗集</el-button>
            <span class="muted">共 {{ books.length }} 本</span>
          </div>
          <div class="writers-grid">
            <div v-for="b in books" :key="b.bookid" class="writer-card" @click="openBook(b)">
              <div class="b-name">{{ b.bookname }}</div>
              <div class="w-intro ell2">{{ b.description || '—' }}</div>
              <div class="muted">{{ b.sum || 0 }} 篇 · {{ b.end ? '已完结' : '进行中' }}</div>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- 编辑资料弹窗 -->
    <el-dialog v-model="showEdit" title="编辑个人信息" width="min(480px, calc(100vw - 32px))">
      <el-form :model="editForm" label-position="top" @submit.prevent="saveEdit" :aria-busy="editPending">
        <el-form-item label="昵称"><el-input v-model="editForm.name" /></el-form-item>
        <el-form-item label="性别"><el-radio-group v-model="editForm.sex"><el-radio value="男">男</el-radio><el-radio value="女">女</el-radio></el-radio-group></el-form-item>
        <el-form-item label="邮箱" :error="editEmailError"><el-input v-model="editForm.email" autocomplete="email" inputmode="email" @input="editEmailError = ''" /></el-form-item>
        <el-form-item label="手机"><el-input v-model="editForm.phone" /></el-form-item>
        <el-form-item label="学历"><el-input v-model="editForm.degree" /></el-form-item>
      </el-form>
      <p v-if="editError" class="form-error" role="alert">{{ editError }}</p>
      <template #footer><el-button @click="showEdit=false" :disabled="editPending">取消</el-button><el-button type="primary" @click="saveEdit" :loading="editPending" :disabled="editPending">{{ editPending ? '保存中…' : '保存' }}</el-button></template>
    </el-dialog>

    <!-- 新建诗集弹窗 -->
    <el-dialog v-model="showAddBook" title="新建诗集" width="min(480px, calc(100vw - 32px))">
      <el-form :model="bookForm" label-position="top" @submit.prevent="saveBook" :aria-busy="bookPending">
        <el-form-item label="诗集名称" :error="bookNameError"><el-input v-model="bookForm.bookname" @input="bookNameError = ''" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="bookForm.description" type="textarea" /></el-form-item>
      </el-form>
      <p v-if="bookError" class="form-error" role="alert">{{ bookError }}</p>
      <template #footer><el-button @click="showAddBook=false" :disabled="bookPending">取消</el-button><el-button type="primary" @click="saveBook" :loading="bookPending" :disabled="bookPending">{{ bookPending ? '创建中…' : '创建' }}</el-button></template>
    </el-dialog>

    <!-- 诗集详情弹窗: 今日任务 + 复习曲线 + 诗列表 -->
    <el-dialog v-model="showBook" :title="currentBook?.bookname" width="min(640px, calc(100vw - 32px))" @open="onBookOpen">
      <div class="book-today" v-if="todayList.length">
        <div class="lab">今 日 应 复 习 · {{ todayList.length }} 首</div>
        <div v-for="t in todayList" :key="t.poemid" class="mini-poem today-item">
          <span class="ti-text" @click="$router.push({name:'poem-detail',params:{title:t.title},query:{id:t.poemid}})">
            {{ t.title }} · {{ t.writer }} <span class="muted">{{ t.dueStage }}</span>
          </span>
          <el-button size="small" type="primary" :loading="reciting === t.poemid" @click="markRecited(t)">背诵完成</el-button>
        </div>
        <div class="muted" style="font-size:12px;margin-top:6px">背诵完成即推进艾宾浩斯轮次（1/3/7/14/30天），全部完成后今日任务清空</div>
      </div>
      <div class="book-today" v-else-if="!planLoading"><div class="lab muted">今 日 无 到 期</div></div>

      <div class="lab" style="margin-top:14px">复 习 曲 线 · 7 日</div>
      <div ref="chartEl" class="plan-chart" v-loading="planLoading"></div>

      <div class="lab" style="margin-top:14px">诗 集 内 · {{ bookPoems.length }} 首</div>
      <div v-for="p in bookPoems" :key="p.id" class="mini-poem" @click="$router.push({name:'poem-detail',params:{title:p.title},query:{id:p.id}})">{{ p.title }} · {{ p.writer }}</div>
      <div v-if="!bookPoems.length" class="hint">诗集中暂无诗作</div>
      <template #footer>
        <el-button @click="reviewBook" :disabled="!bookPoems.length">重新排期(开始复习)</el-button>
        <el-button type="primary" @click="showBook=false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { ElMessage } from 'element-plus'
import AppNav from '@/components/AppNav.vue'
import { getMessageById, updateMessageById, getCollectPoems, getCollectRhesis, bookShow, bookAdd, bookShowPoem, bookStartReview, bookShowPlan, bookToday, reciteDone } from '@/api/user'
import { useUserStore } from '@/store/user'
import { useTheme } from '@/composables/useTheme'

const userStore = useUserStore()
const tab = ref('info')
const ctab = ref('poem')
const infoLoading = ref(false)
const info = ref<any>({})
const poems = ref<any[]>([])
const rhesis = ref<any[]>([])
const collectLoading = ref(false)

const showEdit = ref(false)
const editForm = reactive({ name: '', sex: '男', email: '', phone: '', degree: '', username: '' })
const editPending = ref(false)
const editError = ref('')
const editEmailError = ref('')
const openEdit = () => { Object.assign(editForm, info.value); editError.value = ''; editEmailError.value = ''; showEdit.value = true }
const saveEdit = async () => {
  if (editPending.value) return
  editError.value = ''
  editEmailError.value = !editForm.email?.trim() || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(editForm.email.trim()) ? '' : '请输入有效邮箱'
  if (editEmailError.value) return
  editPending.value = true
  try { await updateMessageById({ ...editForm }); ElMessage.success('已保存'); showEdit.value = false; await loadInfo() }
  catch { editError.value = '保存失败，请重试，编辑内容已保留' }
  finally { editPending.value = false }
}

const books = ref<any[]>([])
const showAddBook = ref(false)
const bookForm = reactive({ bookname: '', description: '' })
const bookPending = ref(false)
const bookError = ref('')
const bookNameError = ref('')
const saveBook = async () => {
  if (bookPending.value) return
  bookError.value = ''
  bookNameError.value = bookForm.bookname.trim() ? '' : '请输入诗集名称'
  if (bookNameError.value) return
  bookPending.value = true
  try { await bookAdd({ ...bookForm, bookname: bookForm.bookname.trim() }); ElMessage.success('已创建'); showAddBook.value = false; bookForm.bookname=''; bookForm.description=''; await loadBooks() }
  catch { bookError.value = '创建失败，请重试，草稿已保留' }
  finally { bookPending.value = false }
}

const showBook = ref(false)
const currentBook = ref<any>(null)
const bookPoems = ref<any[]>([])
const openBook = async (b: any) => {
  currentBook.value = b; showBook.value = true; bookPoems.value = []
  await onBookOpen()
}
/* 曲线/今日任务: showplan(按日聚合)+today */
const planLoading = ref(false)
const planDays = ref<any[]>([])
const todayList = ref<any[]>([])
const onBookOpen = async () => {
  if (!currentBook.value) return
  planLoading.value = true
  // 以 bookid 为准重新取书(列表刷新后对象引用会失效)
  try { const bs = await bookShow(); currentBook.value = (bs || []).find(b => b.bookid === currentBook.value.bookid) || currentBook.value } catch {}
  try {
    const bid = currentBook.value.bookid
    const [plan, today] = await Promise.all([
      bookShowPlan(bid).catch(() => []),
      bookToday(bid).catch(() => []),
    ])
    planDays.value = (plan || []).slice(-7)
    todayList.value = today || []
  } catch { planDays.value = []; todayList.value = [] } finally { planLoading.value = false }
}
/* 背诵完成: 走query/end推进SRS轮次(1/3/7/14/30天), 刷新今日+曲线 */
const reciting = ref<number | null>(null)
const markRecited = async (t: any) => {
  reciting.value = t.poemid
  try {
    await reciteDone(t.poemid)
    ElMessage.success(`已推进轮次，下次复习按间隔排期`)
    await onBookOpen()
  } catch { /* 请求层统一显示失败提示。 */ } finally { reciting.value = null }
}

/* ECharts 复习曲线: 计划首数折线+已完成散点, 暗色金线主题 */
const chartEl = ref<HTMLElement | null>(null)
let chart: any = null
const { theme } = useTheme()
const renderChart = async () => {
  if (!chartEl.value) return
  const echarts = await import('echarts/core')
  const { LineChart, ScatterChart } = await import('echarts/charts')
  const { GridComponent, TooltipComponent, LegendComponent } = await import('echarts/components')
  const { CanvasRenderer } = await import('echarts/renderers')
  echarts.use([LineChart, ScatterChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])
  if (!chart) chart = echarts.init(chartEl.value)
  const tokens = getComputedStyle(document.documentElement)
  const palette = (name: string) => tokens.getPropertyValue(name).trim()
  const primary = palette('--md-primary')
  const outline = palette('--md-outline-variant')
  const text = palette('--md-on-surface-variant')
  const days = planDays.value
  const labels = days.map((d: any) => { const dt = new Date(d.date); return `${dt.getMonth() + 1}/${dt.getDate()}` })
  const planned = days.map((d: any) => new Set(d.sum || []).size)
  const doneIdx: number[] = []
  days.forEach((d: any, i: number) => { if ((d.isReview || []).some((v: number) => v === 1)) doneIdx.push(i) })
  chart.setOption({
    backgroundColor: 'transparent',
    grid: { left: 34, right: 16, top: 28, bottom: 26 },
    tooltip: { trigger: 'axis', backgroundColor: palette('--md-surface-container-high'), borderColor: outline, textStyle: { color: palette('--md-on-surface'), fontSize: 14 } },
    xAxis: { type: 'category', data: labels, axisLine: { lineStyle: { color: outline } }, axisLabel: { color: text, fontSize: 13 } },
    yAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: outline } }, axisLabel: { color: text, fontSize: 13 } },
    series: [
      {
        name: '计划首数', type: 'line', data: planned, smooth: true,
        lineStyle: { color: primary, width: 2 }, itemStyle: { color: primary },
        symbolSize: 7, areaStyle: { color: primary, opacity: 0.12 },
      },
      {
        name: '已完成', type: 'scatter',
        data: doneIdx.map((i) => [labels[i], planned[i]]),
        itemStyle: { color: palette('--md-success') }, symbolSize: 10,
      },
    ],
  })
}
// 数据到位/弹窗展开后渲染(nextTick等容器有宽)
import { nextTick } from 'vue'
watch([planDays, showBook, theme], async ([, open]) => {
  if (!open) return
  await nextTick()
  if (planDays.value.length) renderChart()
})
const resizeChart = () => chart?.resize()
onMounted(() => window.addEventListener('resize', resizeChart))
onBeforeUnmount(() => { window.removeEventListener('resize', resizeChart); chart?.dispose(); chart = null })
const reviewBook = async () => {
  if (!currentBook.value) return
  try {
    await bookStartReview(currentBook.value.bookid, 1)
    ElMessage.success('已重新排期：学习日从今天起')
    await onBookOpen()
  } catch { /* 请求层统一显示失败提示。 */ }
}

const clean = (s?: string) => (s || '').replace(/<br\s*\/?>/gi, '\n').replace(/\r\n/g, '\n').trim()
const loadInfo = async () => { infoLoading.value = true; try { info.value = await getMessageById() } finally { infoLoading.value = false } }
const loadCollect = async () => {
  collectLoading.value = true
  try {
    poems.value = (await getCollectPoems()) || []
    rhesis.value = (await getCollectRhesis(userStore.userId || 0)) || []
  } finally { collectLoading.value = false }
}
const loadBooks = async () => { try { books.value = (await bookShow()) || [] } catch {} }

watch(tab, (t) => { if (t === 'collect') loadCollect(); if (t === 'book') loadBooks() })
onMounted(loadInfo)
</script>

<style scoped>
.uc-tabs { margin-top: 8px; }
:deep(.el-tabs__item) { font-family: inherit; letter-spacing: normal; font-size: 15px; }
.uc-block { padding: 28px 32px; position: relative; }
.uc-row { display: flex; padding: 12px 0; border-bottom: 1px dashed var(--md-outline-variant); }
.uc-row .k { width: 90px; color: var(--md-on-surface-variant); letter-spacing: normal; }
.uc-row .v { flex: 1; color: var(--md-on-surface); }
.edit-btn { margin-top: 24px; background: var(--md-primary); border: none; color: var(--md-on-primary); letter-spacing: normal; }
.edit-btn:hover { background: var(--md-primary); }
.sub-tabs { display: flex; gap: 8px; margin-bottom: 18px;  flex-wrap: wrap; }
.sub-tabs button { cursor: pointer; font-size: 14px; letter-spacing: normal; color: var(--md-on-surface-variant); padding-bottom: 4px; border-bottom: 2px solid transparent;  padding: 8px 16px;  min-height: 44px;  border-radius: 999px;  border: 1px solid var(--md-outline);  background: transparent; }
.sub-tabs button.on {  background: var(--md-primary-container); ;
  color: var(--md-on-primary-container);
  border-color: var(--md-primary-container);
}
.book-bar { display: flex; align-items: center; gap: 16px; margin: 12px 0 20px; }
.b-name { font-size: 18px; letter-spacing: normal; color: var(--md-on-surface); margin-bottom: 8px; }
.mini-poem { padding: 10px 0; border-bottom: 1px dashed var(--md-outline-variant); cursor: pointer; letter-spacing: normal; }
.mini-poem:hover { color: var(--md-primary); }
.rhesis-item { break-inside: avoid; margin: 0 0 16px; padding: 16px 20px; background: var(--md-surface-container-lowest); border: 1px solid var(--md-outline-variant); border-radius: 24px; box-shadow: var(--shadow-sm); }
.r-name { font-size: 17px; line-height: 1.8; letter-spacing: normal; color: var(--md-on-surface); margin: 0 0 6px; }
.r-from { margin: 0; font-size: 13px; }

.book-today { padding: 8px 10px; border: 1px dashed var(--md-outline-variant); border-radius: 12px; margin-bottom: 6px; }
.book-today .lab { font-size: 13px; color: var(--md-primary); margin-bottom: 6px; letter-spacing: normal; }
.chart-wrap { padding: 8px 4px 2px; }
.plan-chart { width: 100%; height: 220px; }
.chart-legend { font-size: 13px; margin-top: 2px; }

.today-item { display: flex; justify-content: space-between; align-items: center; gap: 8px;  flex-wrap: wrap; }
.ti-text { cursor: pointer; }
.ti-text:hover { color: var(--md-primary); }

:deep(.el-button) { min-height: 44px; border-radius: 999px; font-family: var(--f-sans); letter-spacing: normal; }
:deep(.el-input__wrapper) { min-height: 48px; border-radius: 12px; }
:deep(.el-textarea__inner) { border-radius: 12px; font-size: 15px; }
:deep(.el-tabs__item) { min-height: 48px; font-family: var(--f-sans); letter-spacing: normal; }
:deep(.el-dialog) { max-width: calc(100vw - 32px); border-radius: 28px; }
.form-error { font-size: 14px; line-height: 1.5; color: var(--md-error); background: var(--md-error-container); border-radius: 12px; padding: 12px 16px; }

.r-name { font-family: var(--f-serif); } .uc-row .v { min-width: 0; overflow-wrap: anywhere; } .writers-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr)); gap: 16px; } .writer-card { padding: 24px; border-radius: 24px; border: 1px solid var(--md-outline-variant); background: var(--md-surface-container-lowest); } @media (max-width: 600px) { .uc-block { padding: 20px; } .book-bar { flex-wrap: wrap; } }
</style>

