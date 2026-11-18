<template>
  <div class="content-admin-page">
    <AppNav />
    <div class="ca-container">
      <!-- 页面顶栏：工坊标头与状态门 -->
      <header class="ca-header">
        <div class="ca-header-left">
          <div class="title-row">
            <h1 class="ca-title">内容管理中台</h1>
            <span class="meta-badge">OPERATIONAL WORKSPACE</span>
          </div>
          <p class="ca-desc">语料与知识库对账 · L1/L2多级缓存观测 · 典籍名家 · 社区与反馈治理</p>
        </div>
        <div class="ca-header-right">
          <div class="operator-pill">
            <span class="dot-online"></span>
            <span class="operator-text">{{ admin.userName || 'admin' }}</span>
          </div>
          <router-link to="/console" class="nav-console-btn">
            控制台 ↗
          </router-link>
        </div>
      </header>

      <!-- 未登录提示门 -->
      <div v-if="!admin.token" class="unauth-box inset">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" class="lock-icon">
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
          <path d="M7 11V7a5 5 0 0 1 10 0v4" />
        </svg>
        <div class="unauth-text">请先在管理控制台完成操作员身份验签</div>
        <router-link to="/console" class="unauth-btn">前往管理控制台登录</router-link>
      </div>

      <!-- 主工作区：左侧精准工作区导航 + 右侧面板 -->
      <div v-else class="ca-shell">
        <aside class="ca-sidebar inset">
          <nav class="ca-nav-groups">
            <!-- 分组 1: 认知与缓存 -->
            <div class="nav-group">
              <div class="group-label">认知与存储</div>
              <button type="button" class="nav-item" :class="{ active: cur === 'kb' }" @click="selectMenu('kb')">
                <svg class="item-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
                  <ellipse cx="12" cy="5" rx="9" ry="3" />
                  <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
                  <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
                </svg>
                <span>知识库同步</span>
              </button>
              <button type="button" class="nav-item" :class="{ active: cur === 'cache' }" @click="selectMenu('cache')">
                <svg class="item-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
                  <rect x="4" y="4" width="16" height="16" rx="2" />
                  <rect x="9" y="9" width="6" height="6" />
                  <line x1="9" y1="1" x2="9" y2="4" /><line x1="15" y1="1" x2="15" y2="4" />
                  <line x1="9" y1="20" x2="9" y2="23" /><line x1="15" y1="20" x2="15" y2="23" />
                  <line x1="20" y1="9" x2="23" y2="9" /><line x1="20" y1="15" x2="23" y2="15" />
                  <line x1="1" y1="9" x2="4" y2="9" /><line x1="1" y1="15" x2="4" y2="15" />
                </svg>
                <span>多级缓存观测</span>
              </button>
            </div>

            <!-- 分组 2: 典籍与名家 -->
            <div class="nav-group">
              <div class="group-label">典籍与名家</div>
              <button type="button" class="nav-item" :class="{ active: cur === 'poem' }" @click="selectMenu('poem')">
                <svg class="item-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
                  <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                  <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
                </svg>
                <span>诗词语料</span>
              </button>
              <button type="button" class="nav-item" :class="{ active: cur === 'writer' }" @click="selectMenu('writer')">
                <svg class="item-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                  <circle cx="12" cy="7" r="4" />
                </svg>
                <span>历代诗人</span>
              </button>
              <button type="button" class="nav-item" :class="{ active: cur === 'rhesis' }" @click="selectMenu('rhesis')">
                <svg class="item-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
                  <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
                </svg>
                <span>经典名句</span>
              </button>
            </div>

            <!-- 分组 3: 运营与风控 -->
            <div class="nav-group">
              <div class="group-label">运营与风控</div>
              <button type="button" class="nav-item" :class="{ active: cur === 'forum' }" @click="selectMenu('forum')">
                <svg class="item-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
                <span>帖子与评论</span>
              </button>
              <button type="button" class="nav-item" :class="{ active: cur === 'feedback' }" @click="selectMenu('feedback')">
                <svg class="item-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
                  <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
                  <polyline points="22,6 12,13 2,6" />
                </svg>
                <span>用户反馈回复</span>
              </button>
              <button type="button" class="nav-item" :class="{ active: cur === 'user' }" @click="selectMenu('user')">
                <svg class="item-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                  <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                  <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                </svg>
                <span>用户账号管控</span>
              </button>
              <button type="button" class="nav-item" :class="{ active: cur === 'notice' }" @click="selectMenu('notice')">
                <svg class="item-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
                  <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                  <path d="M13.73 21a2 2 0 0 1-3.46 0" />
                </svg>
                <span>全站置顶公告</span>
              </button>
            </div>
          </nav>
        </aside>

        <!-- 右侧主体工作区 -->
        <main class="ca-main-panel inset">
          <!-- 面板 1: 知识库同步与对账 -->
          <section v-if="cur === 'kb'" class="panel-section">
            <div class="section-head">
              <h2 class="section-title">知识库双向对账 (MySQL ↔ Milvus 向量库)</h2>
              <span class="section-desc">基于 BGE-M3 密集向量表征，监控底层数据事实源与检索块的一致性状态</span>
            </div>

            <div class="telemetry-grid" v-loading="kbLoading">
              <div class="telemetry-card">
                <div class="card-eyebrow">
                  <span>诗词底表记录</span>
                  <span class="subtle-pill">FACTS</span>
                </div>
                <div class="card-value">{{ kb.potry_total ?? '—' }}</div>
                <div class="card-sub">MySQL 诗词库总条数</div>
              </div>

              <div class="telemetry-card">
                <div class="card-eyebrow">
                  <span>向量覆盖条目</span>
                  <span class="status-pill pill-good">INDEXED</span>
                </div>
                <div class="card-value">{{ kb.poem_covered ?? '—' }}</div>
                <div class="card-sub">已生成 Embedding 并入库</div>
              </div>

              <div class="telemetry-card" :class="{ 'card-warn': (kb.uncovered || 0) > 0 }">
                <div class="card-eyebrow">
                  <span>未覆盖落后条目</span>
                  <span v-if="(kb.uncovered || 0) > 0" class="status-pill pill-warn">LAGGED</span>
                  <span v-else class="status-pill pill-good">CLEAR</span>
                </div>
                <div class="card-value" :class="{ 'val-warn': (kb.uncovered || 0) > 0 }">{{ kb.uncovered ?? '0' }}</div>
                <div class="card-sub">需执行增量向量补充</div>
              </div>

              <div class="telemetry-card">
                <div class="card-eyebrow">
                  <span>待处理分块</span>
                  <span class="subtle-pill">PENDING</span>
                </div>
                <div class="card-value">{{ kb.chunks_pending ?? '0' }}</div>
                <div class="card-sub">待生成密集向量的文本切片</div>
              </div>

              <div class="telemetry-card">
                <div class="card-eyebrow">
                  <span>双向一致性对账</span>
                  <span :class="['status-pill', kb.consistent ? 'pill-good' : 'pill-warn']">
                    {{ kb.consistent ? 'CONSISTENT' : 'DRIFT' }}
                  </span>
                </div>
                <div class="card-value" :style="{ color: kb.consistent ? 'var(--gold)' : 'var(--md-error)' }">
                  {{ kb.consistent ? '完整一致' : '存在差异' }}
                </div>
                <div class="card-sub">标量与向量指纹核验</div>
              </div>
            </div>

            <div class="craft-toolbar">
              <div class="toolbar-left">
                <el-button size="small" class="tool-btn-ghost" @click="loadKb">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 4px">
                    <polyline points="23 4 23 10 17 10" />
                    <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
                  </svg>
                  刷新对账
                </el-button>
                <el-button size="small" type="primary" class="tool-btn-gold" :loading="syncing" @click="doSync">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 4px">
                    <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2" />
                  </svg>
                  执行后台全量同步 (清除孤儿+补全嵌入)
                </el-button>
              </div>
              <div class="toolbar-right">
                <span class="audit-log" v-if="kb.last_sync">最新审计: {{ JSON.stringify(kb.last_sync).slice(0, 75) }}</span>
              </div>
            </div>
          </section>

          <!-- 面板 2: 多级缓存与布隆过滤器监控 -->
          <section v-else-if="cur === 'cache'" class="panel-section">
            <div class="section-head">
              <h2 class="section-title">多级缓存与布隆防穿透监控 (L1 Caffeine + L2 Redis)</h2>
              <span class="section-desc">微秒级堆内本地缓存 + 逻辑过期防击穿 + Redisson 分布式位图 0.1ms 非法拦截</span>
            </div>

            <div class="telemetry-grid" v-loading="cacheLoading">
              <div class="telemetry-card">
                <div class="card-eyebrow">
                  <span>L1 诗词堆内缓存</span>
                  <span class="subtle-pill">CAFFEINE</span>
                </div>
                <div class="card-value">{{ cacheInfo.poemL1EstimatedSize ?? '0' }}</div>
                <div class="card-sub">容量上限 10,000 / LRU 驱逐</div>
              </div>

              <div class="telemetry-card">
                <div class="card-eyebrow">
                  <span>L1 诗词命中率</span>
                  <span class="status-pill pill-gold">ACCELERATED</span>
                </div>
                <div class="card-value" style="color: var(--gold);">{{ cacheInfo.poemL1HitRate ?? '0%' }}</div>
                <div class="card-sub">
                  命中 {{ cacheInfo.poemL1HitCount ?? 0 }} / 未命中 {{ cacheInfo.poemL1MissCount ?? 0 }}
                </div>
              </div>

              <div class="telemetry-card">
                <div class="card-eyebrow">
                  <span>L1 诗人堆内缓存</span>
                  <span class="subtle-pill">CAFFEINE</span>
                </div>
                <div class="card-value">{{ cacheInfo.writerL1EstimatedSize ?? '0' }}</div>
                <div class="card-sub">容量上限 2,000 / 30m TTL</div>
              </div>

              <div class="telemetry-card">
                <div class="card-eyebrow">
                  <span>布隆过滤器注册 ID</span>
                  <span class="subtle-pill">BITSET</span>
                </div>
                <div class="card-value">{{ cacheInfo.poemBloomEstimatedCount ?? '0' }}</div>
                <div class="card-sub">预设容量 100,000 / 容错率 1%</div>
              </div>

              <div class="telemetry-card">
                <div class="card-eyebrow">
                  <span>分布式布隆状态</span>
                  <span :class="['status-pill', cacheInfo.poemBloomInitialized ? 'pill-good' : 'pill-warn']">
                    {{ cacheInfo.poemBloomInitialized ? 'READY' : 'OFFLINE' }}
                  </span>
                </div>
                <div class="card-value" :style="{ color: cacheInfo.poemBloomInitialized ? 'var(--ink-900)' : 'var(--md-error)' }">
                  {{ cacheInfo.poemBloomInitialized ? '集群位图就绪' : '未初始预热' }}
                </div>
                <div class="card-sub">拦截非法 ID 零压力穿透</div>
              </div>
            </div>

            <div class="craft-toolbar">
              <div class="toolbar-left">
                <el-button size="small" class="tool-btn-ghost" @click="loadCacheStats">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 4px">
                    <polyline points="23 4 23 10 17 10" />
                    <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
                  </svg>
                  刷新监控指标
                </el-button>
                <el-button size="small" type="primary" class="tool-btn-gold" :loading="warmingUp" @click="doWarmUpCache">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 4px">
                    <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
                  </svg>
                  全量重热分布式布隆过滤器
                </el-button>
                <el-button size="small" class="tool-btn-danger" @click="doClearL1Cache">
                  清空当前节点 L1 缓存
                </el-button>
              </div>
              <div class="toolbar-right">
                <span class="audit-log" v-if="warmUpMsg">{{ warmUpMsg }}</span>
              </div>
            </div>
          </section>

          <!-- 面板 3: 诗词语料管理 -->
          <AdminCrud v-else-if="cur === 'poem'" ref="poemRef"
            hint="维护诗词篇目语料；写入或修改后将触发 L1/L2 多级缓存失效广播与向量库即时同步"
            :columns="[
              { prop: 'id', label: 'ID', width: 80 },
              { prop: 'title', label: '标题', tooltip: true },
              { prop: 'writer', label: '作者', width: 120 },
              { prop: 'dynasty', label: '朝代', width: 90 },
              { prop: 'type', label: '体裁/类型', width: 100 },
            ]"
            :formFields="[
              { prop: 'title', label: '标题' },
              { prop: 'writer', label: '作者' },
              { prop: 'dynasty', label: '朝代' },
              { prop: 'type', label: '类型' },
              { prop: 'content', label: '正文内容', type: 'textarea' },
            ]"
            :list="poemPage" :add="poemAdd" :update="poemUpdate" :remove="poemDelete" />

          <!-- 面板 4: 诗人档案管理 -->
          <AdminCrud v-else-if="cur === 'writer'"
            hint="诗人名家档案库；维护画像头像 OSS 寻址与生平评述，供诗人画卷与检索关联使用"
            :columns="[
              { prop: 'id', label: 'ID', width: 80 },
              { prop: 'name', label: '名讳', width: 130 },
              { prop: 'headImageUrl', label: '头像资源路径', tooltip: true },
              { prop: 'simpleIntro', label: '简要传记', tooltip: true },
            ]"
            :formFields="[
              { prop: 'name', label: '姓名' },
              { prop: 'headImageUrl', label: '头像URL' },
              { prop: 'simpleIntro', label: '简要概述' },
              { prop: 'detailIntro', label: '详细生平', type: 'textarea' },
            ]"
            :list="writerPage" :add="writerAdd" :update="writerUpdate" :remove="writerDelete" />

          <!-- 面板 5: 经典名句 -->
          <AdminCrud v-else-if="cur === 'rhesis'"
            hint="千古名句库；为系统主屏与伴学卡片提供随机池提取数据源"
            :columns="[
              { prop: 'id', label: 'ID', width: 80 },
              { prop: 'name', label: '名句摘录', tooltip: true },
              { prop: 'fromm', label: '诗篇出处', tooltip: true },
            ]"
            :formFields="[
              { prop: 'name', label: '诗句' },
              { prop: 'fromm', label: '出处' },
            ]"
            :list="rhesisPage" :add="rhesisAdd" :update="rhesisUpdate" :remove="rhesisDelete" />

          <!-- 面板 6: 帖子与评论审核 -->
          <template v-else-if="cur === 'forum'">
            <div class="section-head">
              <h2 class="section-title">社区交流帖与评论审核</h2>
              <span class="section-desc">审查违规论坛发帖；支持单帖下钻展开双层嵌套评论树并实施精细化下架</span>
            </div>
            <AdminCrud
              hint="删除帖子不级联物理删除评论；压测帖子可支持批量清理"
              :columns="[
                { prop: 'id', label: 'ID', width: 80 },
                { prop: 'title', label: '发帖标题', tooltip: true },
                { prop: 'username', label: '发布者', width: 120 },
                { prop: 'liked', label: '获赞数', width: 80 },
                { prop: 'conmments', label: '评论总计', width: 90 },
              ]"
              :formFields="[]"
              :list="blogPage" :remove="blogDelete" :action-width="160">
              <template #row="{ row }">
                <el-button link size="small" type="primary" @click="openComments(row)">检视评论</el-button>
              </template>
            </AdminCrud>

            <!-- 评论下钻抽屉 -->
            <el-drawer v-model="cmtDlg" :title="`帖子 #${cmtBlogId} 评论审核抽屉`" size="52%" class="craft-drawer">
              <div class="drawer-content">
                <el-table :data="cmtRows" v-loading="cmtLoading" size="small" class="craft-table">
                  <el-table-column prop="id" label="ID" width="70">
                    <template #default="{ row }">
                      <span class="id-pill">#{{ row.id }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column prop="username" label="发表用户" width="110" />
                  <el-table-column prop="context" label="评论留言" show-overflow-tooltip />
                  <el-table-column prop="liked" label="点赞" width="70" />
                  <el-table-column label="处置" width="80" align="center">
                    <template #default="{ row }">
                      <el-button link type="danger" size="small" @click="delCmt(row)">下架</el-button>
                    </template>
                  </el-table-column>
                </el-table>
                <div class="crud-pager">
                  <span class="total-caption">共 {{ cmtTotal }} 条回复</span>
                  <el-pagination layout="prev, pager, next" :total="cmtTotal" :page-size="20"
                    :current-page="cmtPage" @current-change="loadCmts" background small />
                </div>
              </div>
            </el-drawer>
          </template>

          <!-- 面板 7: 用户留言反馈与管理员答复 -->
          <section v-else-if="cur === 'feedback'" class="panel-section">
            <div class="section-head-bar">
              <div class="section-head">
                <h2 class="section-title">用户留言反馈治理</h2>
                <span class="section-desc">已拆分至安全网关 admin/feedback 专属鉴权通道，支持管理员权威答复</span>
              </div>
              <el-button size="small" class="tool-btn-ghost" @click="loadFeedbacks(fbPage)">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 4px">
                  <polyline points="23 4 23 10 17 10" />
                  <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
                </svg>
                刷新反馈
              </el-button>
            </div>

            <div class="table-frame">
              <el-table :data="fbRows" v-loading="fbLoading" size="small" class="craft-table">
                <el-table-column prop="id" label="ID" width="70">
                  <template #default="{ row }">
                    <span class="id-pill">#{{ row.id }}</span>
                  </template>
                </el-table-column>
                <el-table-column prop="userid" label="用户标识" width="120">
                  <template #default="{ row }">
                    <span class="uid-pill">UID: {{ row.userid }}</span>
                  </template>
                </el-table-column>
                <el-table-column prop="messsage" label="反馈诉求内容" min-width="240" show-overflow-tooltip />
                <el-table-column prop="createtime" label="来函时间" width="165" />
                <el-table-column label="管理操作" width="130" align="center">
                  <template #default="{ row }">
                    <el-button link type="primary" size="small" @click="openReplyDlg(row)">回复</el-button>
                    <el-button link type="danger" size="small" @click="delFeedback(row)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>

            <div class="crud-pager">
              <span class="total-caption">共 {{ fbTotal }} 份用户来函</span>
              <el-pagination layout="prev, pager, next" :total="fbTotal" :page-size="15"
                :current-page="fbPage" @current-change="loadFeedbacks" background small />
            </div>

            <!-- 回复弹窗 -->
            <el-dialog v-model="fbReplyDlg" :title="`答复用户反馈来函 #${curFb?.id}`" width="min(520px, calc(100vw - 32px))" class="craft-dialog">
              <div v-if="curFb" class="reply-target-box">
                <div class="quote-eyebrow">用户原始来函：</div>
                <div class="quote-body">{{ curFb.messsage }}</div>
              </div>
              <el-form label-width="70px" class="craft-form">
                <el-form-item label="答复文辞">
                  <el-input v-model="fbReplyMsg" type="textarea" :rows="5" placeholder="请输入答复内容，提交后用户将在个人中心查收此回函..." />
                </el-form-item>
              </el-form>
              <template #footer>
                <div class="dialog-footer">
                  <el-button size="small" @click="fbReplyDlg = false">暂不回复</el-button>
                  <el-button size="small" type="primary" :loading="fbSubmitting" @click="submitFbReply">发送答复回函</el-button>
                </div>
              </template>
            </el-dialog>
          </section>

          <!-- 面板 8: 用户账号管控 -->
          <AdminCrud v-else-if="cur === 'user'"
            hint="全站注册账号身份池；执行封禁后网关拦截器将彻底阻断该账号验签"
            :columns="[
              { prop: 'id', label: 'ID', width: 80 },
              { prop: 'username', label: '账号名', width: 140 },
              { prop: 'name', label: '用户昵称', width: 120 },
              { prop: 'email', label: '安全邮箱', tooltip: true },
              { prop: 'status', label: '账号状态', width: 95, formatter: (r: any) => (r.status === 1 || r.status === '1' ? '正常运行' : '已封禁') },
            ]"
            :formFields="[]"
            :list="userPage" :action-width="130">
            <template #row="{ row }">
              <el-button v-if="row.status != 1" link type="success" size="small" @click="toggle(row, 1)">解除封禁</el-button>
              <el-button v-else link type="warning" size="small" @click="toggle(row, 0)">予以封禁</el-button>
            </template>
          </AdminCrud>

          <!-- 面板 9: 全站置顶公告 -->
          <AdminCrud v-else-if="cur === 'notice'"
            hint="全站系统通告；前台游客与注册用户端即时刷新生效"
            :columns="[
              { prop: 'id', label: 'ID', width: 80 },
              { prop: 'name', label: '通告标题', tooltip: true },
              { prop: 'contents', label: '通告正文', tooltip: true },
            ]"
            :formFields="[
              { prop: 'name', label: '标题' },
              { prop: 'contents', label: '公告正文', type: 'textarea' },
            ]"
            :list="noticePage" :add="noticeAdd" :update="noticeUpdate" :remove="noticeDelete" />
        </main>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import AppNav from '@/components/AppNav.vue'
import AdminCrud from '@/components/AdminCrud.vue'
import { useAdminStore } from '@/store/admin'
import {
  poemPage, poemAdd, poemUpdate, poemDelete,
  writerPage, writerAdd, writerUpdate, writerDelete,
  rhesisPage, rhesisAdd, rhesisUpdate, rhesisDelete,
  blogPage, blogDelete, blogComments, commentDelete,
  userPage, userDisable,
  noticePage, noticeAdd, noticeUpdate, noticeDelete,
  kbSyncStats, kbSyncTrigger,
  adminFeedbackPage, adminFeedbackDelete, adminFeedbackReply,
  cacheStats, cacheWarmup, cacheClear
} from '@/api/adminApi'

const admin = useAdminStore()
const cur = ref('kb')

const selectMenu = (key: string) => {
  cur.value = key
  if (key === 'cache') {
    loadCacheStats()
  } else if (key === 'feedback') {
    loadFeedbacks(1)
  }
}

/* KB 同步 */
const kb = ref<any>({})
const kbLoading = ref(false)
const syncing = ref(false)
const loadKb = async () => {
  kbLoading.value = true
  try { kb.value = await kbSyncStats() } catch { kb.value = {} } finally { kbLoading.value = false }
}
const doSync = async () => {
  syncing.value = true
  try {
    const r = await kbSyncTrigger()
    ElMessage.success(r?.accepted ? '已触发后台增量同步' : (r?.reason || '已触发同步任务'))
    setTimeout(loadKb, 3000)
  } catch { /* 请求层统一显示失败提示。 */ } finally { syncing.value = false }
}

/* 多级缓存监控 */
const cacheInfo = ref<any>({})
const cacheLoading = ref(false)
const warmingUp = ref(false)
const warmUpMsg = ref('')

const loadCacheStats = async () => {
  cacheLoading.value = true
  try {
    cacheInfo.value = await cacheStats()
  } catch {
    cacheInfo.value = {}
  } finally {
    cacheLoading.value = false
  }
}

const doWarmUpCache = async () => {
  warmingUp.value = true
  try {
    const res = await cacheWarmup()
    warmUpMsg.value = `预热成功: 诗词 ${res?.poemCount ?? 0} 首, 诗人 ${res?.writerCount ?? 0} 位 (耗时 ${res?.durationMs ?? 0}ms)`
    ElMessage.success('布隆过滤器全量预热成功')
    await loadCacheStats()
  } catch { /* 请求层统一显示失败提示。 */ } finally {
    warmingUp.value = false
  }
}

const doClearL1Cache = async () => {
  try {
    await cacheClear()
    ElMessage.success('当前节点本地 L1 缓存已清空')
    await loadCacheStats()
  } catch { /* 请求层统一显示失败提示。 */ }
}

/* 用户反馈管理 */
const fbRows = ref<any[]>([])
const fbTotal = ref(0)
const fbPage = ref(1)
const fbLoading = ref(false)
const fbReplyDlg = ref(false)
const curFb = ref<any>(null)
const fbReplyMsg = ref('')
const fbSubmitting = ref(false)

const loadFeedbacks = async (p = 1) => {
  fbPage.value = p
  fbLoading.value = true
  try {
    const res = await adminFeedbackPage(p, 15)
    fbRows.value = res?.records ?? []
    fbTotal.value = Number(res?.total ?? 0)
  } catch {
    fbRows.value = []
  } finally {
    fbLoading.value = false
  }
}

const openReplyDlg = (row: any) => {
  curFb.value = row
  fbReplyMsg.value = ''
  fbReplyDlg.value = true
}

const submitFbReply = async () => {
  if (!fbReplyMsg.value.trim()) {
    ElMessage.warning('请输入回复内容')
    return
  }
  fbSubmitting.value = true
  try {
    await adminFeedbackReply({
      feedbackid: curFb.value.id,
      message: fbReplyMsg.value.trim(),
      userid: curFb.value.userid,
    })
    ElMessage.success('已向用户发送答复回函')
    fbReplyDlg.value = false
    loadFeedbacks(fbPage.value)
  } catch { /* 请求层统一显示失败提示。 */ } finally {
    fbSubmitting.value = false
  }
}

const delFeedback = async (row: any) => {
  try {
    await adminFeedbackDelete(row.id)
    ElMessage.success('反馈记录已删除')
    loadFeedbacks(fbPage.value)
  } catch { /* 请求层统一显示失败提示。 */ }
}

/* 用户封禁/解封 */
const toggle = async (row: any, status: number) => {
  try {
    await userDisable(status, row.id)
    ElMessage.success(status === 1 ? '已解除封禁' : '已予以封禁')
    row.status = status
  } catch { /* 请求层统一显示失败提示。 */ }
}

/* 评论抽屉 */
const cmtDlg = ref(false)
const cmtBlogId = ref(0)
const cmtRows = ref<any[]>([])
const cmtTotal = ref(0)
const cmtPage = ref(1)
const cmtLoading = ref(false)
const openComments = (row: any) => { cmtBlogId.value = row.id; cmtPage.value = 1; cmtDlg.value = true; loadCmts(1) }
const loadCmts = async (p: number) => {
  cmtPage.value = p; cmtLoading.value = true
  try {
    const d = await blogComments(cmtBlogId.value, p, 20)
    cmtRows.value = d?.records ?? []
    cmtTotal.value = Number(d?.total ?? 0)
  } catch { cmtRows.value = [] } finally { cmtLoading.value = false }
}
const delCmt = async (row: any) => {
  try {
    await commentDelete([row.id])
    ElMessage.success('已删除违规评论')
    loadCmts(cmtPage.value)
  } catch { /* 请求层统一显示失败提示。 */ }
}

onMounted(() => { if (admin.token) loadKb() })
</script>

<style scoped>
.content-admin-page {
  min-height: 100dvh;
}

.ca-container {
  max-width: 1220px;
  margin: 0 auto;
  padding: 36px 24px 72px;
}

/* ===== 顶部中台 Header ===== */
.ca-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--md-outline-variant);
 flex-wrap: wrap;  gap: 16px; }

.title-row {
  display: flex;
  align-items: center;
  gap: 12px;
 flex-wrap: wrap; }

.ca-title {
  font-family: var(--f-sans);
  font-size: 24px;
  font-weight: 500;
  letter-spacing: normal;
  color: var(--md-on-surface);
  margin: 0;
}

.meta-badge {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 10.5px;
  letter-spacing: normal;
  color: var(--md-primary);
  border: 1px solid var(--md-outline-variant);
  padding: 2px 7px;
  border-radius: 12px;
  background: var(--md-primary-container);
}

.ca-desc {
  font-size: 13px;
  color: var(--md-on-surface-variant);
  letter-spacing: normal;
  margin: 6px 0 0;
}

.ca-header-right {
  display: flex;
  align-items: center;
  gap: 14px;
 flex-wrap: wrap; }

.operator-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
  color: var(--md-on-surface-variant);
  background: var(--md-surface-container);
  border: 1px solid var(--md-outline-variant);
  padding: 5px 10px;
  border-radius: 12px;
}

.dot-online {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--md-success);
  box-shadow: var(--shadow-sm);
}

.nav-console-btn {
  font-size: 13px;
  letter-spacing: normal;
  color: var(--md-on-surface);
  background: var(--md-surface-container);
  border: 1px solid var(--md-outline-variant);
  padding: 5px 12px;
  border-radius: 12px;
  transition: all 0.2s ease;
}

.nav-console-btn:hover {
  color: var(--md-primary);
  border-color: var(--md-outline-variant);
  background: var(--md-primary-container);
}

/* ===== 未登录门 ===== */
.unauth-box {
  padding: 48px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.lock-icon {
  color: var(--md-primary);
  opacity: 0.85;
}

.unauth-text {
  font-size: 14px;
  color: var(--md-on-surface-variant);
  letter-spacing: normal;
}

.unauth-btn {
  font-size: 13px;
  color: var(--md-on-primary);
  background: var(--md-primary);
  padding: 7px 18px;
  border-radius: 12px;
  font-weight: 500;
  letter-spacing: normal;
}

/* ===== 主体架构 ===== */
.ca-shell {
  display: flex;
  gap: 18px;
  align-items: flex-start;
}

/* 侧边导航 */
.ca-sidebar {
  width: 200px;
  flex-shrink: 0;
  padding: 12px 8px;
}

.ca-nav-groups {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.nav-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.group-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--md-on-surface-variant);
  text-transform: uppercase;
  letter-spacing: normal;
  padding: 4px 10px 6px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 999px;
  font-size: 13px;
  color: var(--md-on-surface-variant);
  cursor: pointer;
  user-select: none;
  transition: all 0.16s ease;
 min-height: 48px;  border: 1px solid transparent;  text-align: left;  background: transparent;  width: 100%;  font-family: var(--f-sans); }

.nav-item:hover {
  background: var(--md-surface-container);
  color: var(--md-on-surface);
}

.nav-item.active {
  background: var(--md-primary-container);
  font-weight: 500;
  border: 1px solid var(--md-outline-variant);
  box-shadow: var(--shadow-sm); ;
  color: var(--md-on-primary-container);
  border-color: var(--md-primary-container);
}

.item-icon {
  flex-shrink: 0;
  opacity: 0.85;
}

.nav-item.active .item-icon {
  opacity: 1;
}

/* 右侧工作台面板 */
.ca-main-panel {
  flex: 1;
  padding: 22px 24px;
  min-width: 0;
}

.panel-section {
  display: flex;
  flex-direction: column;
}

.section-head {
  margin-bottom: 16px;
}

.section-head-bar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.section-title {
  font-family: var(--f-sans);
  font-size: 17px;
  font-weight: 500;
  letter-spacing: normal;
  color: var(--md-on-surface);
  margin: 0 0 4px;
}

.section-desc {
  font-size: 13px;
  color: var(--md-on-surface-variant);
  letter-spacing: normal;
}

/* ===== 遥测大盘卡片 (Telemetry Grid) ===== */
.telemetry-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}

.telemetry-card {
  background: var(--md-surface-container-low);
  border: 1px solid var(--md-outline-variant);
  border-radius: 24px;
  padding: 16px 14px;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.telemetry-card:hover {
  border-color: var(--md-outline-variant);
  box-shadow: var(--shadow-sm);
}

.card-eyebrow {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  color: var(--md-on-surface-variant);
  letter-spacing: normal;
  margin-bottom: 8px;
}

.card-value {
  font-family: var(--f-sans);
  font-size: 26px;
  font-weight: 500;
  line-height: 1.15;
  color: var(--md-on-surface);
  font-variant-numeric: tabular-nums;
  margin-bottom: 4px;
}

.card-sub {
  font-size: 13px;
  color: var(--md-on-surface-variant);
  letter-spacing: normal;
}

.subtle-pill {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 9.5px;
  letter-spacing: normal;
  color: var(--md-on-surface-variant);
  background: var(--md-surface-container);
  padding: 1px 5px;
  border-radius: 12px;
}

.status-pill {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 9.5px;
  letter-spacing: normal;
  padding: 1px 5px;
  border-radius: 12px;
}

.pill-good {
  color: var(--md-success);
  background: var(--md-success-container);
  border: 1px solid var(--md-outline-variant);
}

.pill-warn {
  color: var(--md-error);
  background: var(--md-error-container);
  border: 1px solid var(--md-outline-variant);
}

.pill-gold {
  color: var(--md-primary);
  background: var(--md-primary-container);
  border: 1px solid var(--md-outline-variant);
}

.val-warn {
  color: var(--md-error) !important;
}

/* ===== 操作工具条 ===== */
.craft-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  background: var(--md-surface-container);
  border: 1px solid var(--md-outline-variant);
  border-radius: 12px;
  gap: 12px;
  flex-wrap: wrap;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.tool-btn-ghost {
  display: inline-flex;
  align-items: center;
  background: var(--md-surface-container);
  border: 1px solid var(--md-outline-variant);
  color: var(--md-on-surface);
  font-size: 13px;
  transition: all 0.18s;
}

.tool-btn-ghost:hover {
  background: var(--md-surface-container);
  color: var(--md-on-surface);
}

.tool-btn-gold {
  display: inline-flex;
  align-items: center;
  font-size: 13px;
  letter-spacing: normal;
}

.tool-btn-danger {
  font-size: 13px;
  color: var(--md-error);
  background: var(--md-error-container);
  border: 1px solid var(--md-outline-variant);
}

.tool-btn-danger:hover {
  background: var(--md-error-container);
  color: var(--md-error);
}

.audit-log {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
  color: var(--md-on-surface-variant);
}

/* ===== 表格与分页统一样式 ===== */
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
  padding: 8px 0;
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

.uid-pill {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
  color: var(--md-primary);
  background: var(--md-primary-container);
  padding: 2px 6px;
  border-radius: 12px;
  border: 1px solid var(--md-outline-variant);
}

.crud-pager {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 14px;
  padding: 4px 2px;
}

.total-caption {
  font-size: 13px;
  color: var(--md-on-surface-variant);
  font-variant-numeric: tabular-nums;
}

/* 弹窗与回复对话框 */
.reply-target-box {
  background: var(--md-primary-container);
  border: 1px solid var(--md-outline-variant);
  border-radius: 12px;
  padding: 12px 14px;
  margin-bottom: 16px;
}

.quote-eyebrow {
  font-size: 13px;
  color: var(--md-on-surface-variant);
  margin-bottom: 4px;
}

.quote-body {
  font-size: 13.5px;
  color: var(--md-on-surface);
  line-height: 1.6;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

:deep(.el-button) { min-height: 44px; border-radius: 999px; font-family: var(--f-sans); letter-spacing: normal; }
:deep(.el-input__wrapper) { min-height: 48px; border-radius: 12px; }
:deep(.el-textarea__inner) { border-radius: 12px; font-size: 15px; }
:deep(.el-tabs__item) { min-height: 48px; font-family: var(--f-sans); letter-spacing: normal; }
:deep(.el-dialog) { max-width: calc(100vw - 32px); border-radius: 28px; }
.form-error { font-size: 14px; line-height: 1.5; color: var(--md-error); background: var(--md-error-container); border-radius: 12px; padding: 12px 16px; }

button, .cs-nav-btn, .nav-content-btn, .nav-console-btn, .unauth-btn { min-height: 44px; border-radius: 999px; } .crud-container, .tab-panel, .panel-section, .ca-container, .cs-container { min-width: 0; max-width: 100%; } .craft-input { min-height: 48px; max-width: 100%; border-radius: 12px; } .crud-pager, .dialog-actions, .dialog-footer, .craft-toolbar, .toolbar-left, .toolbar-right { gap: 12px; flex-wrap: wrap; }
@media (max-width: 900px) { .ca-container { padding: 24px 16px 64px; } .ca-shell { flex-direction: column; } .ca-sidebar { width: 100%; padding: 16px; } .ca-nav-groups { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; } .ca-main-panel { width: 100%; padding: 20px 16px; } .telemetry-grid { grid-template-columns: repeat(auto-fit, minmax(min(100%, 200px), 1fr)); } .section-head-bar { flex-wrap: wrap; } :deep(.craft-drawer) { width: min(560px, 100vw) !important; } .drawer-content { overflow-x: auto; } }
</style>
