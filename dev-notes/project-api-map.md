# 古韵传习堂 · 项目全景 API 地图（2026-10-25 整理）

> 给自己的项目导览 + 面试底稿。Java 端 ~150 个映射、Agent 端 19 个路由，
> 按**业务域**组织（不是按 Controller 文件），核心接口详讲、同类 CRUD 合并。
> 接口契约细节以 COORDINATION.md §3 为准；性能数据见 resume-metrics-plan.md。

---

## 0. 架构总览与请求流

```
浏览器(Vue:5173)
   │  统一走网关
   ▼
poetry-gateway(9080) ── JWT鉴权(用户/管理双密钥+legacy轮换) + Redis令牌桶限流(2000/s+突发4000)
   │ Nacos 服务发现(lb://服务名)
   ├────────────────────► potry-service(8081, Java)  ←→ MySQL8.4(25表) / Redis5.0
   │                              │ afterCommit
   │                              ▼ RabbitMQ(post.exchange→死信+重试)
   │                              ▼ STOMP WebSocket(/ws, /topic/*)
   └────────────────────► potry-ai-agent(8000, Python)  ←→ Milvus向量库 / Langfuse观测
基础设施: Nacos(8848) · RabbitMQ(5672/15672) · Prometheus(9091) · Grafana(3001) · Langfuse(3000)
入口聚合: http://localhost:8000/nav(运维导航台)
```

三个角色一句话：**网关管门禁**（谁进、进多少）、**Java 管业务与数据**（一切写操作）、**Agent 管 AI**（检索问答/工作流/飞轮）。

---

## 1. 认证与用户域（/user/*，UserController）

| 接口 | 作用 |
|---|---|
| POST /user/login | 账号密码登录 → JWT（无密码账号提示"未设置密码"） |
| POST /user/login/email | 邮箱验证码登录，**新用户自动隐式注册** |
| GET /user/login/code?phone= | 发邮箱验证码（60s 限流 + 异步发送 + 一次性消费） |
| POST /user/register | 注册（存量 bug：500，backlog 待修） |
| GET /user/forget | 忘记密码流程 |
| GET /user/getmassagebyid / PUT | 个人资料查改 |

技术点：JWT 双密钥（用户/管理员隔离）+ legacy 轮换、验证码防重放、mailThreadPool 异步化。

## 2. 诗词检索域（/user/poetry/*，约 30 个，PoetryController）

**核心链路（搜索一条龙）**：
- GET /suggest?kw= → 自动补全（ZSet rangeByLex，8 条，降级 DB 前缀索引）
- GET /GetPoembyTitle?title= → **主搜索**（≥2 字 FULLTEXT ngram 短语匹配，单字回退 LIKE；埋点热搜）
- GET /hotsearch → 24h 热搜 Top10（ZINCRBY + 防刷）

**浏览与详情**：
- GET /GetPoemsByDynasty?dynasty=&pageNum= → 朝代分页（缓存+索引，压测主力接口 QPS 977）
- GET /GetPoemPage → 全量分页（带当前用户点赞状态）
- GET /GetContentById/{id} → 详情（cache-aside + 空值缓存防穿透 + 坏缓存自愈）
- GET /GetCount / GetAllDynasty / GetDynastyandpoem → 聚合数据（逻辑过期+互斥重建防击穿）

**随机族（全部走 Redis 随机 id 池，ORDER BY RAND() 已清零）**：
- GET /GetPoemDateRondom（随机 10 首）、/GetVeryGoodPoem（今日推荐 1 首）
- GET /Get（随机诗人分页卡片，QPS 133→932 那个改造）

**其余**：按诗人/朝代/类型多维查询（GetPoemByWriter、GetPoemByType、GetwriterBywriter…约 15 个变体）、
GET /query/end?poemid= → **答题正确触发 SRS 复习推进**（一条 SQL 原子推进轮次+下次时间）。

## 3. 名句域（/user/rhesis/*，RhesisController）

GetRhesisDateRondom（随机 10 条，rhesis:idpool 池化）、GetVeryGoodRhesis（今日名句）、
GetRhesisByKey/{keyword}（搜索）、GetRhesisPage（分页，语义已修复为随机 N 条+真实 total）等 8 个。

## 4. 诗人域（/user/writer/*，WriterController）

GetRandomWriters（随机 5 位，writer:idpool）、getWritersByPage（分页）、
getPoemsByWriter、GetRandomPoems（复用 potry 池）等。

## 5. 论坛域（/user/luntan/*，18 个，PoemLunTanController）

**发帖链路（事件驱动核心故事）**：
- POST /fabutiezi → 发帖（事务提交后投 MQ）→ 消费者：粉丝收件箱(ZSet 推模式 feed) + 帖子缓存 + STOMP 广播
- GET /selecttiez → 帖子列表（分页+类型过滤）；/selectxiangxi → 详情（收件箱点开走缓存）
- GET /dianzan / commentdianzan → **点赞 toggle**（幂等版：ZADD 原子占位+明细表事实源+死锁重试）
- GET /dianzanrank → 点赞排行
- GET /guanzhu / isguanzhu / select/user/{id}… → 关注/粉丝体系（tb_follow）
- POST /fabacomment + GET /selectConmmets → 评论（**两级模型**：parentId 归一根评论、
  replyToUserName"回复@"、两段式加载 615ms→21ms）
- GET /search → 论坛搜古诗（FULLTEXT 短语匹配版）

## 6. 背诵学习域（SRS，/user/book/*，UserController 内）

| 接口 | 作用 |
|---|---|
| POST /book/statr | 按学历智能配诗建书（修复断链 bug 后真正入库） |
| POST /book/start | 开始背诵：按 N 首/天排期（窗口函数一条 SQL，65x 提速），首复习=学习日+1 |
| GET /book/today?bookid= | **今日应复习列表**（dueStage 轮次文案，agent 端 get_study_plan 同源） |
| GET /book/remindcount / remindlog | 提醒红点 / 最近 7 天提醒历史（⑳ 新功能） |
| GET /book/show*、showplan | 书架与排期展示 |
| GET /query/end（poetry 域） | 答对推进轮次：间隔 1/3/7/14/30 天，第 5 轮毕业 |

## 7. 收藏与评论杂项（/user/collect*、/user/Comment）

collect/addpem、collect/ids（agent 端 get_my_collection 工具读的就是 usercollectionpoem 表）、
名句收藏 addrhesis 等；Comment 域 thumb/reply（旧评论体系，论坛评论在 luntan 域）。

## 8. 答题游戏域（/user/game/*，QuestionGameController）

questions（出题，随机诗抽取）、check（判分）、score、getRank（**Redis ZSet 排行榜**，
Lua 保证仅更高分覆盖，修复同用户重复上榜）、SelectPage。

## 9. AI 对话域（/ai/*、/user/AI/*）

- GET /ai/submita → **Java 侧 SSE 流式 AI 对话**（多诗人角色人设 + 上下文记忆）
- /user/AI/getCharacter 等 → 诗人角色卡管理（preset-message 预设Prompt）
- /user/AI/draow、Interactive → AI 画图/互动实验接口

## 10. 管理端域（/admin/*、/notice/*，约 43 个映射）

**鉴权**：JwtTokenAdminInterceptor + 网关双密钥（管理 token 物理隔离用户 token）；公告读白名单游客可访问。

| 模块 | 接口组 |
|---|---|
| /admin（AdminController） | login/getCode（图片验证码 String+5minTTL）/register/disable/{status}/getAll/getUserCount + **remind/trigger**（手动触发复习提醒跑批） |
| /admin/potry | 诗词 CRUD + 分页 |
| /admin/writer | 诗人 CRUD + 头像更新 |
| /admin/rhesis | 名句 CRUD |
| /admin/blog | 帖子管理（getAllBlog/deleteBlog） |
| /admin/log | 操作日志 |
| /admin/command | AI 指令处理（handle/forum） |
| /notice | 公告 CRUD（get/getList 游客白名单，写操作需 admin） |

## 11. 实时通道（WebSocket）

- 端点 `/ws`（SockJS 或原生 ws://host/ws/websocket + STOMP 帧）
- 订阅 `/topic/newpost` → 新帖实时推送（发帖→MQ→消费者→广播，端到端 411ms）
- 订阅 `/topic/review.{userId}` → **复习提醒**（`{type:"review_remind",count,date}`）

---

## 12. Agent 端（potry-ai-agent:8000，Python/FastAPI/LangGraph）

### 对话与工作流（SSE 流）
| 路由 | 作用 |
|---|---|
| POST /agent/chat | 轻量聊天 SSE：`meta→tool_status*→token*→done` |
| POST /agent/workflow | **主编排** SSE：`meta→trace→tool_status*→token*→action?→done`（意图路由→RAG 检索→置信度闸→主力 Agent→自评入链；trace 帧含八行编排轨迹；action 帧可下发 forum_draft 草稿卡） |
| POST /agent/workflow/resume | 放行"工单确认"类 interrupt 续跑 |
| POST /agent/feedback（/negative） | 消息级 👍👎 → 数据飞轮负反馈入口 |
| POST /agent/correction | 纠错提交 |
| GET /api/conversations、/{sid}/messages | 会话列表/回放（前端侧栏用） |

### 管理面（/api/admin/**，需管理端 token）
GET /api/admin/review（列表/详情）+ approve/reject → **数据飞轮人工审核**（低置信/负反馈问题池回流知识库）；
GET /api/admin/cost?days=N → 按意图 token/成本报表；GET /api/admin/audit → 工具调用审计流。

### 运维面
GET /nav（运维导航台）、/chat /admin/review /admin/cost（自带页面）、/health、/metrics（Prometheus）。

### Agent 只读的 Java 表
usercollectionpoem（收藏工具）、userbook/userbookpoem（学习计划工具）、poem_blog（论坛工具）。

---

## 13. 四条必讲业务链（面试串讲用）

1. **搜索**：输入→suggest 补全（ZSet 字典序）→回车 GetPoembyTitle（FULLTEXT ngram 短语/单字回退）→埋点热搜→返回分页
2. **发帖通知**：写库（事务）→afterCommit 投 MQ（失败进 Redis 补偿队列 20s 重投）→消费者（重试 3 次+死信+幂等）→粉丝收件箱+缓存+STOMP 广播→在线用户 toast
3. **背诵闭环**：statr 配诗→start 排期→每天 today 列表→答题 query/end 推进轮次→9 点定时扫到期→STOMP 提醒→remindcount 红点
4. **AI 问答**：Vue→网关 lb://potry-ai-agent→意图识别→RAG（BGE-M3+Milvus top5）→置信度闸（0.46 校准值）→过闸 LLM 生成/不过闸入飞轮→SSE token 流→自评→Langfuse trace

## 14. 遗留与已知问题

- /user/register 存量 500（backlog）
- 旧反馈队列 kkk 绑定错位（backlog#4）
- ch08 评估流水线（agent 端）、admin CRUD 补 @AutoLog 等小项（见 COORDINATION §9.3）
