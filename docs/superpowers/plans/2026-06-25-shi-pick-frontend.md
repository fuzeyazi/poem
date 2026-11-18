# 拾诗 (Pick Poem) Frontend — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the MVP frontend for "拾诗", a desktop-first Web app for reading classical Chinese poetry with a Song-dynasty-inspired visual aesthetic.

**Architecture:** Vue 3 SPA + Vite + TypeScript + Pinia + Vue Router + Naive UI (themed). Desktop-first responsive layout. Mock data first, then real API integration. JWT auth with email + username/password login.

**Tech Stack:**
- Vue 3.4+ (`<script setup>` composition API)
- TypeScript 5+
- Vite 5+
- Vue Router 4
- Pinia 2
- Naive UI 2.38+
- Axios 1.6+
- VueUse 10+
- Vitest 1+ (unit tests only for utils/stores/api layer)
- ESLint 8+ + Prettier 3+
- 思源宋体 (Source Han Serif SC) via Google Fonts CDN

**Project location:** `E:\javatexts\frontend\shi-pick\`

**Spec:** `docs/superpowers/specs/2026-06-25-shi-pick-design.md`

---

## File Structure

```
E:\javatexts\frontend\shi-pick\
├── public/
│   └── favicon.svg
├── src/
│   ├── api/
│   │   ├── request.ts             # axios instance + interceptors
│   │   ├── poem.ts                # poem endpoints
│   │   ├── author.ts              # author endpoints
│   │   ├── user.ts                # auth + favorites endpoints
│   │   └── paths.ts               # path constants
│   ├── assets/
│   │   ├── images/                # 5-8 hero images
│   │   └── svg/
│   │       └── stamp-seal.svg     # seal SVG source
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppHeader.vue
│   │   │   ├── AppFooter.vue
│   │   │   └── AppLayout.vue
│   │   ├── poem/
│   │   │   ├── PoemCard.vue
│   │   │   ├── PoemContent.vue
│   │   │   └── PoemAnnotation.vue
│   │   └── common/
│   │       ├── StampSeal.vue
│   │       ├── EmptyState.vue
│   │       └── SkeletonLoader.vue
│   ├── views/
│   │   ├── HomeView.vue
│   │   ├── PoemListView.vue
│   │   ├── PoemDetailView.vue
│   │   ├── AuthorView.vue
│   │   ├── FavoritesView.vue
│   │   ├── LoginView.vue
│   │   ├── MeView.vue
│   │   └── NotFoundView.vue
│   ├── router/
│   │   └── index.ts
│   ├── stores/
│   │   ├── user.ts
│   │   └── favorites.ts
│   ├── styles/
│   │   ├── theme.ts               # Naive UI themeOverrides
│   │   ├── tokens.ts              # design tokens (colors/spacing/fonts)
│   │   └── global.css
│   ├── types/
│   │   ├── poem.ts
│   │   ├── author.ts
│   │   ├── user.ts
│   │   └── api.ts
│   ├── utils/
│   │   ├── auth.ts                # token storage
│   │   └── format.ts
│   ├── App.vue
│   ├── main.ts
│   └── mock-index.ts              # re-exports for views
├── tests/
│   ├── api/
│   │   └── request.test.ts
│   ├── stores/
│   │   ├── user.test.ts
│   │   └── favorites.test.ts
│   └── utils/
│       ├── auth.test.ts
│       └── format.test.ts
├── mock/
│   ├── poems.ts                   # 10 sample poems
│   └── authors.ts                 # 6 sample authors
├── index.html
├── vite.config.ts
├── tsconfig.json
├── tsconfig.node.json
├── package.json
├── .eslintrc.cjs
├── .prettierrc.json
├── .gitignore
├── .env.development
└── README.md
```

---


## Phase 1 (continued)

### Task 1.3: 设计 tokens + 全局样式

**Files:**
- Create: `src/styles/tokens.ts`
- Create: `src/styles/global.css`

- [ ] **Step 1: 写入 src/styles/tokens.ts**

```typescript
// 拾诗 - 设计 tokens (石青黛影)
export const colors = {
  bgPrimary: '#ece5d5',
  bgSecondary: '#f5f0e1',
  primary: '#2d4a52',
  accent: '#d97757',
  ink: '#1a1a1a',
  inkMuted: '#888888',
  border: '#e5dccb',
  divider: '#c9bfa6'
} as const

export const spacing = {
  xs: '4px', sm: '8px', md: '16px', lg: '24px', xl: '32px', xxl: '64px'
} as const

export const fonts = {
  serif: '"Noto Serif SC", "Source Han Serif SC", "Songti SC", serif',
  sans: '"PingFang SC", "Microsoft YaHei", system-ui, sans-serif',
  kai: 'KaiTi, "STKaiti", serif'
} as const

export const radii = { sm: '4px', md: '6px' } as const
```

- [ ] **Step 2: 写入 src/styles/global.css**

```css
:root {
  --color-bg-primary: #ece5d5;
  --color-bg-secondary: #f5f0e1;
  --color-primary: #2d4a52;
  --color-accent: #d97757;
  --color-ink: #1a1a1a;
  --color-ink-muted: #888888;
  --color-border: #e5dccb;
  --color-divider: #c9bfa6;
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 32px;
  --space-xxl: 64px;
  --font-serif: 'Noto Serif SC', 'Source Han Serif SC', 'Songti SC', serif;
  --font-sans: 'PingFang SC', 'Microsoft YaHei', system-ui, sans-serif;
  --font-kai: KaiTi, 'STKaiti', serif;
}

* { box-sizing: border-box; }

html, body {
  margin: 0; padding: 0;
  background: var(--color-bg-primary);
  color: var(--color-ink);
  font-family: var(--font-sans);
  font-size: 15px;
  line-height: 1.7;
  -webkit-font-smoothing: antialiased;
}

#app { min-height: 100vh; }

a { color: var(--color-primary); text-decoration: none; transition: color 0.2s ease; }
a:hover { color: var(--color-accent); }

.poem-text {
  font-family: var(--font-serif);
  letter-spacing: 6px;
  line-height: 2.2;
}

.divider-with-seal {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  color: var(--color-divider);
  margin: var(--space-lg) 0;
}
.divider-with-seal::before, .divider-with-seal::after {
  content: ''; flex: 1; height: 1px; background: var(--color-divider);
}
.divider-with-seal span {
  color: var(--color-accent);
  font-size: 11px;
  letter-spacing: 3px;
}
```

- [ ] **Step 3: 提交**

```powershell
git add src/styles/
git commit -m "feat(styles): add design tokens and global styles"
```

---

### Task 1.4: Naive UI 主题覆盖

**Files:**
- Create: `src/styles/theme.ts`

- [ ] **Step 1: 写入 src/styles/theme.ts**

```typescript
import type { GlobalThemeOverrides } from 'naive-ui'
import { colors } from './tokens'

export const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: colors.primary,
    primaryColorHover: colors.accent,
    primaryColorPressed: colors.primary,
    primaryColorSuppl: colors.primary,
    infoColor: colors.primary,
    successColor: '#5b8c5a',
    warningColor: colors.accent,
    errorColor: '#c1452b',
    bodyColor: colors.bgPrimary,
    cardColor: colors.bgSecondary,
    modalColor: colors.bgSecondary,
    popoverColor: colors.bgSecondary,
    textColorBase: colors.ink,
    textColor1: colors.ink,
    textColor2: colors.ink,
    textColor3: colors.inkMuted,
    placeholderColor: colors.inkMuted,
    borderColor: colors.border,
    dividerColor: colors.divider,
    borderRadius: '4px',
    borderRadiusSmall: '4px',
    fontFamily: '"PingFang SC", "Microsoft YaHei", system-ui, sans-serif'
  },
  Button: { fontWeight: '400', borderRadiusMedium: '4px' },
  Input: {
    border: '1px solid #e5dccb',
    borderHover: '1px solid #2d4a52',
    borderFocus: '1px solid #d97757',
    boxShadowFocus: 'none'
  },
  Card: { borderColor: '#e5dccb', borderRadius: '6px' }
}
```

- [ ] **Step 2: 提交**

```powershell
git add src/styles/theme.ts
git commit -m "feat(styles): add Naive UI theme overrides"
```

---

### Task 1.5: Vue Router + 入口文件

**Files:**
- Create: `src/router/index.ts`, `src/App.vue`, `src/main.ts`

- [ ] **Step 1: 写入 src/router/index.ts**

```typescript
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  { path: '/', name: 'home', component: () => import('@/views/HomeView.vue') },
  { path: '/poems', name: 'poem-list', component: () => import('@/views/PoemListView.vue') },
  { path: '/poems/:id', name: 'poem-detail', component: () => import('@/views/PoemDetailView.vue') },
  { path: '/authors/:id', name: 'author', component: () => import('@/views/AuthorView.vue') },
  { path: '/favorites', name: 'favorites', component: () => import('@/views/FavoritesView.vue'), meta: { requiresAuth: true } },
  { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue') },
  { path: '/me', name: 'me', component: () => import('@/views/MeView.vue'), meta: { requiresAuth: true } },
  { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('@/views/NotFoundView.vue') }
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() { return { top: 0 } }
})

router.beforeEach((to, _from, next) => {
  if (to.meta.requiresAuth) {
    const token = localStorage.getItem('shi-pick-token')
    if (!token) {
      next({ name: 'login', query: { redirect: to.fullPath } })
      return
    }
  }
  next()
})

export default router
```

- [ ] **Step 2: 写入 src/App.vue**

```vue
<script setup lang="ts">
import { NConfigProvider, NMessageProvider } from 'naive-ui'
import { themeOverrides } from '@/styles/theme'
import AppLayout from '@/components/layout/AppLayout.vue'
</script>

<template>
  <NConfigProvider :theme-overrides="themeOverrides">
    <NMessageProvider>
      <AppLayout>
        <RouterView />
      </AppLayout>
    </NMessageProvider>
  </NConfigProvider>
</template>
```

- [ ] **Step 3: 写入 src/main.ts**

```typescript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './styles/global.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
```

- [ ] **Step 4: 提交**

```powershell
git add src/router src/App.vue src/main.ts
git commit -m "feat(router): add vue router + entry files"
```

---

### Task 1.6: Layout 组件（AppLayout / AppHeader / AppFooter / StampSeal + stub stores）

**Files:**
- Create: `src/components/common/StampSeal.vue`
- Create: `src/components/layout/AppHeader.vue`
- Create: `src/components/layout/AppFooter.vue`
- Create: `src/components/layout/AppLayout.vue`
- Create: `src/stores/user.ts` (stub - replaced in Phase 4)
- Create: `src/stores/favorites.ts` (stub - replaced in Phase 4)

- [ ] **Step 1: 写入 src/components/common/StampSeal.vue**

```vue
<script setup lang="ts">
interface Props {
  text?: string
  size?: number
  color?: string
}
withDefaults(defineProps<Props>(), { text: '诗', size: 36, color: '#d97757' })
</script>

<template>
  <div class="stamp-seal" :style="{ width: `${size}px`, height: `${size}px`, borderColor: color, color: color }">
    <span class="stamp-text" :style="{ fontSize: `${size * 0.4}px` }">{{ text }}</span>
  </div>
</template>

<style scoped>
.stamp-seal {
  display: inline-flex; align-items: center; justify-content: center;
  border: 2px solid; border-radius: 4px;
  font-family: var(--font-kai); letter-spacing: 1px; flex-shrink: 0;
}
.stamp-text { font-weight: 600; }
</style>
```

- [ ] **Step 2: 写入 src/components/layout/AppHeader.vue**

```vue
<script setup lang="ts">
import { useRouter } from 'vue-router'
import { NInput, NIcon, NDropdown } from 'naive-ui'
import { SearchOutline, PersonCircleOutline } from '@vicons/ionicons5'
import StampSeal from '@/components/common/StampSeal.vue'
import { ref, watch } from 'vue'
import { useUserStore } from '@/stores/user'
import { useFavoritesStore } from '@/stores/favorites'

const router = useRouter()
const searchKeyword = ref('')
const userStore = useUserStore()
const favStore = useFavoritesStore()

const navItems = [
  { name: 'home', label: '首页', path: '/' },
  { name: 'poem-list', label: '诗库', path: '/poems' },
  { name: 'favorites', label: '收藏', path: '/favorites' },
  { name: 'me', label: '我的', path: '/me' }
]

function onSearch() {
  if (searchKeyword.value.trim()) {
    router.push({ name: 'poem-list', query: { keyword: searchKeyword.value.trim() } })
  }
}

const userMenu = [
  { label: '我的', key: 'me' },
  { label: '收藏', key: 'favorites' },
  { type: 'divider', key: 'd1' },
  { label: '退出', key: 'logout' }
]

function onUserMenu(key: string) {
  if (key === 'logout') {
    userStore.logout()
    favStore.clear()
    router.push('/')
  } else {
    router.push({ name: key })
  }
}

watch(
  () => userStore.isLoggedIn,
  (logged) => {
    if (logged) favStore.load().catch(() => {})
    else favStore.clear()
  },
  { immediate: true }
)
</script>

<template>
  <header class="app-header">
    <div class="header-inner">
      <RouterLink to="/" class="logo">
        <StampSeal text="诗" :size="32" />
        <span class="logo-text">拾诗</span>
        <span class="logo-sub">PICK POEM</span>
      </RouterLink>
      <nav class="nav">
        <RouterLink v-for="item in navItems" :key="item.name" :to="item.path" class="nav-item" active-class="active">
          {{ item.label }}
        </RouterLink>
      </nav>
      <div class="search">
        <NInput v-model:value="searchKeyword" placeholder="搜索诗名、作者..." clearable @keyup.enter="onSearch">
          <template #prefix><NIcon :component="SearchOutline" /></template>
        </NInput>
      </div>
      <div class="user-area">
        <NDropdown :options="userMenu" @select="onUserMenu" trigger="click">
          <NIcon :component="PersonCircleOutline" size="28" class="user-icon" />
        </NDropdown>
      </div>
    </div>
  </header>
</template>

<style scoped>
.app-header {
  position: sticky; top: 0; z-index: 100;
  background: rgba(236, 229, 213, 0.95);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--color-border);
}
.header-inner {
  max-width: 1280px; margin: 0 auto;
  padding: 12px 64px;
  display: flex; align-items: center; gap: 32px;
}
.logo { display: flex; align-items: center; gap: 8px; color: var(--color-primary); }
.logo-text { font-family: var(--font-serif); font-size: 22px; font-weight: 600; letter-spacing: 4px; }
.logo-sub { font-size: 10px; letter-spacing: 2px; color: var(--color-ink-muted); margin-left: 4px; }
.nav { display: flex; gap: 24px; }
.nav-item { font-size: 14px; color: var(--color-ink); padding: 4px 0; position: relative; }
.nav-item:hover, .nav-item.active { color: var(--color-primary); }
.nav-item.active::after {
  content: ''; position: absolute; bottom: -2px; left: 50%; transform: translateX(-50%);
  width: 16px; height: 2px; background: var(--color-accent);
}
.search { flex: 1; max-width: 320px; }
.user-area { margin-left: auto; }
.user-icon { cursor: pointer; color: var(--color-primary); }
@media (max-width: 768px) {
  .header-inner { padding: 12px 16px; gap: 12px; }
  .logo-sub, .nav { display: none; }
}
</style>
```

- [ ] **Step 3: 创建 stub stores (Phase 4 会替换)**

Create `src/stores/user.ts`:
```typescript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
export const useUserStore = defineStore('user', () => {
  const user = ref<any>(null)
  const isLoggedIn = computed(() => false)
  function logout() { user.value = null }
  return { user, isLoggedIn, logout }
})
```

Create `src/stores/favorites.ts`:
```typescript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
export const useFavoritesStore = defineStore('favorites', () => {
  const ids = ref<Set<string>>(new Set())
  const count = computed(() => 0)
  function clear() { ids.value = new Set() }
  function load() { return Promise.resolve() }
  function isFavorited(_id: string) { return false }
  function toggle(_id: string) { return Promise.resolve(false) }
  return { ids, count, clear, load, isFavorited, toggle }
})
```

- [ ] **Step 4: 写入 src/components/layout/AppFooter.vue**

```vue
<template>
  <footer class="app-footer">
    <div class="footer-inner">
      <div class="footer-section">
        <span class="footer-title">拾诗</span>
        <span class="footer-sub">PICK POEM · 桌面端古诗词阅读</span>
      </div>
      <div class="footer-links">
        <a href="#">关于</a><span class="dot">·</span>
        <a href="#">反馈</a><span class="dot">·</span>
        <a href="#">GitHub</a>
      </div>
      <div class="footer-copy">© 2026 · 仅供学习交流</div>
    </div>
  </footer>
</template>

<style scoped>
.app-footer { margin-top: 80px; padding: 32px 0; border-top: 1px solid var(--color-divider); background: var(--color-bg-secondary); }
.footer-inner { max-width: 1280px; margin: 0 auto; padding: 0 64px; display: flex; align-items: center; justify-content: space-between; font-size: 12px; color: var(--color-ink-muted); }
.footer-section { display: flex; flex-direction: column; gap: 4px; }
.footer-title { font-family: var(--font-serif); font-size: 16px; letter-spacing: 4px; color: var(--color-primary); }
.footer-sub { font-size: 10px; letter-spacing: 2px; }
.footer-links { display: flex; gap: 8px; align-items: center; }
.dot { color: var(--color-divider); }
.footer-copy { font-size: 11px; }
@media (max-width: 768px) { .footer-inner { padding: 0 16px; flex-direction: column; gap: 12px; text-align: center; } }
</style>
```

- [ ] **Step 5: 写入 src/components/layout/AppLayout.vue**

```vue
<script setup lang="ts">
import AppHeader from './AppHeader.vue'
import AppFooter from './AppFooter.vue'
</script>

<template>
  <div class="app-layout">
    <AppHeader />
    <main class="app-main"><slot /></main>
    <AppFooter />
  </div>
</template>

<style scoped>
.app-layout { display: flex; flex-direction: column; min-height: 100vh; }
.app-main { flex: 1; max-width: 1280px; width: 100%; margin: 0 auto; padding: 32px 64px; }
@media (max-width: 768px) { .app-main { padding: 16px; } }
</style>
```

- [ ] **Step 6: 提交**

```powershell
git add src/components/ src/stores/
git commit -m "feat(layout): add app header/footer/layout + stamp seal + stub stores"
```

---

### Task 1.7: 占位视图

**Files:** Create 8 placeholder views under `src/views/`.

For each file use this template (replace `LABEL` and `TITLE`):

```vue
<script setup lang="ts">
import StampSeal from '@/components/common/StampSeal.vue'
</script>

<template>
  <div class="placeholder">
    <StampSeal text="LABEL" :size="48" />
    <h2>TITLE</h2>
    <p>Phase 实装</p>
  </div>
</template>

<style scoped>
.placeholder { text-align: center; padding: 80px 0; }
h2 { font-family: var(--font-serif); letter-spacing: 6px; color: var(--color-primary); margin: 16px 0; }
</style>
```

Files (LABEL/TITLE):
- `HomeView.vue` — 首页 / 拾诗
- `PoemListView.vue` — 诗库 / 诗库
- `PoemDetailView.vue` — 详情 / 诗词详情
- `AuthorView.vue` — 作者 / 作者详情
- `FavoritesView.vue` — 收藏 / 我的收藏
- `LoginView.vue` — 登录 / 登录
- `MeView.vue` — 我 / 我的
- `NotFoundView.vue` — 404 / 页面未找到

- [ ] **Steps 1-8: 创建所有占位文件**

- [ ] **Step 9: 提交**

```powershell
git add src/views/
git commit -m "feat(views): add placeholder views for all routes"
```

---

### Task 1.8: favicon + Phase 1 验证

**Files:**
- Create: `public/favicon.svg`

- [ ] **Step 1: 写入 public/favicon.svg**

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" fill="#ece5d5"/>
  <rect x="6" y="6" width="20" height="20" fill="none" stroke="#d97757" stroke-width="2"/>
  <text x="16" y="22" text-anchor="middle" font-family="KaiTi, serif" font-size="14" fill="#d97757" font-weight="600">诗</text>
</svg>
```

- [ ] **Step 2: 启动 dev server 验证**

```powershell
cd E:\javatexts\frontend\shi-pick
npm run dev
```

Visit http://localhost:5173/. Verify:
- 顶部导航有 Logo "拾诗" + 印章
- 4 个导航项
- 首页显示 "拾诗" 大标题 + "卷 · 一" 分隔线
- 各导航切换占位页正常
- Console 无报错

- [ ] **Step 3: 提交**

```powershell
git add public/
git commit -m "feat: add favicon"
```

- [ ] **Step 4: Phase 1 检查点**

Ask user: "Phase 1 完成。视觉风格对路吗？对就回 OK，我接着做 Phase 2。"

---

## Phase 2: 首页 + 诗库 + 详情（Mock 数据） (~4 days)

**Checkpoint**: User can browse poems and see details using local mock data.

### Task 2.1: 类型定义 + Mock 数据

**Files:**
- Create: `src/types/api.ts`, `poem.ts`, `author.ts`, `user.ts`
- Create: `mock/poems.ts`, `mock/authors.ts`, `src/mock-index.ts`

- [ ] **Step 1: 写入 src/types/api.ts**

```typescript
export interface ApiResult<T> { code: number; msg: string; data: T }
export interface PageQuery { page?: number; size?: number; dynasty?: string; author?: string; category?: string; keyword?: string }
export interface PageResult<T> { total: number; list: T[]; page: number; size: number }
```

- [ ] **Step 2: 写入 src/types/poem.ts**

```typescript
export interface Poem {
  id: string
  title: string
  author: string
  authorId: string
  dynasty: string
  content: string[]
  annotation?: string
  translation?: string
  appreciation?: string
  category?: string
  createTime?: string
}
```

- [ ] **Step 3: 写入 src/types/author.ts**

```typescript
export interface Author {
  id: string
  name: string
  dynasty: string
  bio: string
  avatar?: string
  poemCount?: number
}
```

- [ ] **Step 4: 写入 src/types/user.ts**

```typescript
export interface User {
  id: string
  username: string
  email: string
  nickname: string
  avatar?: string
  token: string
}
```

- [ ] **Step 5: 写入 mock/poems.ts** (10 sample poems)

```typescript
import type { Poem } from '@/types/poem'

export const mockPoems: Poem[] = [
  { id: '1', title: '静夜思', author: '李白', authorId: 'a1', dynasty: '唐', content: ['床前明月光，疑是地上霜。', '举头望明月，低头思故乡。'], annotation: '床：指井栏。疑是：好像是。', translation: '明亮的月光洒在床前的窗户纸上，好像地上泛起了一层霜。', appreciation: '这首诗写的是在寂静的月夜思念家乡的感受。', category: '思乡' },
  { id: '2', title: '春晓', author: '孟浩然', authorId: 'a2', dynasty: '唐', content: ['春眠不觉晓，处处闻啼鸟。', '夜来风雨声，花落知多少。'], translation: '春日里贪睡不知不觉天已破晓。', category: '四季' },
  { id: '3', title: '登鹳雀楼', author: '王之涣', authorId: 'a3', dynasty: '唐', content: ['白日依山尽，黄河入海流。', '欲穷千里目，更上一层楼。'], translation: '夕阳依傍着西山慢慢地沉没。', category: '登高' },
  { id: '4', title: '望庐山瀑布', author: '李白', authorId: 'a1', dynasty: '唐', content: ['日照香炉生紫烟，遥看瀑布挂前川。', '飞流直下三千尺，疑是银河落九天。'], category: '山水' },
  { id: '5', title: '早发白帝城', author: '李白', authorId: 'a1', dynasty: '唐', content: ['朝辞白帝彩云间，千里江陵一日还。', '两岸猿声啼不住，轻舟已过万重山。'], category: '山水' },
  { id: '6', title: '黄鹤楼送孟浩然之广陵', author: '李白', authorId: 'a1', dynasty: '唐', content: ['故人西辞黄鹤楼，烟花三月下扬州。', '孤帆远影碧空尽，唯见长江天际流。'], category: '送别' },
  { id: '7', title: '江南春', author: '杜牧', authorId: 'a4', dynasty: '唐', content: ['千里莺啼绿映红，水村山郭酒旗风。', '南朝四百八十寺，多少楼台烟雨中。'], category: '四季' },
  { id: '8', title: '山行', author: '杜牧', authorId: 'a4', dynasty: '唐', content: ['远上寒山石径斜，白云生处有人家。', '停车坐爱枫林晚，霜叶红于二月花。'], category: '四季' },
  { id: '9', title: '咏鹅', author: '骆宾王', authorId: 'a5', dynasty: '唐', content: ['鹅，鹅，鹅，曲项向天歌。', '白毛浮绿水，红掌拨清波。'], category: '咏物' },
  { id: '10', title: '九月九日忆山东兄弟', author: '王维', authorId: 'a6', dynasty: '唐', content: ['独在异乡为异客，每逢佳节倍思亲。', '遥知兄弟登高处，遍插茱萸少一人。'], category: '思乡' }
]

export const mockTodayPoems = [mockPoems[0], mockPoems[3]]
export const mockHotPoems = [mockPoems[0], mockPoems[2], mockPoems[7], mockPoems[9]]
```

- [ ] **Step 6: 写入 mock/authors.ts**

```typescript
import type { Author } from '@/types/author'

export const mockAuthors: Author[] = [
  { id: 'a1', name: '李白', dynasty: '唐', bio: '李白（701年—762年），字太白，号青莲居士，唐代伟大的浪漫主义诗人。', poemCount: 4 },
  { id: 'a2', name: '孟浩然', dynasty: '唐', bio: '孟浩然（689年—740年），唐代著名山水田园派诗人。', poemCount: 1 },
  { id: 'a3', name: '王之涣', dynasty: '唐', bio: '王之涣（688年—742年），唐代著名诗人。', poemCount: 1 },
  { id: 'a4', name: '杜牧', dynasty: '唐', bio: '杜牧（803年—852年），唐代杰出的诗人、散文家。', poemCount: 2 },
  { id: 'a5', name: '骆宾王', dynasty: '唐', bio: '骆宾王，唐代著名诗人，"初唐四杰"之一。', poemCount: 1 },
  { id: 'a6', name: '王维', dynasty: '唐', bio: '王维（约701年—761年），唐代著名诗人、画家。', poemCount: 1 }
]

export const mockDynasties = ['唐', '宋', '元', '明', '清']
export const mockCategories = ['山水', '思乡', '送别', '四季', '登高', '咏物']
```

- [ ] **Step 7: 写入 src/mock-index.ts**

```typescript
export { mockPoems, mockTodayPoems, mockHotPoems } from '../mock/poems'
export { mockAuthors, mockDynasties, mockCategories } from '../mock/authors'
```

- [ ] **Step 8: 提交**

```powershell
git add src/types mock/ src/mock-index.ts
git commit -m "feat(types): add types + mock data"
```

---

### Task 2.2: utils + 单元测试

**Files:**
- Create: `src/utils/auth.ts`, `src/utils/format.ts`
- Create: `tests/utils/auth.test.ts`, `tests/utils/format.test.ts`

- [ ] **Step 1: 写入 src/utils/auth.ts**

```typescript
const TOKEN_KEY = 'shi-pick-token'
const USER_KEY = 'shi-pick-user'

export function getToken(): string | null { return localStorage.getItem(TOKEN_KEY) }
export function setToken(token: string): void { localStorage.setItem(TOKEN_KEY, token) }
export function removeToken(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export function getStoredUser<T>(): T | null {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) return null
  try { return JSON.parse(raw) as T } catch { return null }
}

export function setStoredUser<T>(user: T): void {
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}
```

- [ ] **Step 2: 写入 src/utils/format.ts**

```typescript
export function formatDate(input?: string): string {
  if (!input) return ''
  const d = new Date(input)
  if (isNaN(d.getTime())) return input
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export function truncate(text: string, maxLen: number = 60): string {
  if (text.length <= maxLen) return text
  return text.slice(0, maxLen) + '...'
}
```

- [ ] **Step 3: 写入 tests/utils/auth.test.ts**

```typescript
import { describe, it, expect, beforeEach } from 'vitest'
import { getToken, setToken, removeToken, getStoredUser, setStoredUser } from '@/utils/auth'

describe('auth utils', () => {
  beforeEach(() => { localStorage.clear() })

  it('getToken returns null when no token', () => { expect(getToken()).toBeNull() })
  it('setToken and getToken roundtrip', () => {
    setToken('abc123')
    expect(getToken()).toBe('abc123')
  })
  it('removeToken clears both token and user', () => {
    setToken('abc123')
    setStoredUser({ name: 'test' })
    removeToken()
    expect(getToken()).toBeNull()
    expect(getStoredUser()).toBeNull()
  })
  it('getStoredUser returns parsed user', () => {
    setStoredUser({ id: 1, name: '李白' })
    expect(getStoredUser()).toEqual({ id: 1, name: '李白' })
  })
  it('getStoredUser returns null on invalid JSON', () => {
    localStorage.setItem('shi-pick-user', 'invalid{')
    expect(getStoredUser()).toBeNull()
  })
})
```

- [ ] **Step 4: 写入 tests/utils/format.test.ts**

```typescript
import { describe, it, expect } from 'vitest'
import { formatDate, truncate } from '@/utils/format'

describe('format utils', () => {
  it('formatDate formats ISO date', () => { expect(formatDate('2024-03-15T10:00:00Z')).toBe('2024-03-15') })
  it('formatDate returns input for invalid', () => { expect(formatDate('not-a-date')).toBe('not-a-date') })
  it('formatDate returns empty for undefined', () => { expect(formatDate(undefined)).toBe('') })
  it('truncate leaves short text unchanged', () => { expect(truncate('hello', 10)).toBe('hello') })
  it('truncate cuts long text with ellipsis', () => { expect(truncate('床前明月光', 5)).toBe('床前明月光...') })
})
```

- [ ] **Step 5: 运行测试**

```powershell
cd E:\javatexts\frontend\shi-pick
npm test
```

Expected: All tests pass.

- [ ] **Step 6: 提交**

```powershell
git add src/utils tests/utils
git commit -m "feat(utils): add auth/format utils with unit tests"
```

---

### Task 2.3: PoemCard 组件

**Files:**
- Create: `src/components/poem/PoemCard.vue`

- [ ] **Step 1: 写入 src/components/poem/PoemCard.vue**

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import type { Poem } from '@/types/poem'

interface Props { poem: Poem; showDynasty?: boolean }
const props = withDefaults(defineProps<Props>(), { showDynasty: true })
const router = useRouter()
const preview = computed(() => props.poem.content[0] || '')
</script>

<template>
  <article class="poem-card" @click="router.push(`/poems/${poem.id}`)">
    <header class="card-header">
      <h3 class="card-title">{{ poem.title }}</h3>
      <span class="card-meta">
        <span v-if="showDynasty" class="dynasty">[{{ poem.dynasty }}]</span>
        {{ poem.author }}
      </span>
    </header>
    <p class="card-preview poem-text">{{ preview }}</p>
    <footer v-if="poem.category" class="card-footer">
      <span class="category">{{ poem.category }}</span>
    </footer>
  </article>
</template>

<style scoped>
.poem-card {
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 24px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.poem-card:hover { border-color: var(--color-primary); transform: translateY(-2px); }
.card-header { margin-bottom: 16px; }
.card-title { font-family: var(--font-serif); font-size: 22px; font-weight: 600; letter-spacing: 4px; color: var(--color-primary); margin: 0 0 6px; }
.card-meta { font-size: 12px; color: var(--color-ink-muted); letter-spacing: 1px; }
.dynasty { margin-right: 4px; }
.card-preview { font-size: 16px; color: var(--color-ink); margin: 0; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.card-footer { margin-top: 16px; padding-top: 12px; border-top: 1px dashed var(--color-divider); }
.category { font-family: var(--font-kai); font-size: 11px; color: var(--color-accent); letter-spacing: 3px; }
</style>
```

- [ ] **Step 2: 提交**

```powershell
git add src/components/poem/PoemCard.vue
git commit -m "feat(poem): add PoemCard component"
```

---

### Task 2.4: 首页 (HomeView) with mock data

**Files:**
- Modify: `src/views/HomeView.vue`

- [ ] **Step 1: 重写 src/views/HomeView.vue**

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import StampSeal from '@/components/common/StampSeal.vue'
import PoemCard from '@/components/poem/PoemCard.vue'
import { mockTodayPoems, mockHotPoems, mockDynasties, mockCategories } from '@/mock-index'

const router = useRouter()
const todayPoems = computed(() => mockTodayPoems)
const hotPoems = computed(() => mockHotPoems)

function goToPoem(id: string) { router.push(`/poems/${id}`) }
function goToDynasty(d: string) { router.push({ name: 'poem-list', query: { dynasty: d } }) }
function goToCategory(c: string) { router.push({ name: 'poem-list', query: { category: c } }) }
</script>

<template>
  <div class="home">
    <section class="hero">
      <StampSeal text="诗" :size="56" />
      <h1 class="hero-title">拾诗</h1>
      <p class="hero-sub">PICK POEM · 桌面端古诗词阅读</p>
      <div class="divider-with-seal"><span>卷 · 一</span></div>
      <p class="hero-desc">在喧嚣的尘世里，为自己拾起一首诗。<br />读诗，是与自己的一次安静对话。</p>
    </section>

    <section v-if="todayPoems.length" class="section">
      <div class="section-title">
        <span class="section-label">TODAY</span>
        <h2>今日一诗</h2>
      </div>
      <div class="today-list">
        <article v-for="poem in todayPoems" :key="poem.id" class="today-poem" @click="goToPoem(poem.id)">
          <h3 class="today-title">{{ poem.title }}</h3>
          <p class="today-meta">[{{ poem.dynasty }}] {{ poem.author }}</p>
          <div class="today-content poem-text">
            <p v-for="(line, i) in poem.content" :key="i">{{ line }}</p>
          </div>
        </article>
      </div>
    </section>

    <section class="section">
      <div class="section-title">
        <span class="section-label">DYNASTY</span>
        <h2>按朝代浏览</h2>
      </div>
      <div class="dynasty-grid">
        <button v-for="d in mockDynasties" :key="d" class="dynasty-btn" @click="goToDynasty(d)">{{ d }}</button>
      </div>
    </section>

    <section class="section">
      <div class="section-title">
        <span class="section-label">CATEGORY</span>
        <h2>按主题</h2>
      </div>
      <div class="category-grid">
        <button v-for="c in mockCategories" :key="c" class="category-btn" @click="goToCategory(c)">{{ c }}</button>
      </div>
    </section>

    <section v-if="hotPoems.length" class="section">
      <div class="section-title">
        <span class="section-label">POPULAR</span>
        <h2>热门作品</h2>
      </div>
      <div class="poem-grid">
        <PoemCard v-for="poem in hotPoems" :key="poem.id" :poem="poem" />
      </div>
    </section>
  </div>
</template>

<style scoped>
.home { padding: 32px 0; }
.hero { text-align: center; padding: 64px 0 80px; }
.hero-title { font-family: var(--font-serif); font-size: 56px; font-weight: 600; letter-spacing: 16px; margin: 24px 0 12px; color: var(--color-primary); }
.hero-sub { font-size: 11px; letter-spacing: 4px; color: var(--color-ink-muted); margin: 0; }
.hero-desc { margin-top: 32px; font-family: var(--font-serif); font-size: 16px; color: var(--color-ink); line-height: 2; letter-spacing: 2px; }
.section { margin: 80px 0; }
.section-title { display: flex; align-items: baseline; gap: 16px; margin-bottom: 32px; }
.section-label { font-size: 10px; letter-spacing: 4px; color: var(--color-accent); }
.section-title h2 { font-family: var(--font-serif); font-size: 28px; letter-spacing: 6px; color: var(--color-primary); margin: 0; font-weight: 600; }
.today-list { display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 32px; }
.today-poem { background: var(--color-bg-secondary); border: 1px solid var(--color-border); border-radius: 6px; padding: 32px; cursor: pointer; transition: all 0.2s; }
.today-poem:hover { border-color: var(--color-primary); }
.today-title { font-family: var(--font-serif); font-size: 26px; font-weight: 600; letter-spacing: 8px; text-align: center; color: var(--color-primary); margin: 0 0 8px; }
.today-meta { text-align: center; font-size: 12px; color: var(--color-ink-muted); letter-spacing: 3px; margin: 0 0 24px; }
.today-content { text-align: center; font-size: 16px; }
.today-content p { margin: 6px 0; }
.dynasty-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 16px; }
.dynasty-btn { padding: 24px; background: var(--color-bg-secondary); border: 1px solid var(--color-border); border-radius: 6px; font-family: var(--font-serif); font-size: 22px; letter-spacing: 8px; color: var(--color-primary); cursor: pointer; transition: all 0.2s; }
.dynasty-btn:hover { border-color: var(--color-accent); color: var(--color-accent); }
.category-grid { display: flex; flex-wrap: wrap; gap: 12px; }
.category-btn { padding: 8px 20px; background: transparent; border: 1px solid var(--color-divider); border-radius: 4px; font-family: var(--font-kai); font-size: 13px; letter-spacing: 3px; color: var(--color-ink); cursor: pointer; transition: all 0.2s; }
.category-btn:hover { border-color: var(--color-accent); color: var(--color-accent); }
.poem-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 24px; }
</style>
```

- [ ] **Step 2: 提交**

```powershell
git add src/views/HomeView.vue
git commit -m "feat(home): build home view with mock data"
```

---

### Task 2.5: 诗库列表 (PoemListView)

**Files:**
- Modify: `src/views/PoemListView.vue`

- [ ] **Step 1: 重写 src/views/PoemListView.vue**

```vue
<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import PoemCard from '@/components/poem/PoemCard.vue'
import StampSeal from '@/components/common/StampSeal.vue'
import { mockPoems, mockDynasties, mockCategories } from '@/mock-index'

const route = useRoute()
const dynastyFilter = ref<string>(route.query.dynasty ? String(route.query.dynasty) : '')
const categoryFilter = ref<string>(route.query.category ? String(route.query.category) : '')
const keywordFilter = ref<string>(route.query.keyword ? String(route.query.keyword) : '')

const filteredPoems = computed(() => mockPoems.filter((p) => {
  if (dynastyFilter.value && p.dynasty !== dynastyFilter.value) return false
  if (categoryFilter.value && p.category !== categoryFilter.value) return false
  if (keywordFilter.value && !p.title.includes(keywordFilter.value) && !p.author.includes(keywordFilter.value)) return false
  return true
}))

function clearFilters() {
  dynastyFilter.value = ''
  categoryFilter.value = ''
  keywordFilter.value = ''
}
</script>

<template>
  <div class="poem-list">
    <header class="page-header">
      <StampSeal text="诗库" :size="40" />
      <h1>诗库</h1>
      <p class="subtitle">POEM LIBRARY · 共 {{ filteredPoems.length }} 首</p>
    </header>
    <div class="filters">
      <div class="filter-group">
        <span class="filter-label">朝代</span>
        <button v-for="d in mockDynasties" :key="d" class="filter-btn" :class="{ active: dynastyFilter === d }" @click="dynastyFilter = dynastyFilter === d ? '' : d">{{ d }}</button>
      </div>
      <div class="filter-group">
        <span class="filter-label">主题</span>
        <button v-for="c in mockCategories" :key="c" class="filter-btn" :class="{ active: categoryFilter === c }" @click="categoryFilter = categoryFilter === c ? '' : c">{{ c }}</button>
      </div>
      <button v-if="dynastyFilter || categoryFilter || keywordFilter" class="clear-btn" @click="clearFilters">清除筛选</button>
    </div>
    <div v-if="filteredPoems.length" class="poem-grid">
      <PoemCard v-for="poem in filteredPoems" :key="poem.id" :poem="poem" />
    </div>
    <div v-else class="empty">
      <p>没有匹配的诗词</p>
      <button @click="clearFilters">清除筛选</button>
    </div>
  </div>
</template>

<style scoped>
.poem-list { padding: 32px 0; }
.page-header { text-align: center; margin-bottom: 48px; }
.page-header h1 { font-family: var(--font-serif); font-size: 40px; letter-spacing: 12px; color: var(--color-primary); margin: 16px 0 8px; }
.subtitle { font-size: 11px; letter-spacing: 4px; color: var(--color-ink-muted); }
.filters { display: flex; flex-wrap: wrap; align-items: center; gap: 24px; padding: 20px 24px; background: var(--color-bg-secondary); border: 1px solid var(--color-border); border-radius: 6px; margin-bottom: 32px; }
.filter-group { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.filter-label { font-size: 12px; color: var(--color-ink-muted); letter-spacing: 2px; margin-right: 4px; }
.filter-btn { padding: 4px 14px; background: transparent; border: 1px solid var(--color-divider); border-radius: 4px; font-size: 13px; color: var(--color-ink); cursor: pointer; transition: all 0.2s; }
.filter-btn:hover { border-color: var(--color-primary); }
.filter-btn.active { background: var(--color-primary); border-color: var(--color-primary); color: white; }
.clear-btn { margin-left: auto; padding: 4px 14px; background: transparent; border: 1px dashed var(--color-divider); border-radius: 4px; font-size: 12px; color: var(--color-ink-muted); cursor: pointer; }
.clear-btn:hover { border-color: var(--color-accent); color: var(--color-accent); }
.poem-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 24px; }
.empty { text-align: center; padding: 80px 0; color: var(--color-ink-muted); }
.empty button { margin-top: 16px; padding: 6px 16px; background: transparent; border: 1px solid var(--color-primary); color: var(--color-primary); border-radius: 4px; cursor: pointer; }
</style>
```

- [ ] **Step 2: 提交**

```powershell
git add src/views/PoemListView.vue
git commit -m "feat(poem-list): build library view with filters"
```

---

### Task 2.6: 诗词详情 (PoemDetailView) + 子组件

**Files:**
- Create: `src/components/poem/PoemContent.vue`
- Create: `src/components/poem/PoemAnnotation.vue`
- Modify: `src/views/PoemDetailView.vue`

- [ ] **Step 1: 写入 src/components/poem/PoemContent.vue**

```vue
<script setup lang="ts">
interface Props { content: string[]; title: string; author: string; dynasty: string }
defineProps<Props>()
</script>

<template>
  <div class="poem-content">
    <h1 class="poem-title">{{ title }}</h1>
    <p class="poem-meta">[{{ dynasty }}] {{ author }}</p>
    <div class="poem-body poem-text">
      <p v-for="(line, i) in content" :key="i" class="poem-line">{{ line }}</p>
    </div>
  </div>
</template>

<style scoped>
.poem-content { text-align: center; padding: 48px 0; }
.poem-title { font-family: var(--font-serif); font-size: 48px; font-weight: 600; letter-spacing: 16px; color: var(--color-primary); margin: 0 0 12px; }
.poem-meta { font-size: 14px; color: var(--color-ink-muted); letter-spacing: 4px; margin: 0 0 48px; }
.poem-body { display: inline-block; text-align: left; }
.poem-line { margin: 12px 0; font-size: 22px; letter-spacing: 8px; text-indent: 2em; }
</style>
```

- [ ] **Step 2: 写入 src/components/poem/PoemAnnotation.vue**

```vue
<script setup lang="ts">
import { NCollapse, NCollapseItem } from 'naive-ui'
interface Props { annotation?: string; translation?: string; appreciation?: string }
defineProps<Props>()
</script>

<template>
  <div class="poem-annotation">
    <h3 class="annotation-title">注释 · 译文 · 赏析</h3>
    <NCollapse :default-expanded-names="['translation']" arrow-placement="right">
      <NCollapseItem v-if="translation" title="译文" name="translation"><p class="annotation-content">{{ translation }}</p></NCollapseItem>
      <NCollapseItem v-if="annotation" title="注释" name="annotation"><p class="annotation-content">{{ annotation }}</p></NCollapseItem>
      <NCollapseItem v-if="appreciation" title="赏析" name="appreciation"><p class="annotation-content">{{ appreciation }}</p></NCollapseItem>
    </NCollapse>
  </div>
</template>

<style scoped>
.poem-annotation { margin: 48px 0; padding: 32px; background: var(--color-bg-secondary); border: 1px solid var(--color-border); border-radius: 6px; }
.annotation-title { font-family: var(--font-serif); font-size: 18px; letter-spacing: 6px; color: var(--color-primary); margin: 0 0 24px; text-align: center; }
.annotation-content { font-size: 15px; line-height: 2; color: var(--color-ink); margin: 0; }
</style>
```

- [ ] **Step 3: 重写 src/views/PoemDetailView.vue**

```vue
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NButton, NIcon, useMessage } from 'naive-ui'
import { HeartOutline, Heart, ArrowBackOutline, PersonOutline } from '@vicons/ionicons5'
import PoemContent from '@/components/poem/PoemContent.vue'
import PoemAnnotation from '@/components/poem/PoemAnnotation.vue'
import StampSeal from '@/components/common/StampSeal.vue'
import { mockPoems, mockAuthors } from '@/mock-index'

const route = useRoute()
const router = useRouter()
const message = useMessage()
const poem = computed(() => mockPoems.find((p) => p.id === route.params.id))
const author = computed(() => mockAuthors.find((a) => a.id === poem.value?.authorId))
const isFavorited = ref(false)

function toggleFavorite() {
  isFavorited.value = !isFavorited.value
  message.success(isFavorited.value ? '已收藏' : '已取消收藏')
}
</script>

<template>
  <div v-if="poem" class="poem-detail">
    <div class="back-nav">
      <NButton text @click="router.back()">
        <template #icon><NIcon :component="ArrowBackOutline" /></template>
        返回
      </NButton>
    </div>
    <PoemContent :title="poem.title" :author="poem.author" :dynasty="poem.dynasty" :content="poem.content" />
    <div class="actions">
      <NButton size="large" :type="isFavorited ? 'primary' : 'default'" @click="toggleFavorite">
        <template #icon><NIcon :component="isFavorited ? Heart : HeartOutline" /></template>
        {{ isFavorited ? '已收藏' : '收藏' }}
      </NButton>
      <NButton v-if="author" text size="large" @click="router.push(`/authors/${author.id}`)">
        <template #icon><NIcon :component="PersonOutline" /></template>
        关于作者
      </NButton>
    </div>
    <div class="divider-with-seal"><span>— 译 · 注 · 赏 —</span></div>
    <PoemAnnotation :annotation="poem.annotation" :translation="poem.translation" :appreciation="poem.appreciation" />
    <footer v-if="author" class="author-card">
      <StampSeal :text="author.name.charAt(0)" :size="40" />
      <div class="author-info">
        <h4>{{ author.name }}</h4>
        <p class="author-dynasty">[{{ author.dynasty }}]</p>
        <p class="author-bio">{{ author.bio }}</p>
        <NButton text type="primary" @click="router.push(`/authors/${author.id}`)">查看作品 →</NButton>
      </div>
    </footer>
  </div>
  <div v-else class="not-found">
    <StampSeal text="404" :size="48" />
    <p>未找到这首诗</p>
    <NButton @click="router.push('/poems')">返回诗库</NButton>
  </div>
</template>

<style scoped>
.poem-detail { max-width: 720px; margin: 0 auto; padding: 16px 0 64px; }
.back-nav { margin-bottom: 24px; }
.actions { display: flex; justify-content: center; gap: 16px; margin: 32px 0; }
.author-card { display: flex; gap: 24px; padding: 32px; background: var(--color-bg-secondary); border: 1px solid var(--color-border); border-radius: 6px; margin-top: 48px; }
.author-info h4 { font-family: var(--font-serif); font-size: 24px; letter-spacing: 6px; color: var(--color-primary); margin: 0 0 4px; }
.author-dynasty { font-size: 12px; color: var(--color-ink-muted); margin: 0 0 12px; }
.author-bio { font-size: 14px; line-height: 1.7; color: var(--color-ink); margin: 0 0 12px; }
.not-found { text-align: center; padding: 80px 0; }
</style>
```

- [ ] **Step 4: 提交**

```powershell
git add src/components/poem/ src/views/PoemDetailView.vue
git commit -m "feat(poem-detail): build detail view with content/annotation/author"
```

---

### Task 2.7: 作者详情 (AuthorView)

**Files:**
- Modify: `src/views/AuthorView.vue`

- [ ] **Step 1: 重写 src/views/AuthorView.vue**

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NButton, NIcon } from 'naive-ui'
import { ArrowBackOutline } from '@vicons/ionicons5'
import StampSeal from '@/components/common/StampSeal.vue'
import PoemCard from '@/components/poem/PoemCard.vue'
import { mockAuthors, mockPoems } from '@/mock-index'

const route = useRoute()
const router = useRouter()
const author = computed(() => mockAuthors.find((a) => a.id === route.params.id))
const poems = computed(() => mockPoems.filter((p) => p.authorId === route.params.id))
</script>

<template>
  <div v-if="author" class="author-view">
    <div class="back-nav">
      <NButton text @click="router.back()">
        <template #icon><NIcon :component="ArrowBackOutline" /></template>
        返回
      </NButton>
    </div>
    <header class="author-header">
      <StampSeal :text="author.name.charAt(0)" :size="80" />
      <h1 class="author-name">{{ author.name }}</h1>
      <p class="author-dynasty">[{{ author.dynasty }}] · {{ author.poemCount }} 首作品</p>
      <div class="divider-with-seal"><span>— 生平 —</span></div>
      <p class="author-bio">{{ author.bio }}</p>
    </header>
    <section class="poems-section">
      <h2 class="section-title">代表作品</h2>
      <div class="poem-grid">
        <PoemCard v-for="poem in poems" :key="poem.id" :poem="poem" />
      </div>
    </section>
  </div>
  <div v-else class="not-found">
    <StampSeal text="404" :size="48" />
    <p>未找到该作者</p>
    <NButton @click="router.push('/')">返回首页</NButton>
  </div>
</template>

<style scoped>
.author-view { padding: 16px 0 64px; }
.author-header { text-align: center; padding: 32px 0 48px; }
.author-name { font-family: var(--font-serif); font-size: 56px; font-weight: 600; letter-spacing: 24px; color: var(--color-primary); margin: 24px 0 8px; }
.author-dynasty { font-size: 12px; letter-spacing: 3px; color: var(--color-ink-muted); margin: 0 0 32px; }
.author-bio { max-width: 640px; margin: 0 auto; font-size: 15px; line-height: 2; color: var(--color-ink); text-align: left; }
.poems-section { margin-top: 64px; }
.section-title { font-family: var(--font-serif); font-size: 28px; letter-spacing: 8px; color: var(--color-primary); text-align: center; margin: 0 0 32px; }
.poem-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 24px; }
.not-found { text-align: center; padding: 80px 0; }
</style>
```

- [ ] **Step 2: 提交 + Phase 2 检查点**

```powershell
git add src/views/AuthorView.vue
git commit -m "feat(author): build author view"
```

启动 dev server 验证后，问用户："Phase 2 完成。UI 感觉对路吗？对就回 OK，我做 Phase 3 接后端。"

---

## Phase 3: 对接后端 API (~2 days)

**Checkpoint**: All views read from real backend API.

### Task 3.1: Axios 实例 + 拦截器

**Files:**
- Create: `src/api/request.ts`

- [ ] **Step 1: 写入 src/api/request.ts**

```typescript
import axios, { type AxiosInstance, type InternalAxiosRequestConfig } from 'axios'
import type { ApiResult } from '@/types/api'
import { getToken, removeToken } from '@/utils/auth'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080'

export const request: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' }
})

request.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getToken()
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

request.interceptors.response.use(
  (response) => {
    const body = response.data as ApiResult<unknown>
    if (body && typeof body === 'object' && 'code' in body) {
      if (body.code === 0) return body.data as never
      if (body.code === 401) {
        removeToken()
        window.location.href = '/login'
        return Promise.reject(new Error('Unauthorized'))
      }
      return Promise.reject(new Error(body.msg || 'Request failed'))
    }
    return response.data as never
  },
  (error) => Promise.reject(new Error(error?.response?.data?.msg || error.message || 'Network error'))
)

export default request
```

- [ ] **Step 2: 提交**

```powershell
git add src/api/request.ts
git commit -m "feat(api): add axios instance with interceptors"
```

---

### Task 3.2: poem / author API 模块 + .env

**Files:**
- Create: `src/api/poem.ts`, `src/api/author.ts`, `.env.development`

- [ ] **Step 1: 写入 .env.development**

```
VITE_API_BASE_URL=http://localhost:8080
```

- [ ] **Step 2: 写入 src/api/poem.ts**

```typescript
import request from './request'
import type { Poem } from '@/types/poem'
import type { PageQuery, PageResult } from '@/types/api'

export const poemApi = {
  getToday(): Promise<Poem[]> { return request.get('/potry/today') },
  getHot(): Promise<Poem[]> { return request.get('/potry/hot') },
  getList(query: PageQuery): Promise<PageResult<Poem>> { return request.get('/potry/list', { params: query }) },
  getDetail(id: string): Promise<Poem> { return request.get(`/potry/${id}`) },
  getDynasties(): Promise<string[]> { return request.get('/potry/dynasties') },
  getCategories(): Promise<string[]> { return request.get('/potry/categories') }
}
```

- [ ] **Step 3: 写入 src/api/author.ts**

```typescript
import request from './request'
import type { Author } from '@/types/author'
import type { Poem } from '@/types/poem'

export const authorApi = {
  getDetail(id: string): Promise<Author> { return request.get(`/writer/${id}`) },
  getPoems(id: string): Promise<Poem[]> { return request.get(`/writer/${id}/poems`) }
}
```

- [ ] **Step 4: 提交**

```powershell
git add src/api/ .env.development
git commit -m "feat(api): add poem/author API modules"
```

---

### Task 3.3: 验证并对齐后端 API 路径

- [ ] **Step 1: 启动后端**

```powershell
cd E:\javatexts\poetry-spring2
mvn spring-boot:run -pl potry-service
```

- [ ] **Step 2: 探测实际接口路径**

打开浏览器或用 curl 测试 `http://localhost:8080/potry/today`、`http://localhost:8080/api/potry/today` 等。

打开后端 controller 文件确认每个接口的 `@RequestMapping` 路径（位置：`potry-service/src/main/java/com/fuze/potryservice/controller/`）。

- [ ] **Step 3: 把确认后的路径写入 src/api/paths.ts**

```typescript
// 与后端 controller 对齐后的实际路径
export const PATHS = {
  today: '/potry/today',
  hot: '/potry/hot',
  list: '/potry/list',
  detail: (id: string) => `/potry/${id}`,
  dynasties: '/potry/dynasties',
  categories: '/potry/categories',
  author: (id: string) => `/writer/${id}`,
  authorPoems: (id: string) => `/writer/${id}/poems`
}
```

- [ ] **Step 4: 如果路径不同，修改 src/api/poem.ts 和 src/api/author.ts**

- [ ] **Step 5: 提交**

```powershell
git add src/api/
git commit -m "feat(api): align API paths with backend"
```

---

### Task 3.4: 把各 View 切到真实 API

**Files:** Modify `src/views/HomeView.vue`, `PoemListView.vue`, `PoemDetailView.vue`, `AuthorView.vue`.

- [ ] **Step 1: 修改 src/views/HomeView.vue 使用 poemApi**

Replace the script section with:

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import StampSeal from '@/components/common/StampSeal.vue'
import PoemCard from '@/components/poem/PoemCard.vue'
import { poemApi } from '@/api/poem'
import type { Poem } from '@/types/poem'

const router = useRouter()
const todayPoems = ref<Poem[]>([])
const hotPoems = ref<Poem[]>([])
const dynasties = ref<string[]>([])
const categories = ref<string[]>([])

onMounted(async () => {
  const [t, h, d, c] = await Promise.all([
    poemApi.getToday().catch(() => []),
    poemApi.getHot().catch(() => []),
    poemApi.getDynasties().catch(() => ['唐', '宋', '元', '明', '清']),
    poemApi.getCategories().catch(() => ['山水', '思乡', '送别'])
  ])
  todayPoems.value = t
  hotPoems.value = h
  dynasties.value = d
  categories.value = c
})

function goToPoem(id: string) { router.push(`/poems/${id}`) }
function goToDynasty(d: string) { router.push({ name: 'poem-list', query: { dynasty: d } }) }
function goToCategory(c: string) { router.push({ name: 'poem-list', query: { category: c } }) }
</script>

<!-- Template unchanged from Task 2.4 -->
```

- [ ] **Step 2: 修改 src/views/PoemListView.vue 使用 poemApi.getList**

```vue
<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import PoemCard from '@/components/poem/PoemCard.vue'
import StampSeal from '@/components/common/StampSeal.vue'
import { poemApi } from '@/api/poem'
import type { Poem } from '@/types/poem'

const route = useRoute()
const dynastyFilter = ref<string>(route.query.dynasty ? String(route.query.dynasty) : '')
const categoryFilter = ref<string>(route.query.category ? String(route.query.category) : '')
const keywordFilter = ref<string>(route.query.keyword ? String(route.query.keyword) : '')
const poems = ref<Poem[]>([])
const dynasties = ref<string[]>([])
const categories = ref<string[]>([])

async function loadPoems() {
  const result = await poemApi.getList({
    page: 1,
    size: 100,
    dynasty: dynastyFilter.value || undefined,
    category: categoryFilter.value || undefined,
    keyword: keywordFilter.value || undefined
  }).catch(() => ({ total: 0, list: [], page: 1, size: 0 }))
  poems.value = result.list
}

onMounted(async () => {
  await loadPoems()
  dynasties.value = await poemApi.getDynasties().catch(() => ['唐', '宋'])
  categories.value = await poemApi.getCategories().catch(() => ['山水', '思乡'])
})

watch([dynastyFilter, categoryFilter, keywordFilter], loadPoems)

function clearFilters() {
  dynastyFilter.value = ''
  categoryFilter.value = ''
  keywordFilter.value = ''
}
</script>

<!-- Template uses `poems` instead of `filteredPoems` -->
```

- [ ] **Step 3: 修改 src/views/PoemDetailView.vue 使用 poemApi.getDetail**

```vue
<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NButton, NIcon, useMessage } from 'naive-ui'
import { HeartOutline, Heart, ArrowBackOutline, PersonOutline } from '@vicons/ionicons5'
import PoemContent from '@/components/poem/PoemContent.vue'
import PoemAnnotation from '@/components/poem/PoemAnnotation.vue'
import StampSeal from '@/components/common/StampSeal.vue'
import { poemApi } from '@/api/poem'
import { authorApi } from '@/api/author'
import type { Poem } from '@/types/poem'
import type { Author } from '@/types/author'

const route = useRoute()
const router = useRouter()
const message = useMessage()
const poem = ref<Poem | null>(null)
const author = ref<Author | null>(null)
const isFavorited = ref(false)

async function load() {
  const id = String(route.params.id)
  try {
    poem.value = await poemApi.getDetail(id)
    if (poem.value?.authorId) {
      author.value = await authorApi.getDetail(poem.value.authorId).catch(() => null)
    }
  } catch {
    poem.value = null
  }
}

onMounted(load)
watch(() => route.params.id, load)

function toggleFavorite() {
  isFavorited.value = !isFavorited.value
  message.success(isFavorited.value ? '已收藏' : '已取消收藏')
}
</script>

<!-- Template unchanged -->
```

- [ ] **Step 4: 修改 src/views/AuthorView.vue 使用 authorApi**

```vue
<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NButton, NIcon } from 'naive-ui'
import { ArrowBackOutline } from '@vicons/ionicons5'
import StampSeal from '@/components/common/StampSeal.vue'
import PoemCard from '@/components/poem/PoemCard.vue'
import { authorApi } from '@/api/author'
import type { Author } from '@/types/author'
import type { Poem } from '@/types/poem'

const route = useRoute()
const router = useRouter()
const author = ref<Author | null>(null)
const poems = ref<Poem[]>([])

async function load() {
  const id = String(route.params.id)
  try {
    author.value = await authorApi.getDetail(id)
    poems.value = await authorApi.getPoems(id).catch(() => [])
  } catch {
    author.value = null
  }
}

onMounted(load)
watch(() => route.params.id, load)
</script>

<!-- Template unchanged -->
```

- [ ] **Step 5: 端到端验证**

启动后端 + 前端，访问所有页面，确认数据来自后端。

- [ ] **Step 6: 提交**

```powershell
git add src/views/
git commit -m "feat(views): switch to real backend API"
```

- [ ] **Step 7: Phase 3 检查点**

Ask user: "Phase 3 完成。接得对吗？没问题回 OK，我做 Phase 4。"

---

## Phase 4: 登录 + 收藏 (~3 days)

**Checkpoint**: User can log in (email + username/password), favorite poems, see favorites list.

### Task 4.1: user API + Pinia stores (replace stubs)

**Files:**
- Create: `src/api/user.ts`
- Modify: `src/stores/user.ts` (replace stub)
- Modify: `src/stores/favorites.ts` (replace stub)
- Create: `tests/stores/user.test.ts`, `tests/stores/favorites.test.ts`

- [ ] **Step 1: 写入 src/api/user.ts**

```typescript
import request from './request'
import type { User } from '@/types/user'

export const userApi = {
  loginByAccount(username: string, password: string): Promise<User> {
    return request.post('/user/login', { username, password })
  },
  loginByEmail(email: string, code: string): Promise<User> {
    return request.post('/user/login/email', { email, code })
  },
  sendCode(email: string): Promise<void> {
    return request.post('/user/code', { email })
  },
  getMe(): Promise<User> {
    return request.get('/user/me')
  },
  getFavorites(): Promise<string[]> {
    return request.get('/user/favorites')
  },
  toggleFavorite(poemId: string): Promise<{ favorited: boolean }> {
    return request.post(`/user/favorites/${poemId}`)
  },
  logout(): Promise<void> {
    return request.post('/user/logout')
  }
}
```

- [ ] **Step 2: 重写 src/stores/user.ts**

```typescript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { User } from '@/types/user'
import { userApi } from '@/api/user'
import { setToken, removeToken, setStoredUser, getStoredUser } from '@/utils/auth'

export const useUserStore = defineStore('user', () => {
  const user = ref<User | null>(getStoredUser<User>())
  const loading = ref(false)
  const isLoggedIn = computed(() => !!user.value?.token)

  async function loginByAccount(username: string, password: string) {
    loading.value = true
    try {
      const u = await userApi.loginByAccount(username, password)
      setToken(u.token)
      setStoredUser(u)
      user.value = u
      return u
    } finally { loading.value = false }
  }

  async function loginByEmail(email: string, code: string) {
    loading.value = true
    try {
      const u = await userApi.loginByEmail(email, code)
      setToken(u.token)
      setStoredUser(u)
      user.value = u
      return u
    } finally { loading.value = false }
  }

  async function sendCode(email: string) {
    return userApi.sendCode(email)
  }

  function logout() {
    removeToken()
    user.value = null
  }

  return { user, loading, isLoggedIn, loginByAccount, loginByEmail, sendCode, logout }
})
```

- [ ] **Step 3: 重写 src/stores/favorites.ts**

```typescript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { userApi } from '@/api/user'

export const useFavoritesStore = defineStore('favorites', () => {
  const ids = ref<Set<string>>(new Set())
  const loading = ref(false)
  const count = computed(() => ids.value.size)

  function isFavorited(poemId: string): boolean {
    return ids.value.has(poemId)
  }

  async function load() {
    loading.value = true
    try {
      ids.value = new Set(await userApi.getFavorites())
    } finally { loading.value = false }
  }

  async function toggle(poemId: string): Promise<boolean> {
    const result = await userApi.toggleFavorite(poemId)
    if (result.favorited) ids.value.add(poemId)
    else ids.value.delete(poemId)
    return result.favorited
  }

  function clear() {
    ids.value = new Set()
  }

  return { ids, loading, count, isFavorited, load, toggle, clear }
})
```

- [ ] **Step 4: 写入 tests/stores/user.test.ts**

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useUserStore } from '@/stores/user'

vi.mock('@/api/user', () => ({
  userApi: {
    loginByAccount: vi.fn(async (username) => ({ id: 1, username, email: `${username}@x.com`, nickname: 'test', token: 'mock-token' })),
    loginByEmail: vi.fn(async () => ({ id: 1, email: 'a@b.c', nickname: 'a', token: 'mock' })),
    sendCode: vi.fn(async () => undefined)
  }
}))

describe('user store', () => {
  beforeEach(() => { setActivePinia(createPinia()); localStorage.clear() })

  it('initial state: not logged in', () => {
    const s = useUserStore()
    expect(s.isLoggedIn).toBe(false)
  })

  it('loginByAccount sets user and token', async () => {
    const s = useUserStore()
    await s.loginByAccount('alice', 'pwd')
    expect(s.isLoggedIn).toBe(true)
    expect(s.user?.username).toBe('alice')
    expect(localStorage.getItem('shi-pick-token')).toBe('mock-token')
  })

  it('logout clears user', async () => {
    const s = useUserStore()
    await s.loginByAccount('alice', 'pwd')
    s.logout()
    expect(s.isLoggedIn).toBe(false)
    expect(localStorage.getItem('shi-pick-token')).toBeNull()
  })
})
```

- [ ] **Step 5: 写入 tests/stores/favorites.test.ts**

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useFavoritesStore } from '@/stores/favorites'

vi.mock('@/api/user', () => ({
  userApi: {
    getFavorites: vi.fn(async () => ['1', '2', '3']),
    toggleFavorite: vi.fn(async (id) => ({ favorited: !id.startsWith('r') }))
  }
}))

describe('favorites store', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('initial state: empty', () => { const s = useFavoritesStore(); expect(s.count).toBe(0) })

  it('load populates ids', async () => {
    const s = useFavoritesStore()
    await s.load()
    expect(s.count).toBe(3)
    expect(s.isFavorited('1')).toBe(true)
  })

  it('toggle adds on success', async () => {
    const s = useFavoritesStore()
    const added = await s.toggle('5')
    expect(added).toBe(true)
    expect(s.isFavorited('5')).toBe(true)
  })

  it('clear empties ids', async () => {
    const s = useFavoritesStore()
    await s.load()
    s.clear()
    expect(s.count).toBe(0)
  })
})
```

- [ ] **Step 6: 运行测试**

```powershell
cd E:\javatexts\frontend\shi-pick
npm test
```

Expected: All pass.

- [ ] **Step 7: 提交**

```powershell
git add src/api/user.ts src/stores/ tests/stores/
git commit -m "feat(auth): add user/favorites stores + API + tests"
```

---

### Task 4.2: 登录页 (LoginView)

**Files:**
- Modify: `src/views/LoginView.vue`

- [ ] **Step 1: 重写 src/views/LoginView.vue**

```vue
<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { NCard, NInput, NButton, NTabs, NTabPane, NIcon, useMessage } from 'naive-ui'
import { MailOutline, LockClosedOutline, KeyOutline } from '@vicons/ionicons5'
import StampSeal from '@/components/common/StampSeal.vue'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const message = useMessage()
const userStore = useUserStore()

const username = ref('')
const password = ref('')
const email = ref('')
const code = ref('')
const countdown = ref(0)
let timer: ReturnType<typeof setInterval> | null = null

const canSendCode = computed(() => /\S+@\S+\.\S+/.test(email.value) && countdown.value === 0)
const loading = computed(() => userStore.loading)

async function handleAccountLogin() {
  if (!username.value || !password.value) {
    message.warning('请输入账号和密码')
    return
  }
  try {
    await userStore.loginByAccount(username.value, password.value)
    message.success('登录成功')
    router.push((route.query.redirect as string) || '/')
  } catch (e: any) {
    message.error(e?.message || '登录失败')
  }
}

async function handleEmailLogin() {
  if (!email.value || !code.value) {
    message.warning('请输入邮箱和验证码')
    return
  }
  try {
    await userStore.loginByEmail(email.value, code.value)
    message.success('登录成功')
    router.push((route.query.redirect as string) || '/')
  } catch (e: any) {
    message.error(e?.message || '登录失败')
  }
}

async function handleSendCode() {
  if (!canSendCode.value) return
  try {
    await userStore.sendCode(email.value)
    message.success('验证码已发送')
    countdown.value = 60
    timer = setInterval(() => {
      countdown.value--
      if (countdown.value <= 0 && timer) {
        clearInterval(timer)
        timer = null
      }
    }, 1000)
  } catch (e: any) {
    message.error(e?.message || '发送失败')
  }
}
</script>

<template>
  <div class="login-page">
    <NCard class="login-card" :bordered="false">
      <div class="card-header">
        <StampSeal text="登录" :size="56" />
        <h1>拾诗</h1>
        <p class="subtitle">PICK POEM · 登录以收藏诗词</p>
      </div>
      <NTabs default-value="account" type="line" animated>
        <NTabPane name="account" tab="账号密码">
          <div class="form">
            <NInput v-model:value="username" placeholder="账号" size="large" clearable>
              <template #prefix><NIcon :component="LockClosedOutline" /></template>
            </NInput>
            <NInput v-model:value="password" type="password" placeholder="密码" size="large" show-password-on="click" @keyup.enter="handleAccountLogin">
              <template #prefix><NIcon :component="KeyOutline" /></template>
            </NInput>
            <NButton type="primary" size="large" block :loading="loading" @click="handleAccountLogin">
              登 录
            </NButton>
          </div>
        </NTabPane>
        <NTabPane name="email" tab="邮箱验证码">
          <div class="form">
            <NInput v-model:value="email" placeholder="邮箱" size="large" clearable>
              <template #prefix><NIcon :component="MailOutline" /></template>
            </NInput>
            <div class="code-row">
              <NInput v-model:value="code" placeholder="6 位验证码" size="large" maxlength="6" @keyup.enter="handleEmailLogin" />
              <NButton size="large" :disabled="!canSendCode" @click="handleSendCode">
                {{ countdown > 0 ? `${countdown}s 后重发` : '发送验证码' }}
              </NButton>
            </div>
            <NButton type="primary" size="large" block :loading="loading" @click="handleEmailLogin">
              登 录
            </NButton>
          </div>
        </NTabPane>
      </NTabs>
    </NCard>
  </div>
</template>

<style scoped>
.login-page { display: flex; align-items: center; justify-content: center; min-height: calc(100vh - 200px); padding: 24px; }
.login-card { width: 100%; max-width: 440px; background: var(--color-bg-secondary); border: 1px solid var(--color-border); border-radius: 8px; }
.card-header { text-align: center; padding: 16px 0 24px; }
.card-header h1 { font-family: var(--font-serif); font-size: 32px; letter-spacing: 12px; color: var(--color-primary); margin: 16px 0 4px; }
.subtitle { font-size: 11px; letter-spacing: 3px; color: var(--color-ink-muted); }
.form { display: flex; flex-direction: column; gap: 16px; padding: 16px 0; }
.code-row { display: flex; gap: 12px; }
.code-row :deep(.n-input) { flex: 1; }
</style>
```

- [ ] **Step 2: 提交**

```powershell
git add src/views/LoginView.vue
git commit -m "feat(login): build login view with account/email tabs"
```

---

### Task 4.3: 我的页 (MeView) + 收藏页 (FavoritesView)

**Files:**
- Modify: `src/views/MeView.vue`, `src/views/FavoritesView.vue`

- [ ] **Step 1: 重写 src/views/MeView.vue**

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NCard, useMessage } from 'naive-ui'
import StampSeal from '@/components/common/StampSeal.vue'
import { useUserStore } from '@/stores/user'
import { useFavoritesStore } from '@/stores/favorites'

const router = useRouter()
const message = useMessage()
const userStore = useUserStore()
const favStore = useFavoritesStore()

const user = computed(() => userStore.user)
const isLoggedIn = computed(() => userStore.isLoggedIn)
const favCount = computed(() => favStore.count)

function handleLogout() {
  userStore.logout()
  favStore.clear()
  message.success('已退出')
  router.push('/')
}
</script>

<template>
  <div class="me-view">
    <NCard v-if="isLoggedIn && user" class="profile-card">
      <div class="profile-header">
        <StampSeal :text="(user.nickname || user.username).charAt(0)" :size="72" />
        <div class="profile-info">
          <h2>{{ user.nickname || user.username }}</h2>
          <p class="profile-email">{{ user.email }}</p>
          <p class="profile-username">@{{ user.username }}</p>
        </div>
      </div>
      <div class="stats">
        <div class="stat" @click="router.push('/favorites')">
          <div class="stat-num">{{ favCount }}</div>
          <div class="stat-label">收藏</div>
        </div>
      </div>
      <div class="actions">
        <NButton block @click="router.push('/favorites')">查看我的收藏</NButton>
        <NButton block type="error" ghost @click="handleLogout">退出登录</NButton>
      </div>
    </NCard>
    <div v-else class="not-logged">
      <StampSeal text="未登录" :size="64" />
      <h2>尚未登录</h2>
      <p>登录后可收藏诗词、查看收藏列表</p>
      <NButton type="primary" size="large" @click="router.push('/login')">前往登录</NButton>
    </div>
  </div>
</template>

<style scoped>
.me-view { max-width: 640px; margin: 0 auto; padding: 32px 0; }
.profile-card { background: var(--color-bg-secondary); border: 1px solid var(--color-border); }
.profile-header { display: flex; gap: 24px; align-items: center; padding-bottom: 24px; border-bottom: 1px solid var(--color-divider); }
.profile-info h2 { font-family: var(--font-serif); font-size: 28px; letter-spacing: 6px; color: var(--color-primary); margin: 0 0 4px; }
.profile-email, .profile-username { font-size: 13px; color: var(--color-ink-muted); margin: 4px 0; }
.stats { display: flex; justify-content: center; padding: 32px 0; }
.stat { text-align: center; cursor: pointer; padding: 12px 32px; border-radius: 6px; transition: background 0.2s; }
.stat:hover { background: var(--color-bg-primary); }
.stat-num { font-family: var(--font-serif); font-size: 36px; color: var(--color-primary); }
.stat-label { font-size: 12px; color: var(--color-ink-muted); letter-spacing: 2px; margin-top: 4px; }
.actions { display: flex; flex-direction: column; gap: 12px; padding-top: 24px; border-top: 1px solid var(--color-divider); }
.not-logged { text-align: center; padding: 80px 0; }
.not-logged h2 { font-family: var(--font-serif); font-size: 24px; letter-spacing: 6px; color: var(--color-primary); margin: 16px 0 8px; }
.not-logged p { color: var(--color-ink-muted); margin: 0 0 24px; }
</style>
```

- [ ] **Step 2: 重写 src/views/FavoritesView.vue**

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NButton } from 'naive-ui'
import StampSeal from '@/components/common/StampSeal.vue'
import PoemCard from '@/components/poem/PoemCard.vue'
import { useFavoritesStore } from '@/stores/favorites'
import { poemApi } from '@/api/poem'
import type { Poem } from '@/types/poem'

const favStore = useFavoritesStore()
const poems = ref<Poem[]>([])
const loading = ref(true)

onMounted(async () => {
  await favStore.load()
  const list: Poem[] = []
  for (const id of favStore.ids) {
    try { list.push(await poemApi.getDetail(id)) } catch { /* skip */ }
  }
  poems.value = list
  loading.value = false
})
</script>

<template>
  <div class="favorites-view">
    <header class="page-header">
      <StampSeal text="收藏" :size="40" />
      <h1>我的收藏</h1>
      <p class="subtitle">MY FAVORITES · 共 {{ poems.length }} 首</p>
    </header>
    <div v-if="loading" class="loading">载入中...</div>
    <div v-else-if="poems.length" class="poem-grid">
      <PoemCard v-for="poem in poems" :key="poem.id" :poem="poem" />
    </div>
    <div v-else class="empty">
      <StampSeal text="空" :size="64" />
      <p>还没有收藏任何诗词</p>
      <NButton @click="$router.push('/poems')">去诗库看看</NButton>
    </div>
  </div>
</template>

<style scoped>
.favorites-view { padding: 32px 0; }
.page-header { text-align: center; margin-bottom: 48px; }
.page-header h1 { font-family: var(--font-serif); font-size: 40px; letter-spacing: 12px; color: var(--color-primary); margin: 16px 0 8px; }
.subtitle { font-size: 11px; letter-spacing: 4px; color: var(--color-ink-muted); }
.poem-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 24px; }
.loading, .empty { text-align: center; padding: 80px 0; }
.empty p { margin: 16px 0 24px; color: var(--color-ink-muted); }
</style>
```

- [ ] **Step 3: 提交**

```powershell
git add src/views/MeView.vue src/views/FavoritesView.vue
git commit -m "feat(views): build MeView + FavoritesView"
```

---

### Task 4.4: 详情页接入收藏 store + 端到端验证

**Files:**
- Modify: `src/views/PoemDetailView.vue`

- [ ] **Step 1: 修改 src/views/PoemDetailView.vue 用 favorites store**

```vue
<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NButton, NIcon, useMessage } from 'naive-ui'
import { HeartOutline, Heart, ArrowBackOutline, PersonOutline } from '@vicons/ionicons5'
import PoemContent from '@/components/poem/PoemContent.vue'
import PoemAnnotation from '@/components/poem/PoemAnnotation.vue'
import StampSeal from '@/components/common/StampSeal.vue'
import { poemApi } from '@/api/poem'
import { authorApi } from '@/api/author'
import { useFavoritesStore } from '@/stores/favorites'
import { useUserStore } from '@/stores/user'
import type { Poem } from '@/types/poem'
import type { Author } from '@/types/author'

const route = useRoute()
const router = useRouter()
const message = useMessage()
const favStore = useFavoritesStore()
const userStore = useUserStore()
const poem = ref<Poem | null>(null)
const author = ref<Author | null>(null)

const isFavorited = computed(() => (poem.value ? favStore.isFavorited(String(poem.value.id)) : false))

async function load() {
  const id = String(route.params.id)
  try {
    poem.value = await poemApi.getDetail(id)
    if (poem.value?.authorId) {
      author.value = await authorApi.getDetail(poem.value.authorId).catch(() => null)
    }
  } catch {
    poem.value = null
  }
}

onMounted(load)
watch(() => route.params.id, load)

async function toggleFavorite() {
  if (!userStore.isLoggedIn) {
    message.warning('请先登录')
    router.push({ name: 'login', query: { redirect: route.fullPath } })
    return
  }
  if (!poem.value) return
  const favorited = await favStore.toggle(String(poem.value.id))
  message.success(favorited ? '已收藏' : '已取消收藏')
}
</script>

<!-- Template unchanged from Task 2.6 -->
```

- [ ] **Step 2: 端到端验证**

启动后端 + 前端：
1. 访问 `/poems/1`，未登录点收藏 → 应跳登录
2. 邮箱登录（如后端 mock 验证码 123456）→ 跳回详情
3. 点收藏 → 出现"已收藏"
4. 进 `/favorites` → 看到收藏的诗
5. 进 `/me` → 显示昵称和收藏数
6. 退出登录 → 收藏清空

- [ ] **Step 3: 提交**

```powershell
git add src/views/PoemDetailView.vue
git commit -m "feat(auth): wire favorites store into detail view"
```

- [ ] **Step 4: Phase 4 完成**

Ask user: "MVP 跑通了！要不要我帮你做 README？或者直接收工？"

---

## Phase 5（可选）: README + 启动脚本

### Task 5.1: README + start.bat

**Files:**
- Create: `README.md`, `scripts/start.bat`

- [ ] **Step 1: 写入 README.md**

````markdown
# 拾诗 (Pick Poem)

桌面端优先的古诗词学习 Web 应用。MVP 聚焦"读诗"核心体验。

## 技术栈

Vue 3 + TypeScript + Vite + Naive UI + Pinia + Vue Router + Axios

## 启动

```bash
# 1. 启动后端（E:\javatexts\poetry-spring2\potry-service）
mvn spring-boot:run -pl potry-service

# 2. 启动前端
cd E:\javatexts\frontend\shi-pick
npm install
npm run dev
```

访问 http://localhost:5173

## 环境变量

`.env.development`:
```
VITE_API_BASE_URL=http://localhost:8080
```

## 测试 / 构建

```bash
npm test
npm run build
```
````

- [ ] **Step 2: 写入 scripts/start.bat**

```batch
@echo off
echo Starting shi-pick dev server...
cd /d %~dp0..
npm install
npm run dev
```

- [ ] **Step 3: 提交**

```powershell
git add README.md scripts/
git commit -m "docs: add README and start script"
```

---

## 最终验证清单

After all phases, verify:

- [ ] `npm install` no errors
- [ ] `npm test` all tests pass
- [ ] `npm run dev` starts on :5173
- [ ] Backend running, frontend pulls real data
- [ ] All 4 phases work end-to-end
- [ ] Login (email + account) works
- [ ] Favorites work
- [ ] No console errors
- [ ] Desktop (1280px+) looks best

---

## 风格自检

- [ ] Main color stone blue `#2d4a52`, accent sunset `#d97757`
- [ ] Poetry uses serif (Source Han Serif), UI uses sans
- [ ] Border radius 4-6px, no shadows
- [ ] Lots of whitespace, restrained decoration
- [ ] Logo seal style consistent

---

## V2+ 扩展位置

Reserved extension points:
- AI writing: new view `src/views/AIWriteView.vue`
- Ebbinghaus: new store `src/stores/memory.ts`
- Forum: new API `src/api/forum.ts`
- Dark mode: new theme `src/styles/theme-dark.ts`
