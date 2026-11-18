# 重新认领路线(READING-PATH)

> 目标:把被 AI 改造过的项目重新变成"你的"项目。每步 ≤30 分钟,按"先入口、后细节"排序;
> 每步末尾有自测问题——答不上来就回去再走一遍,不要跳。全程请开着 `docs/ARCHITECTURE.md` 对照。
> 预计 9 步 ≈ 4~5 天(每天 1~2 步 + 复述)。

## 第 1 步 · 全景与手感(30min)

1. `./start-all.bat` 拉起全栈,浏览器开 `http://localhost:5173` 把 12 个页面点一遍;再开 `http://localhost:8000/nav` 看 Agent 运维导航。
2. 通读 `docs/ARCHITECTURE.md` §2 架构图与 §3 模块地图。

**自测**:① 五个端口分别是谁?② 前端请求有几条路径绕过网关?③ 哪个模块是死模块?

## 第 2 步 · 走通一条最短读链(30min)

从"点开诗词列表"追到数据库,共 5 跳:
`PoetryList.vue` → `src/api/poetry.ts` → `utils/request.ts`(token 注入)→ vite 代理 → 网关 `AuthGlobalFilter` → `PoetryController.GetPoemPage` → PotryMapper → MySQL `poem.potry` 表。
随手做:在 `utils/request.ts:47-53` 的 401 拦截下个断言,前端登出再刷新,看它触发。

**自测**:① token 在哪注入、在哪验(几道防线)?② 401 之后发生什么?③ 为什么 `/notice`、`/ai` 在 vite.config 里是逐端点登记而不是整体代理?

## 第 3 步 · 数据模型(30min)

对照 ARCHITECTURE §6 的表清单,打开 `poetry-pojo/.../entity/` 抽 5 个实体(UserJo、Potry、UserBook、UserCollectionPoem、ForumComment)与表对上;再看 Agent 侧 `potry-ai-agent/db.py:10-78` 怎么只读这 6 张表。

**自测**:① 收藏一首诗涉及哪几张表?② Agent 为什么直连 MySQL 而不走 Java 的 API?这个设计的代价是什么?③ 哪张表的列名有历史拼写错误?

## 第 4 步 · AI 对话主链(45min,本项目最核心)

按 ARCHITECTURE §5 链路2 走:`AiChat.vue:167` fetch SSE → 网关 → `main.py:544` → `workflow/graph.py:63-102` 12 节点 → `agent_react.py` ReAct → `nodes.py:292-311` ticket_confirm interrupt → SSE 分帧回传。
随手做:在 `/ai` 页发一句"推荐一首李白的诗",对照 `run-agent.log` 和 Langfuse 里出现的节点顺序,找出 retrieve→gate 的置信度打分。

**自测**:① thread_id 是什么、状态存哪?② 哪个节点会"暂停等人确认"、前端怎么放行?③ 上下文三层各是什么、层2 超预算后发生什么?

## 第 5 步 · RAG 与知识库(30min)

`build_kb.py` 切块→BGE-M3→Milvus;`kb_sync_api.py` 三层对账;管理台"知识库同步"卡片(`/console/content`)对应 `GET /api/admin/kb/syncstats`。
随手做:调一次 syncstats,看 potry_total/covered/pending/embedded 四个数现在多少。

**自测**:① 为什么离线建库必须先停 Agent?② 导入一首诗后,知识库是怎么"自动"更新的?(提示:PotryController.java:64-79)③ EVIDENCE_CONFIDENCE_THRESHOLD=0.46 是怎么来的?

## 第 6 步 · 两条实时链(30min)

发帖推送:发帖 → RabbitMQ post.exchange → PostNotifyListener → STOMP `/topic/newpost` → Forum.vue 刷第一页;失败有 DLX + 20s 补偿重投。
背诵提醒:ReviewRemindTask 每日 9:00(批次锁+用户防重)→ `/topic/review.{userId}` → reviewRemind.ts toast → 今日任务 → `query/end?kk=1` 推进艾宾浩斯轮次。
随手做:管理台手动触发一次 remind/trigger,观察自己的 toast。

**自测**:① MQ 挂了帖子推送还能不能到?(两层兜底是什么)② 提醒的"当日只提醒一次"靠哪两个 Redis key?③ 背诵轮次的天数序列在哪定义?

## 第 7 步 · 管理端与鉴权体系(30min)

`/console` 与 `/console/content` 两页 → `api/adminApi.ts`(独立 axios 实例)→ 网关 `/admin/**` 管理密钥 → 后端管理拦截器。对照前端路由 `/console*` 是 public、AppNav 对所有登录用户展示入口——理解"前端裸奔、后端兜底"的现状。

**自测**:① 用户端和管理端 JWT 的差异(密钥、claims、header)?② 为什么说 /console 前端"没锁门"?要在路由层加守卫该改哪?③ Agent 的 admin 接口用什么密钥?

## 第 8 步 · 精读体检报告,亲手验证三个疑点(30min)

打开 `docs/ARCHITECTURE.md` §7,挑三个 P1/P2 疑点亲手证实或证伪,例如:
- 打开 `Mapper/UserMapper.xml:14-22` 确认 `UPDATE your_table` 占位;
- 全局搜 `@Cacheable` 证实 @EnableCaching 是空转;
- 全局搜 ai.ts 的 import,证实 10 个函数零调用。

**自测**:① 53 个死 API 函数是怎么产生的?(对照 git log:AI 改造用新方案替换旧方案后未回收)② 你验证的三个疑点,修复成本各多大?

## 第 9 步 · 实操任务:亲手回收一块"AI 遗产"(45min,动真格)

> **更新(2026-10-25)**:下面三个选项已由 AI 代为执行并验证——`/build/bulid` 已删除并 404、requirements.txt 已补齐、前端 ai.ts/comment.ts/.bak 及 vite 死代理已清(vitest 8 绿 + vue-tsc build 通过)。想补上"亲手做"的手感,改做:
> ① 清理剩余 38 个死 API 函数(从 `notice.ts`、`feedback.ts` 开始,每删一组跑一次 `npm test`);
> ② 修 `GET /user/forget` 用 `@RequestBody` 的反模式(UserController.java:154-156,改成 query 参数,注意前端同步);
> ③ 清根目录杂物(`out/`、`-m/`、练手 java、`*.log`、mp3)并补 `.gitignore`,给仓库一次"断舍离"。

三选一(都建议先开分支):
1. **补依赖**(最稳,15min):把 PyJWT、langfuse、onnxruntime、requests 补进 `potry-ai-agent/requirements.txt`,删掉未用的 modelscope,重装 venv 后 `pytest -q` 仍 423 绿。
2. **回收死代码**(30min):删 `frontend/src/api/ai.ts` 与 `comment.ts` 全文件、5 个 `.vue.bak`,顺带清 vite.config 里只服务死代码的 `/ai/*` 代理;`npm test` 8 绿 + 手点 /ai、/forum 页确认无恙。
3. **堵最危险的洞**(40min,需谨慎):给 `buildSqlController` 加管理端鉴权或直接删除该 Controller,重启后端,验证 `/build/bulid` 返回 401/404。

做完提交一条自己的 commit(信息写清"人工回收",和 AI 代改的提交区分开)——**这一步的意义是重新建立"每个文件我都有权决定去留"的所有权**。

## 之后

- 每周复述一遍架构图(不看书,画在纸上,对照 §2 查漏)。
- 发现新的疑点随手补进 `ARCHITECTURE.md` §7,让文档跟着仓库长。
- 面试前过一遍 `dev-notes/interview-quickcard.md`,把本导览的链路 2/4/5 练成能白板画的程度。
