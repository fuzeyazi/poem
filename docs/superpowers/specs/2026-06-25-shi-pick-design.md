# 拾诗 (Pick Poem) — 设计文档

> **状态**：草案 v1（待用户最终审核）
> **日期**：2026-06-25
> **范围**：MVP 学习极简版

---

## 1. 项目概述

**名称**：拾诗 (Pick Poem)

**一句话定位**：桌面端优先的古诗词学习 Web 应用，MVP 聚焦"读诗"核心体验。

**差异化卖点**：
- 宋韵长卷美学：留白、克制、有书卷气
- 石青黛影配色：宋代山水/汝窑的经典调子
- 阅读体验即审美体验：读诗本身成为享受

**非目标（明确不做）**：
- 不是文学研究工具（不需要注释考证、学术引用）
- 不是社区平台（无评论、无关注、无动态流，V3 再说）
- 不是电商（不卖书、不卖课）

---

## 2. 目标用户与场景

**用户画像**：对古诗词感兴趣、注重审美体验的成年人。

**典型场景**：
- 工作日晚饭后，桌面浏览器打开"拾诗"
- 沉浸读几首诗，看注释译文
- 收藏喜欢的，准备睡前再翻

**设备优先级**：桌面浏览器 > 平板 > 手机。

**为什么桌面优先**：用户希望读诗时能"被空间包裹"，手机屏幕太小撑不起"长卷感"。

---

## 3. MVP 范围

### 3.1 必须做（MVP 必交付）

- 诗词浏览（按朝代/作者/分类筛选 + 列表）
- 诗词详情（原文 + 注释 + 译文 + 赏析）
- 登录（邮箱验证码 + 账号密码，双 tab）
- 收藏（收藏 / 取消 / 查看收藏列表）
- 顶部导航 + 全局视觉系统

### 3.2 不做（明确排除）

- ❌ AI 写诗 / 续写 / 问答 → V2
- ❌ 论坛 / 评论 / 点赞 → V3
- ❌ 答题游戏 → V3
- ❌ WebSocket 实时聊天 → V3
- ❌ 微信扫码登录 → V4
- ❌ 艾宾浩斯记忆调度 → V2
- ❌ 微信支付 / 会员 → V4
- ❌ 暗色模式 → V2（先做透亮色，PMF 后再说）

### 3.3 验收标准

- 在桌面浏览器（Chrome / Edge / Safari 最新版）能完整跑通"打开首页 → 浏览 → 看详情 → 登录 → 收藏 → 查看收藏"全流程
- 没有控制台报错
- 移动端可用但不做精修
- 总工期 ≤ 11 个工作日

### 3.4 浏览器兼容

- **支持**：Chrome 110+ / Edge 110+ / Safari 16+ / Firefox 110+
- **不承诺**：IE 任何版本 / 旧版国产浏览器
- **不测试**：360 / 搜狗 / QQ 浏览器极速模式（如需另开专项）

---

## 4. 信息架构

### 4.1 页面清单

| 路径 | 页面 | 鉴权 | 说明 |
|---|---|---|---|
| `/` | 首页 | 公开 | 今日一诗 + 朝代/分类入口 + 热门作品 |
| `/poems` | 诗库 | 公开 | 按朝代/作者/分类筛选 + 列表分页 |
| `/poems/:id` | 诗词详情 | 公开 | 原文 + 注释 + 译文 + 赏析 + 收藏按钮 |
| `/authors/:id` | 作者详情 | 公开 | 作者简介 + 代表作品 |
| `/favorites` | 收藏 | 需登录 | 我收藏的诗词列表 |
| `/login` | 登录 | 公开 | 邮箱验证码 + 账号密码双 tab |
| `/me` | 我的 | 需登录 | 头像 / 昵称 / 退出登录 |
| `/*` | 404 | 公开 | 未找到页 |

### 4.2 全局组件

- `AppHeader`：顶部固定导航（Logo + 导航 + 搜索 + 头像）
- `AppFooter`：底部信息（版权 / 关于）
- `StampSeal`：SVG 印章（贯穿全站装饰）
- `PoemCard`：诗词卡片（用于列表展示）
- `SkeletonLoader`：骨架屏（加载占位）

### 4.3 路由守卫

- `/favorites`、`/me` 未登录跳 `/login?redirect=<原路径>`
- 登录后跳回原路径

---

## 5. 视觉系统

### 5.1 色彩（石青黛影）

| 名称 | 色值 | 用途 |
|---|---|---|
| 米白卷 | `#ece5d5` | 页面主背景 |
| 浅米 | `#f5f0e1` | 卡片背景、副背景 |
| 石青 | `#2d4a52` | 主标题、主按钮、链接、强调线 |
| 落霞橘 | `#d97757` | hover、激活态、印章、关键点缀 |
| 墨 | `#1a1a1a` | 正文文字 |
| 淡墨 | `#888` | 次要文字、注释 |
| 描边 | `#e5dccb` | 卡片/输入框边框 |
| 分割 | `#c9bfa6` | 分隔线 |

**色彩比例原则**（高级感关键）：
- 米白卷 60%（背景）
- 石青 25%（主色）
- 墨 10%（文字）
- 落霞橘 ≤ 5%（强调点缀，**绝不超过 5%**）

### 5.2 字体

| 用途 | 字体 | 字号 / 字距 / 行高 |
|---|---|---|
| 诗词正文 | 思源宋体 (Source Han Serif SC) | 22-32px / 字距 6-10px / 行高 2.0+ |
| 页面标题 | 思源宋体 Heavy | 28-40px / 字距 4-8px |
| 正文 UI | PingFang SC / 微软雅黑 | 14-15px / 行高 1.7 |
| 辅助 / 印章 | 楷体 | 11-12px / 字距 3-4px / 落霞橘 |

**字体加载**：通过 Google Fonts CDN 加载思源宋体（subset: chinese-simplified）。

### 5.3 间距系统

- 基础单位：`8px`
- 桌面端页面左右内边距：`64px`
- 平板：`32px`
- 手机：`16px`
- 段落间距：诗词内部 `24px`，UI 段落 `16px`
- 卡片圆角：`4-6px`（**不超过 8px**，避免现代产品味）

### 5.4 关键 UI 元素

| 元素 | 规范 |
|---|---|
| 主按钮 | 石青底白字 / 4px 圆角 / 无阴影 / hover 时落霞橘描边 |
| 次按钮 | 米白底 + 石青描边 / hover 时石青底白字 |
| 输入框 | 仅底部 1px 石青线 / focus 时变落霞橘 |
| 卡片 | 浅米底 + 1px `#e5dccb` 描边 + 4-6px 圆角 / 无阴影 |
| 分隔线 | 1px `#c9bfa6` 横线 + 落霞橘 4×4 小方块点缀 |
| Logo | "拾诗"宋体 + 落霞橘方印（"诗"字） |
| 加载态 | 骨架屏 + 落霞橘微动效 |

### 5.5 图片策略

**只用少量图片**，关键位置点缀：
- 首页 hero：1-2 张背景图（古风摄影：远山、墨竹、书卷）
- 详情页背景：偶尔出现（诗歌主题相关的图）
- 作者头像：用圆形裁剪
- 装饰：少量 SVG（印章、卷云纹、墨点）做点缀

**图片来源**：Unsplash / Pexels 古风摄影。个人项目，不做版权声明。
**总图片数**：5-8 张，控制在 2MB 以内。
**加载策略**：首页关键图 `<link rel="preload">`，其他懒加载。

---

## 6. 技术栈

| 角色 | 选型 | 备注 |
|---|---|---|
| 框架 | Vue 3 + `<script setup>` | 组合式 API |
| 语言 | TypeScript | 强类型，减少联调错误 |
| 构建 | Vite | 秒级热更新 |
| 路由 | Vue Router 4 | 官方 |
| 状态 | Pinia | 用户信息、收藏列表 |
| UI 库 | Naive UI + themeOverrides | 重染为宋韵 |
| HTTP | Axios + 拦截器 | 自动带 JWT |
| 工具集 | VueUse | 防抖、媒体查询等 |
| 代码规范 | ESLint + Prettier | 一次配好 |
| 图标 | `@vicons/ionicons5` 或 lucide-vue-next | 极简线框 |
| 字体 | 思源宋体 (Google Fonts CDN) | subset: chinese-simplified |

---

## 7. 后端 API 对接

**后端地址**：`E:\javatexts\poetry-spring2`（Spring Boot 3.3.4 + Java 17 + MySQL + Redis）
**本地运行**：`http://localhost:8080`（部署后用户告知线上地址）
**认证方式**：JWT（请求头 `Authorization: Bearer <token>`）
**统一响应格式**：`Result<T>` `{ code, msg, data }`

### 7.1 接口清单（待 Phase 3 与后端 Controller 路径对齐）

| 前端功能 | HTTP | 后端 Controller | 接口路径（推测） | 备注 |
|---|---|---|---|---|
| 首页 - 今日一诗 | GET | PotryController | `/potry/today` 或 `/potry/featured` | 返回 1-3 首 |
| 首页 - 热门 | GET | PotryController | `/potry/hot` | |
| 诗库 - 列表 | GET | PotryController | `/potry/list?dynasty=&author=&page=&size=` | 分页 |
| 诗库 - 朝代列表 | GET | PotryController | `/potry/dynasties` | 用于筛选 |
| 诗库 - 分类列表 | GET | PotryController | `/potry/categories` | 用于筛选 |
| 诗词详情 | GET | PotryController | `/potry/{id}` | 含原文/注释/译文/赏析 |
| 作者详情 | GET | WriterController | `/writer/{id}` | |
| 作者作品 | GET | WriterController | `/writer/{id}/poems` | |
| 登录（账号密码） | POST | UserController | `/user/login` | body: `{username, password}` |
| 登录（邮箱） | POST | UserController | `/user/login/email` | body: `{email, code}` |
| 发送验证码 | POST | UserController | `/user/code` | body: `{email}` |
| 我的信息 | GET | UserController | `/user/me` | 需登录 |
| 收藏列表 | GET | UserController | `/user/favorites` | 需登录 |
| 收藏 / 取消 | POST | UserController | `/user/favorites/{poemId}` | toggle |
| 退出登录 | POST | UserController | `/user/logout` | 客户端清除 token 即可 |

> ⚠️ **实现时需用户确认后端 Controller 路径**，部分推测路径可能需要调整。

### 7.2 前端 TypeScript 类型

```typescript
// src/types/poem.ts
export interface Poem {
  id: string | number
  title: string
  author: string
  dynasty: string
  content: string[]           // 诗句数组（按行）
  annotation?: string         // 注释
  translation?: string        // 译文
  appreciation?: string       // 赏析
  category?: string           // 分类（山水/边塞/送别...）
  createTime?: string
}

export interface Author {
  id: string | number
  name: string
  dynasty: string
  bio: string                 // 生平简介
  avatar?: string             // 头像 URL
  poemCount?: number
}

export interface User {
  id: string | number
  username: string
  email: string
  nickname: string
  avatar?: string
  token: string               // JWT
}

export interface PageQuery {
  page?: number               // 默认 1
  size?: number               // 默认 20
  dynasty?: string
  author?: string
  category?: string
  keyword?: string
}

export interface PageResult<T> {
  total: number
  list: T[]
  page: number
  size: number
}

// src/types/api.ts - 统一响应
export interface ApiResult<T> {
  code: number                // 0 = 成功
  msg: string
  data: T
}
```

### 7.3 Axios 配置

- baseURL：从环境变量 `VITE_API_BASE_URL` 读取，默认 `http://localhost:8080`
- 请求拦截器：自动附加 `Authorization: Bearer <token>`
- 响应拦截器：
  - `code === 0` → 返回 `data`
  - `code === 401` → 清 token + 跳登录
  - 其他 → 弹 toast 提示

---

## 8. 项目结构

```
shi-pick/
├── public/
│   └── favicon.svg
├── src/
│   ├── api/
│   │   ├── request.ts          # axios 实例 + 拦截器
│   │   ├── poem.ts             # 诗词接口
│   │   ├── author.ts           # 作者接口
│   │   └── user.ts             # 用户/登录/收藏接口
│   ├── assets/
│   │   ├── images/             # 5-8 张精选图片
│   │   └── svg/                # 印章、卷云纹 SVG
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppHeader.vue
│   │   │   ├── AppFooter.vue
│   │   │   └── AppLayout.vue
│   │   ├── poem/
│   │   │   ├── PoemCard.vue
│   │   │   ├── PoemContent.vue # 大字号诗本体
│   │   │   └── PoemAnnotation.vue
│   │   ├── common/
│   │   │   ├── StampSeal.vue   # SVG 印章
│   │   │   ├── EmptyState.vue
│   │   │   └── SkeletonLoader.vue
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
│   │   └── index.ts            # 路由 + 守卫
│   ├── stores/
│   │   ├── user.ts             # 用户信息
│   │   └── favorites.ts        # 收藏列表（可后端拉）
│   ├── styles/
│   │   ├── theme.ts            # Naive UI 主题覆盖
│   │   ├── tokens.ts           # 设计 tokens（颜色/间距/字体）
│   │   └── global.css
│   ├── types/
│   │   ├── poem.ts
│   │   ├── author.ts
│   │   ├── user.ts
│   │   └── api.ts
│   ├── utils/
│   │   ├── auth.ts             # token 存取
│   │   └── format.ts
│   ├── App.vue
│   └── main.ts
├── index.html
├── vite.config.ts
├── tsconfig.json
├── tsconfig.node.json
├── package.json
├── .eslintrc.cjs
├── .prettierrc.json
├── .gitignore
└── README.md
```

---

## 9. 里程碑

| Phase | 内容 | 周期 | 交付物 |
|---|---|---|---|
| **Phase 1** | 脚手架 + 主题 + 路由 + 顶部导航 | ~2 天 | 项目能跑起来，访问 `/` 看到带主题的导航 |
| **Phase 2** | 首页 + 诗库列表 + 详情页（mock 数据） | ~4 天 | 三个页面完整功能，使用本地 mock JSON |
| **Phase 3** | 对接后端 API（诗词 + 详情） | ~2 天 | 移除 mock，真实数据流通 |
| **Phase 4** | 登录（邮箱+账号双 tab）+ 收藏 | ~3 天 | 完整闭环 |
| **总计** | | **~11 个工作日** | 可演示的 MVP |

### 关键检查点
- Phase 1 结束 → 用户能看到基本视觉，**确认风格对路再继续**
- Phase 2 结束 → 用户能看到完整 UI 流程，**确认交互对路再继续**
- Phase 3 结束 → **真实数据流通**，可演示给朋友
- Phase 4 结束 → MVP 完整

---

## 10. 后续扩展路线（V2+）

按用户价值和实现成本排序：

| 版本 | 内容 | 优先级 |
|---|---|---|
| V2 | AI 写诗 / 续写 / 问答 | ⭐⭐⭐ 高 |
| V2 | 艾宾浩斯记忆学习 | ⭐⭐⭐ 高 |
| V2 | 暗色模式 | ⭐⭐ 中 |
| V3 | 论坛 / 评论 / 点赞 | ⭐⭐ 中 |
| V3 | 答题游戏 | ⭐ 低 |
| V3 | WebSocket 实时聊天 | ⭐ 低 |
| V4 | 微信扫码登录 | ⭐⭐ 中 |
| V4 | 微信支付 / 会员 | ⭐ 低 |

---

## 11. 风险与对策

| 风险 | 概率 | 影响 | 对策 |
|---|---|---|---|
| 用户零前端经验 | 高 | 中 | Naive UI 兜底，AI 助手逐步引导；每个 Phase 都有可演示产物 |
| 后端 API 路径与推测不符 | 中 | 中 | Phase 2 用 mock 数据先做 UI；Phase 3 用户一起对照 Controller 调整 |
| 宋韵长卷视觉不到位 | 中 | 高 | 严格遵循设计 tokens；每 Phase 截图自查；可让用户随时看效果 |
| 字体加载慢（思源宋体大） | 中 | 低 | subset 化（仅 chinese-simplified）；CDN 加载；本地 fallback |
| 桌面端做好但移动端崩 | 中 | 低 | 桌面做完再做响应式；MVP 不承诺完美移动端 |
| JWT token 过期处理 | 中 | 中 | Axios 拦截器统一处理 401；自动跳登录 + 带 redirect |
| Naive UI 默认风格残留 | 中 | 中 | themeOverrides 全覆盖；自定义组件优先 |

---

## 12. 假设与开放问题

**假设**：
- 后端会在本地或服务器跑起来供前端联调
- 用户有 Node.js 18+ 环境
- 后端 JWT 密钥已与前端协商约定（在 localStorage 存）

**待用户确认**：
1. 前端项目放哪里？建议 `E:\javatexts\frontend\shi-pick\` 或同目录的兄弟文件夹
2. 后端 API 路径表（Phase 3 实施时对齐）
3. 部署目标：是只在本地跑，还是要部署到某个服务器？

---

## 13. 不在本设计范围内

明确不做、避免范围蔓延：
- 移动 App / 小程序
- SEO 优化（V2 再考虑 Nuxt SSR）
- 多语言（先做中文）
- 数据分析 / 埋点
- 国际化部署
- 复杂权限管理（无管理后台）

---

**审核记录**：
- [ ] 用户审阅通过
- [ ] 后端接口路径对齐
- [ ] Phase 1 启动

