# Material 3 前端实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 全站采用蓝色 Material 3，并完成搜索阅读、AI 对话和表单反馈的交互改进。

**Architecture:** 统一 semantic CSS tokens 与 Element Plus 映射；App.vue 决定页面框架间距，现有 AppNav 提供自适应导航。各业务页面拥有自己的数据状态和交互，按照文件所有权并行，最终整合验证。

**Tech Stack:** 现有 Vue 3、TypeScript、Vue Router、Pinia、Element Plus、Vitest。

**Spec:** docs/superpowers/specs/2026-11-03-material3-frontend-design.md

## Global Constraints

- Vue 3、TypeScript、Vue Router、Pinia、Element Plus 沿用当前安装版本；不引入新的 UI 框架或动画依赖。
- 默认浅色，主色 #0B57D0，浅色主色容器 #D3E3FD，页面 #F8FAFD，主文字 #1F1F1F。配套深色使用 #A8C7FA 主色和 #131314 页面底色。
- 界面使用已安装 Noto Sans SC；仅诗词正文和诗词卡片保留 Noto Serif SC。
- 保留 /agent/workflow、token header、sessionId、现有 meta/trace/tool_status/token/action/done SSE 与 API 契约；不修改 Java/Python 后端。
- 不重置、清理或提交原有未提交修改。文件所有权互不重叠；公共 CSS 由 Task 1 独占。
- 现有收藏、诗集、典故、卡片导出、声景、管理动作都必须保留。

### Task 1: 设计系统、主题与自适应导航

**Files:** 修改 src/App.vue、src/main.ts、src/assets/main.css、src/components/AppNav.vue；新增 src/assets/material3.css、src/composables/useTheme.ts、tests/material3/theme.spec.ts、tests/material3/navigation.spec.ts。

**Interfaces:** 产生 CSS tokens --md-primary、--md-on-primary、--md-primary-container、--md-on-primary-container、--md-surface、--md-surface-container、--md-on-surface、--md-on-surface-variant、--md-outline、--md-error。旧 --paper、--paper-card、--ink-*、--gold、--cinnabar 映射到语义色。useTheme() 返回 theme 与 toggleTheme()，App.vue 和 AppNav 共用同一实例。

- [x] 先写主题保存/切换及导航菜单 Escape/选中路由的行为测试，并运行确认失败。例如：

```ts
const theme = useTheme()
theme.toggleTheme()
expect(document.documentElement.classList.contains('dark')).toBe(true)
expect(localStorage.getItem('poetry-theme')).toBe('dark')
```

- [x] 在 main.ts 初始化主题，移除强制 dark；tokens 浅深配对；既有主样式改为 M3 全站规则，保留兼容 class 与 v-reveal 静态降级。
- [x] 实现桌面分组侧栏及手机抽屉；已有图标库提供统一图标。drawer 打开时移动焦点，关闭时还原；路由变化关闭；徽标与退出保持现有业务。App.vue 按 login/console/user 分组添加根 class。
- [x] 添加可见 focus、state layer、按钮输入/卡片/EP dialog/popover/menu/message/table 的映射；不要靠大范围 !important 把所有页面强制涂色。
- [x] 运行两个新测试与已有 router/store 测试；记录命令和结果，交回任务审查。

### Task 2: 搜索与阅读

**Files:** 修改 src/views/PoetryList.vue、src/views/PoemDetail.vue、src/components/AgeTabs.vue、src/router/index.ts；必要时新增 src/composables/usePoetrySearch.ts、tests/material3/search.spec.ts、tests/material3/reader.spec.ts。

**Interfaces:** 消费 Task 1 tokens。列表 query 使用 q、dynasty、page；诗词到 AI 使用 query poemTitle、poemId，AI 显示草稿并由用户提交。保留旧诗词路径和 id query。

- [x] 为 AgeTabs native button/aria-pressed、URL 条件恢复、旧请求不能覆盖新查询与错误重试写行为测试，确认合理失败。例如：

```ts
const chips = wrapper.findAll('button.at')
await chips[1].trigger('click')
expect(wrapper.emitted('change')?.[0]).toEqual(['唐代'])
expect(chips[1].attributes('type')).toBe('button')
```

- [x] 把搜索与过滤放入首屏；推荐诗使用 M3 卡片而非满屏夜景；保留热词、建议、全部朝代、分页和声音/卡片功能。
- [x] 使用 native links/buttons、combobox 键盘与 IME guard；请求 epoch 或 cleanup 防止过时响应。query 状态加载和更新保证不形成循环。
- [x] 列表保持成功数据并区分 refreshing/error/empty；点击 retry 再请求。路由 scrollBehavior 返回 savedPosition，页面回访有自己的状态恢复。
- [x] 详情添加返回、pending 收藏、加载诗集/错误/空提示、弹窗视口限宽、可键盘点击典故、适应窄屏的动作；标题和 id 传入 AI query。
- [x] 修改对应 scoped CSS，使用约定 tokens；运行新测试、AgeTabs 与 router 测试并交回审查。

### Task 3: AI 对话

**Files:** 修改 src/views/AiChat.vue；必要时新增 src/components/chat/ChatComposer.vue、src/composables/useChatScroll.ts、src/utils/chatInput.ts、tests/material3/chat.spec.ts。

**Interfaces:** 消费 Task 1 tokens 和 Task 2 的 poemTitle/poemId query；保持所有 SSE、发布草稿与 session 协议。composer 发出 send/stop，草稿保留在页面，停止仅取消前端请求接收。

- [x] 为中文 composition+Enter 不发送、Shift+Enter 换行、停止中止请求并保留输出、离底阅读不被拉回写必要行为测试，确认合理失败。例如：

```ts
expect(shouldSubmit({ key: 'Enter', shiftKey: false, isComposing: true })).toBe(false)
expect(shouldSubmit({ key: 'Enter', shiftKey: true, isComposing: false })).toBe(false)
```

- [x] 多行 composer、清晰发送/停止、生成时可编辑草稿；query poemTitle 首次生成可编辑草稿，不自动发送。stop 使用 AbortController 并区分用户停止与失败。
- [x] waiting/researching/streaming/stopped/failed 状态与对应轮次重试；不能重复用户消息，HTTP/SSE 错误持久呈现，确认反馈 HTTP 成功才显示已提交。
- [x] 手机历史抽屉与桌面侧面板，历史加载/错误/空状态；来源 expander/history 行使用真实按钮和 aria-expanded。
- [x] 距底部约 80px 内才跟随 token；暂停跟随时有“查看最新回复”；reduced-motion 下关闭闪烁。保留来源、工具事件及编辑发布草稿。
- [x] 运行新 AI 行为测试并交回审查。

### Task 4: 其余页面、表单与管理页

**Files:** 修改 src/views/Login.vue、Forum.vue、UserCenter.vue、Feedback.vue、Writers.vue、Rhesis.vue、ReviewToday.vue、Notice.vue、NotFound.vue、Console.vue、ContentAdmin.vue、src/components/AdminCrud.vue、src/components/soundscape/SoundscapeWidget.vue、src/components/card/PoemCardModal.vue。不修改前三项独占文件。诗词卡片导出图保留其古典视觉，仅弹窗控件迁移 Material 3。

**Interfaces:** 消费 Task 1 tokens，现有 API 和 STOMP 保持；表单字段验证在当前表单拥有者完成，避免建立通用巨大 form 控制器。

- [x] 为登录字段错误/提交重复保护等新增行为建立必要测试；纯视觉改变只做浏览器检查。
- [x] 改造登录为明亮 M3 面板；邮箱/密码 label、autocomplete 与 supporting error；提交 loading、失败保留输入。论坛/个人/反馈同样就地错误和提交状态。
- [x] 更新其余页面 scoped CSS：统一 UI 黑体、卡片形状、chips、tabs、按钮、可读字号；旧深色字/底硬编码映射 tokens；不要只给页面追加无限覆盖。
- [x] 管理页保留所有现有接口和分区，使用 M3 高密度布局；移动端表格容器滚动而非整个视口溢出。
- [x] 运行覆盖新行为的测试并交回审查。

### Task 5: 整合、浏览器验证与审查

- [x] 完整 Vitest：在 frontend 执行 node node_modules/vitest/vitest.mjs run。
- [x] 类型与构建：在 frontend 执行 node node_modules/vue-tsc/bin/vue-tsc.js --noEmit，然后 node node_modules/vite/bin/vite.js build。
- [x] 仅启动 Vite：node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5173 --strictPort。
- [x] 浏览器验证 390/768/1440px 浅深色、导航、登录、搜索、详情、AI、控制台。真实后端不可用时使用明确的浏览器请求替身检查状态，报告哪些业务没有联机验证。
- [x] 对照任务基线生成 diff review package，分别检查 spec compliance 和 code quality；修复有效发现，运行受影响检查。
- [x] 输出实际测试结果、截图和未验证的服务范围；保留当前功能分支供用户查看，按授权范围不自动提交或发布。

## 完成记录（2026-11-03）

全站蓝色 Material 3 已实现；四项独立任务均通过规范与质量审查。最终完整 Vitest：17 文件、216 测试通过；vue-tsc 无诊断；Vite 构建 exit 0（2449 模块）。浏览器完成 390/768/1440px 浅深主题与导航、搜索阅读、聊天、表单及管理布局验证。修复了收藏快照并发、旧对话重试状态、跳转主要内容、评论提交后的刷新反馈、管理请求错误反馈以及悬浮控件与聊天发送按钮重叠。

浏览器业务请求使用明确的替身；真实登录、数据库写入、模型输出、推送、播放和下载未做联机验收。仅启动 Vite，保留当前功能分支和所有原有修改，没有提交或发布。截图和交付记录保存于本会话 outputs/material3-delivery.md。
