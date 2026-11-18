<template>
  <div class="console-page">
    <AppNav />
    <div class="cs-container">
      <!-- 页面顶栏：工坊标头与状态门 -->
      <header class="cs-header">
        <div class="cs-header-left">
          <div class="title-row">
            <h1 class="cs-title">管理控制台</h1>
            <span class="meta-badge">SYSTEM OPERATIONS // TELEMETRY & AUDIT</span>
          </div>
          <p class="cs-desc">飞轮闭环审核 · 成本核算 · 工具与安全审计 · 多维运维观测</p>
        </div>

        <div class="cs-header-right">
          <template v-if="admin.token">
            <div class="operator-pill">
              <span class="dot-online"></span>
              <span class="operator-text">{{ admin.userName || '系统管理员' }}</span>
            </div>
            <a href="http://localhost:8000/nav" target="_blank" rel="noopener noreferrer" class="cs-nav-btn" title="查看 FastAPI / 外部系统导航">
              <span>运维导航</span>
              <svg class="out-icon" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                <polyline points="15 3 21 3 21 9" />
                <line x1="10" y1="14" x2="21" y2="3" />
              </svg>
            </a>
            <a href="http://localhost:3000" target="_blank" rel="noopener noreferrer" class="cs-nav-btn" title="打开 Langfuse LLM 观测追踪台">
              <span>Langfuse 观测</span>
              <svg class="out-icon" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                <polyline points="15 3 21 3 21 9" />
                <line x1="10" y1="14" x2="21" y2="3" />
              </svg>
            </a>
            <router-link to="/console/content" class="nav-content-btn">
              <span>内容管理</span>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="9 18 15 12 9 6" />
              </svg>
            </router-link>
            <button class="logout-btn" @click="logoutAdmin">登出</button>
          </template>
        </div>
      </header>

      <!-- 管理员登录门 -->
      <div v-if="!admin.token" class="auth-wrap">
        <div class="auth-card inset" v-loading="loading">
          <div class="auth-header">
            <div class="auth-icon-badge">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
            </div>
            <h2 class="auth-title">操作员验签</h2>
            <p class="auth-desc">飞轮闭环调优 · 成本计量 · 工具审计安全凭证</p>
          </div>

          <form class="auth-form" @submit.prevent="onLogin" :aria-busy="loading">
            <div class="field-group">
              <label class="field-label" for="operator-username">操作员账号</label>
              <el-input id="operator-username" v-model="loginForm.username" autocomplete="username" :disabled="loading" placeholder="请输入管理员用户名" />
            </div>

            <div class="field-group">
              <label class="field-label" for="operator-password">鉴权密钥</label>
              <el-input id="operator-password" v-model="loginForm.password" autocomplete="current-password" :disabled="loading" type="password" show-password placeholder="请输入管理员登录密码" />
            </div>

            <div class="field-group">
              <label class="field-label" for="operator-captcha">图形验证码</label>
              <div class="captcha-row">
                <el-input id="operator-captcha" v-model="loginForm.code" :disabled="loading" autocomplete="off" placeholder="输入图中字符" />
                <button type="button" class="captcha-preview" :disabled="loading" aria-label="刷新验证码" @click="loadCaptcha">
                  <img v-if="captcha" :src="captcha" alt="验证码" class="captcha-img" />
                  <span v-else class="captcha-loading">加载中</span>
                </button>
              </div>
            </div>

            <p v-if="loginError" class="form-error" role="alert">{{ loginError }}</p>
            <button type="submit" class="auth-submit-btn" :disabled="loading">
              <span>{{ loading ? '验证中…' : '验证凭证并进入工作台' }}</span>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="5" y1="12" x2="19" y2="12" />
                <polyline points="12 5 19 12 12 19" />
              </svg>
            </button>
          </form>

          <div class="security-callout">
            <div class="security-badge">SECURITY BOUNDARY</div>
            <p class="security-hint">管理端与用户端密钥隔离：此处登录凭据仅用于飞轮审核、成本报表与工具审计。</p>
          </div>
        </div>
      </div>

      <!-- 主控制台工作区 -->
      <template v-else>
        <!-- 标签导航栏 -->
        <div class="cs-tab-nav">
          <button
            class="cs-tab-btn"
            :class="{ active: tab === 'review' }"
            @click="tab = 'review'"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
              <polyline points="10 9 9 9 8 9" />
            </svg>
            <span>飞轮审核</span>
            <span v-if="reviews.length && reviewStatus === 'pending'" class="tab-count-badge">{{ reviews.length }}</span>
          </button>

          <button
            class="cs-tab-btn"
            :class="{ active: tab === 'cost' }"
            @click="tab = 'cost'"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
              <line x1="12" y1="1" x2="12" y2="23" />
              <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
            </svg>
            <span>成本报表</span>
          </button>

          <button
            class="cs-tab-btn"
            :class="{ active: tab === 'audit' }"
            @click="tab = 'audit'"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            <span>工具审计</span>
          </button>
        </div>

        <!-- 面板 1: 飞轮审核 -->
        <div v-show="tab === 'review'" class="tab-panel">
          <div class="panel-toolbar">
            <div class="filter-cluster">
              <span class="toolbar-label">审核状态</span>
              <div class="segmented-control">
                <button
                  class="seg-item"
                  :class="{ active: reviewStatus === 'pending' }"
                  @click="reviewStatus = 'pending'; loadReview()"
                >
                  <span class="seg-dot dot-pending"></span>
                  待审
                </button>
                <button
                  class="seg-item"
                  :class="{ active: reviewStatus === 'approved' }"
                  @click="reviewStatus = 'approved'; loadReview()"
                >
                  <span class="seg-dot dot-approved"></span>
                  已通过
                </button>
                <button
                  class="seg-item"
                  :class="{ active: reviewStatus === 'rejected' }"
                  @click="reviewStatus = 'rejected'; loadReview()"
                >
                  <span class="seg-dot dot-rejected"></span>
                  已驳回
                </button>
              </div>
            </div>

            <div class="toolbar-right">
              <span class="hint-caption">点击数据行即可调出人工审核与回流面板</span>
              <button class="tool-btn" :disabled="reviewLoading" @click="loadReview">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" :class="{ 'spin-icon': reviewLoading }">
                  <polyline points="23 4 23 10 17 10" />
                  <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
                </svg>
                <span>刷新池</span>
              </button>
            </div>
          </div>

          <div class="table-frame" v-loading="reviewLoading">
            <el-table :data="reviews" size="small" @row-click="openReview" class="craft-table click-table">
              <el-table-column prop="id" label="ID" width="85">
                <template #default="{ row }">
                  <span class="id-pill">#{{ row.id }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="status" label="状态" width="110">
                <template #default="{ row }">
                  <span v-if="row.status === 'pending'" class="status-pill pill-pending">
                    <span class="dot"></span> 待审核
                  </span>
                  <span v-else-if="row.status === 'approved'" class="status-pill pill-approved">
                    <span class="dot"></span> 已通过
                  </span>
                  <span v-else-if="row.status === 'rejected'" class="status-pill pill-rejected">
                    <span class="dot"></span> 已驳回
                  </span>
                  <span v-else class="status-pill">
                    {{ row.status || '—' }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column label="问题摘要" min-width="280">
                <template #default="{ row }">
                  <div class="question-cell">
                    <span class="question-text">{{ questionOf(row) || '（无问法记录）' }}</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column prop="occurrences" label="出现频次" width="105" align="right">
                <template #default="{ row }">
                  <span class="num-badge">{{ row.occurrences ?? 1 }} 次</span>
                </template>
              </el-table-column>
              <el-table-column prop="created_at" label="入池时间" min-width="160" align="right">
                <template #default="{ row }">
                  <span class="time-col mono">{{ row.created_at || '—' }}</span>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>

        <!-- 面板 2: 成本报表 -->
        <div v-show="tab === 'cost'" class="tab-panel">
          <div class="panel-toolbar">
            <div class="filter-cluster">
              <span class="toolbar-label">统计窗口</span>
              <div class="segmented-control">
                <button
                  class="seg-item"
                  :class="{ active: costDays === 7 }"
                  @click="costDays = 7; loadCost()"
                >
                  近 7 天
                </button>
                <button
                  class="seg-item"
                  :class="{ active: costDays === 14 }"
                  @click="costDays = 14; loadCost()"
                >
                  近 14 天
                </button>
                <button
                  class="seg-item"
                  :class="{ active: costDays === 30 }"
                  @click="costDays = 30; loadCost()"
                >
                  近 30 天
                </button>
              </div>
            </div>

            <div class="toolbar-right">
              <div v-if="costTotal" class="total-metric-badge">
                <span class="metric-label">窗口累计核算</span>
                <span class="metric-val mono">${{ costTotal }}</span>
              </div>
              <button class="tool-btn" :disabled="costLoading" @click="loadCost">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" :class="{ 'spin-icon': costLoading }">
                  <polyline points="23 4 23 10 17 10" />
                  <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
                </svg>
                <span>更新报表</span>
              </button>
            </div>
          </div>

          <div class="table-frame" v-loading="costLoading">
            <el-table :data="costRows" size="small" class="craft-table">
              <el-table-column prop="intent" label="交互意图" min-width="150">
                <template #default="{ row }">
                  <span class="intent-pill">{{ row.intent || 'default' }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="model" label="承接模型" min-width="160">
                <template #default="{ row }">
                  <span class="model-pill mono">{{ row.model || '—' }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="calls" label="调用频次" width="100" align="right">
                <template #default="{ row }">
                  <span class="num-cell mono">{{ Number(row.calls || 0).toLocaleString() }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="input" label="输入 Tokens" width="125" align="right">
                <template #default="{ row }">
                  <span class="num-cell mono">{{ Number(row.input || 0).toLocaleString() }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="output" label="输出 Tokens" width="125" align="right">
                <template #default="{ row }">
                  <span class="num-cell mono">{{ Number(row.output || 0).toLocaleString() }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="costUsd" label="估算成本" width="115" align="right">
                <template #default="{ row }">
                  <span class="cost-cell mono">${{ Number(row.costUsd || 0).toFixed(4) }}</span>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>

        <!-- 面板 3: 工具审计 -->
        <div v-show="tab === 'audit'" class="tab-panel">
          <div class="panel-toolbar">
            <div class="filter-cluster">
              <span class="toolbar-label">工具名称</span>
              <div class="search-input-wrap">
                <input
                  v-model="auditTool"
                  placeholder="过滤工具标识，如 get_my_collection"
                  class="craft-input"
                  @keyup.enter="loadAudit"
                />
                <button class="tool-btn" @click="loadAudit">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="11" cy="11" r="8" />
                    <line x1="21" y1="21" x2="16.65" y2="16.65" />
                  </svg>
                  <span>检索</span>
                </button>
              </div>
            </div>

            <div class="toolbar-right">
              <span class="hint-caption">最近 50 条调用记录</span>
              <button class="tool-btn" :disabled="auditLoading" @click="loadAudit">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" :class="{ 'spin-icon': auditLoading }">
                  <polyline points="23 4 23 10 17 10" />
                  <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
                </svg>
                <span>刷新</span>
              </button>
            </div>
          </div>

          <div class="table-frame" v-loading="auditLoading">
            <el-table :data="auditRows" size="small" class="craft-table">
              <el-table-column prop="id" label="ID" width="80">
                <template #default="{ row }">
                  <span class="id-pill">#{{ row.id }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="toolName" label="工具标识" min-width="170">
                <template #default="{ row }">
                  <span class="tool-pill mono">{{ row.toolName }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="source" label="调用源" width="95">
                <template #default="{ row }">
                  <span class="source-tag">{{ row.source || 'agent' }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="status" label="执行状态" width="100">
                <template #default="{ row }">
                  <span v-if="row.status === 'SUCCESS' || row.status === 'OK'" class="status-pill pill-approved">
                    <span class="dot"></span> 正常
                  </span>
                  <span v-else class="status-pill pill-rejected">
                    <span class="dot"></span> {{ row.status || '失败' }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="durationMs" label="耗时" width="95" align="right">
                <template #default="{ row }">
                  <span :class="['num-cell', 'mono', Number(row.durationMs) > 2000 ? 'cell-warn' : '']">
                    {{ row.durationMs }}ms
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="resultSummary" label="结果摘要" min-width="240" show-overflow-tooltip>
                <template #default="{ row }">
                  <span class="summary-cell mono">{{ row.resultSummary || '—' }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="createdAt" label="执行时间" min-width="155" align="right">
                <template #default="{ row }">
                  <span class="time-col mono">{{ row.createdAt || '—' }}</span>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </template>

      <!-- 审核详情弹窗 -->
      <el-dialog v-model="showDetail" title="飞轮审核与回流决策" width="min(700px, calc(100vw - 32px))" class="craft-dialog">
        <div v-if="detail" class="detail-container">
          <div class="detail-header-meta">
            <span class="id-pill">ID #{{ detail.id }}</span>
            <span class="meta-time mono">{{ detail.created_at }}</span>
            <span v-if="detail.standard_question" class="sq-badge">
              标问：{{ detail.standard_question }}
            </span>
          </div>

          <!-- 原始回答示例 -->
          <div v-if="detail.example_answer" class="editorial-card">
            <div class="card-header">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
              <span>原始模型生成答案示例</span>
              <span class="card-badge">RAW GENERATION</span>
            </div>
            <div class="card-body serif-text">{{ detail.example_answer }}</div>
          </div>

          <!-- 检索证据 -->
          <div v-if="detail.pending && detail.pending.length" class="evidence-section">
            <div v-for="(p, i) in detail.pending" :key="i" class="evidence-card">
              <div class="evidence-header">
                <div class="ev-title">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                  </svg>
                  <span>检索证据 #{{ i + 1 }}</span>
                </div>
                <span class="ev-hit-count">知识库命中 {{ (p.snapshot || []).length }} 条</span>
              </div>

              <div class="snap-list">
                <div v-for="(s, j) in p.snapshot || []" :key="j" class="snap-item">
                  <div class="snap-header">
                    <span class="snap-source">{{ s.title || '未知典籍' }}</span>
                    <span v-if="s.writer || s.dynasty" class="snap-author">
                      [{{ s.dynasty || '朝代不详' }}] {{ s.writer || '佚名' }}
                    </span>
                    <span v-if="s.score != null" class="snap-score mono">
                      相似度 {{ Number(s.score).toFixed(3) }}
                    </span>
                  </div>
                  <div class="snap-content">{{ s.text }}</div>
                </div>
              </div>
            </div>
          </div>

          <!-- 审核决策表单 -->
          <div class="decision-form">
            <div class="form-field">
              <label class="form-label">
                <span>归一标准问法</span>
                <span class="label-opt">（选填，用于聚类归一问法）</span>
              </label>
              <el-input v-model="sqInput" placeholder="输入清洗后的标准问法" />
            </div>

            <div class="form-field">
              <label class="form-label">
                <span>回流答案正文</span>
                <span class="label-req">（审核通过后直接回流知识库检索）</span>
              </label>
              <el-input
                v-model="answerInput"
                type="textarea"
                :rows="5"
                placeholder="请输入经过核验的高质量正文回答..."
              />
            </div>
          </div>
        </div>

        <template #footer>
          <div class="dialog-actions">
            <button class="action-btn-ghost" @click="showDetail = false">取消</button>
            <button class="action-btn-danger" @click="onReject">驳 回</button>
            <button class="action-btn-primary" @click="onApprove">
              <span>通过并回流知识库</span>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </button>
          </div>
        </template>
      </el-dialog>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import AppNav from '@/components/AppNav.vue'
import { useAdminStore } from '@/store/admin'
import {
  adminGetCode,
  adminLogin,
  reviewList,
  reviewDetail,
  reviewApprove,
  reviewReject,
  costReport,
  auditList
} from '@/api/adminApi'

const admin = useAdminStore()
const tab = ref<'review' | 'cost' | 'audit'>('review')
const loading = ref(false)

/* 登录 */
const captcha = ref('')
const codeKey = ref('')
const loginForm = ref({ username: '', password: '', code: '' })
const loginError = ref('')

const loadCaptcha = async () => {
  try {
    const d = await adminGetCode()
    captcha.value = d?.code || ''
    codeKey.value = d?.codeKey || ''
  } catch {}
}

const onLogin = async () => {
  if (loading.value) return
  loginError.value = ''
  if (!loginForm.value.username || !loginForm.value.password || !loginForm.value.code) {
    loginError.value = '账号、密码与验证码必填'
    return
  }
  loading.value = true
  try {
    const d = await adminLogin({ ...loginForm.value, codeKey: codeKey.value })
    admin.setAdmin(d?.token || '', d?.userName || loginForm.value.username)
    ElMessage.success('管理员身份已验签')
    loadAll()
  } catch { loginError.value = '登录失败，请检查凭证与验证码后重试' } finally {
    loading.value = false
  }
}

const logoutAdmin = () => {
  admin.clearAdmin()
  captcha.value = ''
  loadCaptcha()
}

/* 飞轮审核 */
const reviews = ref<any[]>([])
const reviewStatus = ref('pending')
const reviewLoading = ref(false)
const showDetail = ref(false)
const detail = ref<any>(null)
const sqInput = ref('')
const answerInput = ref('')

const questionOf = (row: any) =>
  row?.question || row?.standard_question || row?.pending?.[0]?.snapshot?.[0]?.question || row?.title || ''

const loadReview = async () => {
  reviewLoading.value = true
  try {
    reviews.value = (await reviewList(reviewStatus.value))?.items || []
  } catch {
    reviews.value = []
  } finally {
    reviewLoading.value = false
  }
}

const openReview = async (row: any) => {
  try {
    detail.value = await reviewDetail(row.id)
    answerInput.value = detail.value?.example_answer || ''
    sqInput.value = detail.value?.standard_question || ''
    showDetail.value = true
  } catch {}
}

const onApprove = async () => {
  if (!detail.value) return
  if (!answerInput.value.trim()) {
    ElMessage.warning('回流答案必填')
    return
  }
  try {
    await reviewApprove(detail.value.id, {
      standard_question: sqInput.value.trim() || undefined,
      approved_answer: answerInput.value.trim()
    })
    ElMessage.success('审核已通过并写入知识库')
    showDetail.value = false
    loadReview()
  } catch {}
}

const onReject = async () => {
  if (!detail.value) return
  try {
    await reviewReject(detail.value.id)
    ElMessage.success('已驳回该记录')
    showDetail.value = false
    loadReview()
  } catch {}
}

/* 成本报表 */
const costRows = ref<any[]>([])
const costTotal = ref('')
const costDays = ref(14)
const costLoading = ref(false)

const loadCost = async () => {
  costLoading.value = true
  try {
    const d = await costReport(costDays.value)
    costRows.value = d?.rows || []
    const t = d?.total
    costTotal.value = typeof t === 'object' && t ? String(t.costUsd ?? '') : String(t ?? '')
  } catch {
    costRows.value = []
  } finally {
    costLoading.value = false
  }
}

/* 工具审计 */
const auditRows = ref<any[]>([])
const auditTool = ref('')
const auditLoading = ref(false)

const loadAudit = async () => {
  auditLoading.value = true
  try {
    const d = await auditList({ limit: 50, tool_name: auditTool.value.trim() || undefined })
    auditRows.value = d?.rows || []
  } catch {
    auditRows.value = []
  } finally {
    auditLoading.value = false
  }
}

const loadAll = () => {
  loadReview()
  loadCost()
  loadAudit()
}

onMounted(async () => {
  await loadCaptcha()
  if (admin.token) loadAll()
})
</script>

<style scoped>
.console-page {
  min-height: 100dvh;
  background-color: var(--md-surface);
  padding-bottom: 72px;
}

.cs-container {
  max-width: 1240px;
  margin: 0 auto;
  padding: 28px 32px 0;
}

/* ===== 顶部操作区 ===== */
.cs-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  padding-bottom: 22px;
  border-bottom: 1px solid var(--md-outline-variant);
  margin-bottom: 26px;
  gap: 24px;
 flex-wrap: wrap; }

.title-row {
  display: flex;
  align-items: baseline;
  gap: 14px;
  margin-bottom: 6px;
 flex-wrap: wrap; }

.cs-title {
  margin: 0;
  font-size: 26px;
  font-weight: 500;
  letter-spacing: normal;
  color: var(--md-on-surface);
  font-family: var(--f-sans);
}

.meta-badge {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
  letter-spacing: normal;
  color: var(--md-primary);
  background: var(--md-primary-container);
  border: 1px solid var(--md-outline-variant);
  padding: 2px 7px;
  border-radius: 12px;
}

.cs-desc {
  margin: 0;
  font-size: 13px;
  color: var(--md-on-surface-variant);
  letter-spacing: normal;
}

.cs-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
 flex-wrap: wrap; }

.operator-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 5px 12px;
  background: var(--md-surface-container);
  border: 1px solid var(--md-outline-variant);
  border-radius: 20px;
  font-size: 13px;
  color: var(--md-on-surface);
}

.dot-online {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--md-success);
  box-shadow: var(--shadow-sm);
}

.cs-nav-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  color: var(--md-on-surface-variant);
  background: var(--md-surface-container);
  border: 1px solid var(--md-outline-variant);
  padding: 5px 11px;
  border-radius: 12px;
  transition: all 0.15s ease;
}

.cs-nav-btn:hover {
  color: var(--md-on-surface);
  background: var(--md-surface-container);
  border-color: var(--md-outline);
}

.out-icon {
  opacity: 0.7;
}

.nav-content-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--md-primary);
  background: var(--md-primary-container);
  border: 1px solid var(--md-outline-variant);
  padding: 5px 13px;
  border-radius: 12px;
  transition: all 0.15s ease;
}

.nav-content-btn:hover {
  background: var(--md-primary-container);
  border-color: var(--md-primary);
}

.logout-btn {
  background: transparent;
  border: 1px solid transparent;
  color: var(--md-on-surface-variant);
  font-size: 13px;
  cursor: pointer;
  padding: 5px 10px;
  border-radius: 12px;
  transition: all 0.15s ease;
}

.logout-btn:hover {
  color: var(--md-on-surface);
  background: var(--md-surface-container);
}

/* ===== 登录认证卡片 ===== */
.auth-wrap {
  display: flex;
  justify-content: center;
  padding: 40px 0 60px;
}

.auth-card {
  width: 100%;
  max-width: 440px;
  padding: 34px 36px 28px;
  background: var(--md-surface-container-low);
  border: 1px solid var(--md-outline-variant);
  border-radius: 28px;
  box-shadow: var(--shadow-sm);
}

.auth-header {
  text-align: center;
  margin-bottom: 26px;
}

.auth-icon-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 46px;
  height: 46px;
  border-radius: 10px;
  background: var(--md-primary-container);
  color: var(--md-primary);
  border: 1px solid var(--md-outline-variant);
  margin-bottom: 14px;
}

.auth-title {
  margin: 0 0 6px;
  font-size: 20px;
  font-family: var(--f-sans);
  color: var(--md-on-surface);
  font-weight: 500;
}

.auth-desc {
  margin: 0;
  font-size: 13px;
  color: var(--md-on-surface-variant);
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.field-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--md-on-surface);
  letter-spacing: normal;
}

.captcha-row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.captcha-preview {
  width: 120px;
  height: 38px;
  border-radius: 12px;
  border: 1px solid var(--md-outline-variant);
  background: var(--md-surface-container);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  cursor: pointer;
  flex-shrink: 0;
  transition: border-color 0.15s ease;
}

.captcha-preview:hover {
  border-color: var(--md-primary);
}

.captcha-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.captcha-loading {
  font-size: 13px;
  color: var(--md-on-surface-variant);
}

.auth-submit-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 6px;
  background: var(--md-primary);
  color: var(--md-on-primary);
  border: none;
  font-weight: 500;
  font-size: 13.5px;
  padding: 10px 16px;
  border-radius: 12px;
  cursor: pointer;
  transition: opacity 0.15s ease, transform 0.1s ease;
}

.auth-submit-btn:hover {
  opacity: 0.92;
}

.auth-submit-btn:active {
  transform: translateY(1px);
}

.security-callout {
  margin-top: 22px;
  padding: 12px 14px;
  background: var(--md-surface-container);
  border: 1px solid var(--md-outline-variant);
  border-radius: 12px;
  text-align: left;
}

.security-badge {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 10px;
  color: var(--md-on-surface-variant);
  letter-spacing: normal;
  margin-bottom: 4px;
}

.security-hint {
  margin: 0;
  font-size: 13px;
  color: var(--md-on-surface-variant);
  line-height: 1.6;
}

/* ===== 标签导航栏 ===== */
.cs-tab-nav {
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid var(--md-outline-variant);
  margin-bottom: 22px;
  padding-bottom: 2px;
}

.cs-tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--md-on-surface-variant);
  font-size: 13.5px;
  font-weight: 500;
  padding: 9px 16px;
  cursor: pointer;
  margin-bottom: -2px;
  transition: all 0.15s ease;
}

.cs-tab-btn:hover {
  color: var(--md-on-surface);
}

.cs-tab-btn.active {
  color: var(--md-primary);
  border-bottom-color: var(--md-primary);
}

.tab-count-badge {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
  background: var(--md-primary-container);
  color: var(--md-primary);
  padding: 1px 6px;
  border-radius: 10px;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}

/* ===== 工具条 ===== */
.panel-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  gap: 16px;
  flex-wrap: wrap;
}

.filter-cluster {
  display: flex;
  align-items: center;
  gap: 12px;
}

.toolbar-label {
  font-size: 13px;
  color: var(--md-on-surface-variant);
  letter-spacing: normal;
}

.segmented-control {
  display: inline-flex;
  background: var(--md-surface-container);
  border: 1px solid var(--md-outline-variant);
  border-radius: 999px;
  padding: 2px;
  gap: 2px;
}

.seg-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: transparent;
  border: none;
  color: var(--md-on-surface-variant);
  font-size: 13px;
  padding: 4px 11px;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.seg-item:hover {
  color: var(--md-on-surface);
}

.seg-item.active {
  background: var(--md-primary-container);
  color: var(--md-on-primary-container);
  box-shadow: var(--shadow-sm);
}

.seg-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
}

.dot-pending { background: var(--md-warning); }
.dot-approved { background: var(--md-success); }
.dot-rejected { background: var(--md-error); }

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 14px;
}

.hint-caption {
  font-size: 13px;
  color: var(--md-on-surface-variant);
}

.total-metric-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: var(--md-primary-container);
  border: 1px solid var(--md-outline-variant);
  padding: 4px 11px;
  border-radius: 12px;
}

.metric-label {
  font-size: 13px;
  color: var(--md-on-surface-variant);
}

.metric-val {
  font-size: 13.5px;
  font-weight: 500;
  color: var(--md-primary);
  font-variant-numeric: tabular-nums;
}

.search-input-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.craft-input {
  background: var(--md-surface-container-low);
  border: 1px solid var(--md-outline-variant);
  border-radius: 12px;
  color: var(--md-on-surface);
  font-size: 13px;
  padding: 5px 11px;
  width: 250px;
  outline: none;
  transition: border-color 0.15s ease;
}

.craft-input:focus {
  border-color: var(--md-primary);
}

.tool-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--md-surface-container);
  border: 1px solid var(--md-outline-variant);
  color: var(--md-on-surface);
  font-size: 13px;
  padding: 5px 11px;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.tool-btn:hover:not(:disabled) {
  color: var(--md-on-surface);
  background: var(--md-surface-container);
  border-color: var(--md-outline);
}

.tool-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.spin-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  100% { transform: rotate(360deg); }
}

/* ===== 表格核心样式 ===== */
.table-frame {
  border: 1px solid var(--md-outline-variant);
  border-radius: 16px;
  overflow: auto;
  background: var(--md-surface-container-low);
 max-width: 100%; }

.craft-table {
  width: 100%;
}

:deep(.craft-table .el-table__header-wrapper th) {
  background: var(--md-surface-container) !important;
  color: var(--md-on-surface-variant) !important;
  font-weight: 500;
  font-size: 13px;
  letter-spacing: normal;
  border-bottom: 1px solid var(--md-outline-variant);
  padding: 8px 0;
}

:deep(.craft-table .el-table__row) {
  background: transparent !important;
  color: var(--md-on-surface);
  font-size: 13px;
  transition: background 0.15s ease;
}

:deep(.craft-table .el-table__row:hover > td) {
  background: var(--md-surface-container) !important;
}

:deep(.craft-table td) {
  border-bottom: 1px solid var(--md-outline-variant);
  padding: 9px 0;
}

.click-table :deep(tbody tr) {
  cursor: pointer;
}

/* ===== 表格内部药丸与指标 ===== */
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.id-pill {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
  color: var(--md-on-surface-variant);
  background: var(--md-surface-container);
  padding: 2px 6px;
  border-radius: 12px;
  border: 1px solid var(--md-outline-variant);
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  padding: 2px 8px;
  border-radius: 12px;
  border: 1px solid var(--md-outline-variant);
  color: var(--md-on-surface);
  background: var(--md-surface-container);
}

.status-pill .dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
}

.pill-pending {
  color: var(--md-warning);
  border-color: var(--md-outline-variant);
  background: var(--md-warning-container);
}
.pill-pending .dot { background: var(--md-warning); }

.pill-approved {
  color: var(--md-success);
  border-color: var(--md-outline-variant);
  background: var(--md-success-container);
}
.pill-approved .dot { background: var(--md-success); }

.pill-rejected {
  color: var(--md-error);
  border-color: var(--md-outline-variant);
  background: var(--md-error-container);
}
.pill-rejected .dot { background: var(--md-error); }

.question-cell {
  display: flex;
  align-items: center;
}

.question-text {
  color: var(--md-on-surface);
  line-height: 1.5;
  font-weight: 400;
}

.num-badge {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
  color: var(--md-on-surface);
  background: var(--md-surface-container);
  padding: 2px 7px;
  border-radius: 12px;
  font-variant-numeric: tabular-nums;
}

.num-cell {
  font-size: 13px;
  color: var(--md-on-surface);
  font-variant-numeric: tabular-nums;
}

.cell-warn {
  color: var(--md-warning);
  font-weight: 500;
}

.cost-cell {
  font-size: 13px;
  color: var(--md-primary);
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}

.time-col {
  font-size: 13px;
  color: var(--md-on-surface-variant);
  font-variant-numeric: tabular-nums;
}

.intent-pill {
  font-size: 13px;
  color: var(--md-on-surface);
  background: var(--md-surface-container);
  padding: 2px 7px;
  border-radius: 12px;
}

.model-pill {
  font-size: 13px;
  color: var(--md-primary);
  background: var(--md-primary-container);
  border: 1px solid var(--md-outline-variant);
  padding: 2px 7px;
  border-radius: 12px;
}

.tool-pill {
  font-size: 13px;
  color: var(--md-on-surface);
  background: var(--md-surface-container);
  border: 1px solid var(--md-outline-variant);
  padding: 2px 7px;
  border-radius: 12px;
}

.source-tag {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
  color: var(--md-on-surface-variant);
}

.summary-cell {
  font-size: 13px;
  color: var(--md-on-surface);
}

/* ===== 详情弹窗与决策卡 ===== */
.detail-container {
  max-height: 60vh;
  overflow-y: auto;
  padding-right: 4px;
}

.detail-header-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--md-outline-variant);
}

.meta-time {
  font-size: 13px;
  color: var(--md-on-surface-variant);
}

.sq-badge {
  font-size: 13px;
  color: var(--md-primary);
  background: var(--md-primary-container);
  border: 1px solid var(--md-outline-variant);
  padding: 2px 8px;
  border-radius: 12px;
}

.editorial-card {
  background: var(--md-surface-container);
  border: 1px solid var(--md-outline-variant);
  border-radius: 24px;
  padding: 12px 14px;
  margin-bottom: 14px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--md-on-surface-variant);
  margin-bottom: 8px;
}

.card-badge {
  margin-left: auto;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 10px;
  color: var(--md-on-surface-variant);
  border: 1px solid var(--md-outline-variant);
  padding: 1px 5px;
  border-radius: 12px;
}

.card-body {
  font-size: 13.5px;
  line-height: 1.8;
  color: var(--md-on-surface);
  white-space: pre-wrap;
}

.serif-text {
  font-family: var(--f-sans);
}

.evidence-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
}

.evidence-card {
  background: var(--md-surface-container);
  border: 1px solid var(--md-outline-variant);
  border-radius: 24px;
  padding: 12px 14px;
}

.evidence-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.ev-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  color: var(--md-on-surface);
}

.ev-hit-count {
  font-size: 13px;
  color: var(--md-on-surface-variant);
}

.snap-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.snap-item {
  padding: 8px 10px;
  background: var(--md-surface-container);
  border: 1px solid var(--md-outline-variant);
  border-radius: 12px;
}

.snap-header {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 4px;
}

.snap-source {
  font-size: 13px;
  font-weight: 500;
  color: var(--md-on-surface);
}

.snap-author {
  font-size: 13px;
  color: var(--md-on-surface-variant);
}

.snap-score {
  margin-left: auto;
  font-size: 13px;
  color: var(--md-primary);
}

.snap-content {
  font-size: 13px;
  line-height: 1.7;
  color: var(--md-on-surface);
  white-space: pre-wrap;
  max-height: 120px;
  overflow-y: auto;
}

.decision-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid var(--md-outline-variant);
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-label {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  color: var(--md-on-surface);
}

.label-opt {
  font-size: 13px;
  color: var(--md-on-surface-variant);
}

.label-req {
  font-size: 13px;
  color: var(--md-primary);
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.action-btn-ghost {
  background: transparent;
  border: 1px solid var(--md-outline-variant);
  color: var(--md-on-surface-variant);
  font-size: 13px;
  padding: 6px 14px;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.action-btn-ghost:hover {
  color: var(--md-on-surface);
  border-color: var(--md-outline);
}

.action-btn-danger {
  background: var(--md-error-container);
  border: 1px solid var(--md-outline-variant);
  color: var(--md-error);
  font-size: 13px;
  padding: 6px 14px;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.action-btn-danger:hover {
  background: var(--md-error-container);
}

.action-btn-primary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--md-primary);
  border: 1px solid var(--md-primary);
  color: var(--md-on-primary);
  font-size: 13px;
  font-weight: 500;
  padding: 6px 16px;
  border-radius: 12px;
  cursor: pointer;
  transition: opacity 0.15s ease;
}

.action-btn-primary:hover {
  opacity: 0.92;
}

:deep(.el-button) { min-height: 44px; border-radius: 999px; font-family: var(--f-sans); letter-spacing: normal; }
:deep(.el-input__wrapper) { min-height: 48px; border-radius: 12px; }
:deep(.el-textarea__inner) { border-radius: 12px; font-size: 15px; }
:deep(.el-tabs__item) { min-height: 48px; font-family: var(--f-sans); letter-spacing: normal; }
:deep(.el-dialog) { max-width: calc(100vw - 32px); border-radius: 28px; }
.form-error { font-size: 14px; line-height: 1.5; color: var(--md-error); background: var(--md-error-container); border-radius: 12px; padding: 12px 16px; }

button, .cs-nav-btn, .nav-content-btn, .nav-console-btn, .unauth-btn { min-height: 44px; border-radius: 999px; } .crud-container, .tab-panel, .panel-section, .ca-container, .cs-container { min-width: 0; max-width: 100%; } .craft-input { min-height: 48px; max-width: 100%; border-radius: 12px; } .crud-pager, .dialog-actions, .dialog-footer, .craft-toolbar, .toolbar-left, .toolbar-right { gap: 12px; flex-wrap: wrap; }
@media (max-width: 768px) { .cs-container { padding: 24px 16px 0; } .cs-header { align-items: flex-start; gap: 16px; } .cs-header-right { width: 100%; } .filter-cluster, .search-input-wrap { flex-wrap: wrap; } .auth-card { padding: 24px; } .cs-tab-nav { overflow-x: auto; } .cs-tab-btn { flex-shrink: 0; } .detail-header-meta { flex-wrap: wrap; } }
</style>
