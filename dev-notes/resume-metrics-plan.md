# 简历真实数据产出计划（Java 服务侧）

> 2026-10-24 生成。目标：为简历上每个技术点配上**自己测出来的**真实数据。
> 核心理念：**"技术提高了什么" = 优化前基线 → 优化后对比**。本项目的"优化前"状态是现成的
> （potry 表无二级索引、查询接口无缓存），所以每条数据都真实、可复现、面试经得起追问。

---

## 一、已经到手的真实数据（2026-10-24 实测，MySQL 8 本机）

| 数据 | 数值 |
|---|---|
| 诗词语料 | **10,778 首**（potry 表，数据 16.5MB） |
| 名句 | 10,001 条（rhesis） |
| 诗人 | 153 位 |
| AI 知识库切片 | knowledge_chunks 33.6MB（RAG 语料） |
| 应用表 | 25 张（含论坛/收藏/答题/审核等） |

### 数据库层实测（优化前基线，这就是简历故事的"前半段"）
- `WHERE dynasty='唐代'`：EXPLAIN **type=ALL 全表扫描**，扫描 9,825 行，热查询 **22~31ms**（返回 1,354 行）
- `WHERE title='静夜思'` 精确查：**6.5~9.6ms**（无索引全表扫）
- `title LIKE '%月%'`：**8~9ms**（404 行）
- **索引现状：只有主键 + 两个完全重复的 writer 单列索引**（potry_writer_index / potry_writer_index_2，本身就是"清理冗余索引"的素材）

---

## 二、技术点 → 实验 → 简历话术（按性价比排序）

### ① MySQL 索引优化（2026-10-24 实测完成，git 未提交）
- **改动**：`idx_dynasty(dynasty)`、`idx_title(title)`；删除重复索引 `potry_writer_index_2`
- **证据**：EXPLAIN 由 type=ALL 全表扫 9,825 行 → key=idx_dynasty 精确命中
- **实测**（朝代分页接口，与 ⑥' 调优后同一基线对比）：

| 并发 | 索引前 QPS / P99 | 索引后 QPS / P99 |
|---|---|---|
| 50 | 745 / 141ms | 904 / 123ms |
| 100 | 750 / 314ms | **977 / 238ms（+30%）** |
| 200 | 689 / 731ms | 931 / 542ms（+35%） |

- **话术**：
  > 通过 EXPLAIN 定位朝代/标题查询全表扫描（扫描 9,825 行），设计 dynasty/title 索引并清理 2 个冗余索引，
  > 朝代分页接口 QPS 750→977（+30%），P99 314→238ms。
- 另发现 `potry_id_uindex` 与 PRIMARY 重复（未处理，可作为后续清理项）

### ② Redis 缓存 + 随机查询改造（2026-10-24 实测完成，git 未提交）
- **缓存**（cache-aside，10 分钟 TTL）：`getcount`、`GetAllDynasty`(distinct)、`GetDynastyandpoem`(group_concat 聚合)
  —— 实测 Redis 命中率 **97.6%**（keyspace_hits 167 / misses 4）
- **随机改造**：5 处 `ORDER BY RAND()` 中的两处热路径（随机诗/推荐诗）改为
  **Redis Set 随机 id 池（SRANDMEMBER）+ 主键 IN 回表**，池 1 小时过期自愈，异常降级回 RAND()
- **实测**（单次延迟，30 次采样）：

| 接口 | 改造前 | 改造后 |
|---|---|---|
| 随机诗 ×10 | 12.9ms | **5.8ms（-55%）** |
| 朝代聚合 group_concat | 10.6ms | **5.2ms（-51%）** |
| 朝代列表 distinct | 4.7ms | 3.6ms |
| 诗词总数 COUNT | 2.6ms | 4.4ms（本地 Redis 往返，量级无差） |

- 随机诗接口并发：**c=100 QPS 1,148、P99 192ms、零错误**（改造前并发基线未单独采集，引用单次 -55% 延迟数据）
- **话术**：
  > 为静态语料的高频读取接口引入 Redis cache-aside 缓存（命中率 97.6%），随机推荐由 ORDER BY RAND()
  > 全表扫描+filesort 改造为 Redis 随机 id 池+主键回表，随机接口延迟 -55%；配合索引优化，
  > 朝代分页 QPS +30%。（剩余 3 处 writer 侧 ORDER BY RAND() 已于 ⑭ 清零；
  > 搜索接口 %x% 前置模糊已于 ⑮ 改造为 FULLTEXT ngram）

### ③ RabbitMQ 异步解耦 + WebSocket 实时推送（2026-10-24 实测完成，git 未提交）
- **改造**：发帖通知链路从"线程池直推"改为**事件驱动**——
  发帖事务 `afterCommit` 后投递 MQ（`post.exchange` → `post.notify.queue`，routingKey `post.created`），
  消费者（@RabbitListener 声明式建队列）承担：①粉丝 ZSet 收件箱（推模式 feed）②帖子内容缓存 1h
  ③**STOMP 广播 /topic/newpost**（WebSocket 基建首次启用，在线用户实时收到新帖提醒）
- **事务一致性**：afterCommit 投递，避免消费者读到未提交数据；获得削峰/重试/发布订阅解耦能力
- RabbitMQ 以 Docker 运行（`poetry-rabbit` 容器，5672/15672，管理台 guest/guest）
- **实测**（端到端脚本 `docs/bench/test_mq_stomp.py`）：
  - 发帖接口 RT **96ms**（含事务提交+MQ 投递）
  - **发帖→MQ→消费者→STOMP 推送→订阅者收到，端到端 411ms**
  - 收件箱 ZSet、帖子缓存 TTL 3600s、队列消息即产即消（消费者 1 在线）
- 顺带发现（未动，登记台账）：旧反馈链路 `kkk` 队列绑定错位（发到 myExchange 却绑到 amq.topic，
  消息发出即丢）且无消费者；点赞双存储一致性问题仍在 backlog
- **话术**：
  > 论坛发帖通知改造为 RabbitMQ 事件驱动：事务提交后投递（afterCommit 防脏读），消费者
  > 完成粉丝收件箱（Redis ZSet 推模式 feed）、内容缓存与 WebSocket(STOMP) 在线实时推送；
  > 实测发帖→订阅者收到推送端到端 411ms，队列即产即消，接口 RT 96ms，获得削峰与重试能力。

### ④ SSE 流式 AI 对话（多诗人角色 Agent，前端体验故事）
- **实验**：`curl -N` 记录首字节时间（TTFB）vs 完整响应时间。
- **话术模板**：
  > AI 诗人角色对话采用 SSE 流式推送，首 token 延迟 __ms，相比整体返回用户可感知等待降低约 __%，
  > 支持 8 个诗人角色人设与上下文记忆（InMemory ChatMemory）。

### ⑤ JWT 双端认证 + 验证码链路（2026-10-24 已完成一轮加固，git 未提交）
- **已落地改动**（当天的回归测试 6 场景全过）：
  - 修复：新用户首次邮箱登录 NPE 500（Controller 先建号后查用户的顺序问题）
  - 修复：验证码错误返回字符串假 token（改为抛 AccountNotFoundException）
  - 修复：登录异常被 catch(Exception) 吞成 Internal server error（区分业务异常）
  - 验证码一次性消费：校验通过即删 Redis key，防 10 分钟内重放
  - 发送限流：同邮箱 60s 一次（Redis setIfAbsent）
  - 异步发送：新增 mailThreadPool（3/8/100/CallerRuns），SMTP 不再阻塞请求线程（实测接口 337ms 返回，邮件后台发送中）
  - OTP 用户不再设默认密码 123456（password NULL，密码登录友好拦截）
- **改造前基线尚未压测**：改动未 commit，可用 `git stash` 回旧版打包测同步版 RT（≈SMTP 耗时 1~2s）作对比
- **话术模板**：
  > 邮箱 OTP 无密码登录与隐式注册；验证码一次性消费 + 60s 发送限流防重放防轰炸；
  > 发送链路线程池异步化（独立 mailThreadPool，CallerRuns 降级），接口 RT 由 __ms 降至 __ms；
  > JWT 双端密钥隔离 + 拦截器统一鉴权（ThreadLocal 传递用户上下文），鉴权开销实测 < __ms。

### ⑥' 连接池/线程池调优（2026-10-24 实测完成，git 未提交）

**压测条件**：本机全家桶（客户端+服务+MySQL+Redis 同机），`GetPoemsByDynasty` 接口，
每档并发 20s（脚本 `docs/bench/bench_poetry.py`，python requests 多线程）。

**调优前**（Hikari 默认 10 连接，MySQL Threads_connected 实测钉死 11）：

| 并发 | QPS | avg | P95 | P99 | 错误 |
|---|---|---|---|---|---|
| 10 | 543 | 18ms | 30 | 38 | 0 |
| 50 | 717 | 69ms | 120 | 151 | 0 |
| 100 | 669 | 146ms | 275 | 365 | 0 |
| 200 | 663 | 253ms | 557 | 783 | 0 |

**调优后**（hikari 20/min-idle 5/conn-timeout 3s + tomcat 显式 200/20/200 + 修 forumThreadPool
拒绝策略顺序 bug + 修 lettuce 池矛盾配置；实测连接按需涨到 15）：

| 并发 | QPS | avg | P95 | P99 | 错误 |
|---|---|---|---|---|---|
| 10 | 620 | 16ms | 24 | 30 | 0 |
| 50 | 745 | 67ms | 113 | 141 | 0 |
| 100 | 750 | 130ms | 239 | 314 | 0 |
| 200 | 689 | 241ms | 525 | 731 | 0 |

**结论**：瓶颈从 Hikari 10 连接（QPS 钉死 ~670）转移到单机 CPU（客户端/服务/DB 同机竞争），
c=100 档 QPS +12%、P95 -13%、P99 -16%。面试要点：
- 10 连接 ÷ 15ms/查询 ≈ 670 QPS，**QPS 上限 = 连接数 / 单查询耗时**（Little's Law 现场推导）
- 压测期间 `SHOW STATUS LIKE 'Threads_connected'` = 11（前）/15（后）是连接瓶颈的直接证据
- **坑1**：`ThreadPoolTaskExecutor.setRejectedExecutionHandler()` 在 `initialize()` 之后调用不生效，
  forumThreadPool 实际跑默认 AbortPolicy（队列满抛异常静默丢通知）
- **坑2**：lettuce 池配了 `max-idle:0 + min-idle:100`（自相矛盾）
- **坑3**：`max-active` 曾被误认为 MySQL 连接池——那是 lettuce 的属性；Hikari 默认才 10

**话术模板**：
> 压测定位 HikariCP 连接池（默认10）为 DB 型接口瓶颈（QPS 钉死 ~670，Threads_connected 佐证），
> 调优至 20 并显式配置 Tomcat 线程模型，c=100 档 QPS +12%、P99 -16%；修复线程池拒绝策略
> 注册顺序 bug（initialize 后 set 不生效导致 AbortPolicy 丢任务）。


### ⑥ 观测体系：Actuator + Micrometer + Prometheus + Grafana（2026-10-25 实测完成）
- **改造**：
  - potry-service 与 gateway 接入 spring-boot-starter-actuator + micrometer-registry-prometheus，
    `/actuator/prometheus` 输出指标（application 标签区分服务）
  - Prometheus（5s 抓取双服务）+ Grafana 11.3（**datasource 与大盘全自动 provisioning**，
    免手工配置）——大盘 8 面板：HTTP QPS/按 uri 的 P95/P99、HikariCP active/idle/pending、
    Tomcat 线程、JVM 堆 used/max、GC 暂停、5xx 错误率、进程 CPU
  - **全链路 traceId**：网关 GlobalFilter 生成/透传 X-Trace-Id（响应头回带），服务 Filter 写入
    MDC（日志 pattern 输出 `[traceId]`），MQ 生产者 afterCommit 同线程读 MDC 随消息头透传、
    消费者取回填 MDC —— **实测同一 traceId 贯穿 HTTP 线程与 MQ 消费线程日志**
    （发帖请求三行日志：服务处理→发布成功→消费者"发帖通知消费完成"，`[57717ec922114280]` 全程一致）
  - health 治理：mail 指标器关闭（异步旁路不参与健康判定），RabbitMQ 保持（核心依赖）
- **踩坑（都是实测发现的）**：
  1. **Micrometer 默认不发 http_server_requests 直方图分桶**（只有 count/sum/max），
     `histogram_quantile` 查不到 P95/P99 —— 必须显式
     `management.metrics.distribution.percentiles-histogram.http.server.requests: true`
  2. **服务端 P99 ≠ 客户端 P99**：c=50 压测下服务端 P95=3ms（朝代分页，缓存命中路径）
     vs 客户端 P95=106ms —— 差额在并发排队/网络/客户端调度，这是"慢在服务还是慢在排队"
     的定位依据
  3. health 聚合默认纳入 Rabbit/Mail 等外部依赖，中间件缺席时整体 DOWN（误判健康）
  4. 部署侧：本机 Docker 引擎拉镜像时反复崩溃 → 降级为 Windows 裸跑二进制
     （dl.grafana.com 国内限速 ~40KB/s 且镜像站无 Windows 包，用 HTTP Range 8 段并行下载
     185MB 解决）；两套启动方式都落在仓库 deploy/observability/
- **实测验证**：Prometheus 双 target up；Grafana datasource health OK + 大盘自动加载；
  压测期间实时采集：QPS 209（爬坡中）/按 uri P95/P99 可查、Hikari active 0/pending 0/idle 13
  （朝代分页走缓存命中路径，DB 无压力——缓存效果的直接观测证据）、heap 196MB、GC 0.001s/s
- **话术**：
  > 搭建 Spring Boot Actuator + Prometheus + Grafana 可观测体系（datasource/大盘全自动
  > provisioning，8 面板覆盖 HTTP P95/P99、连接池、JVM、错误率），并实现全链路 traceId：
  > 网关生成透传→服务 MDC→MQ 消息头→消费者回填，一次发帖请求的日志可跨 HTTP 与消费线程
  > 串联检索；压测中通过大盘实时定位缓存命中路径（服务端 P95 3ms、连接池零活跃）与客户端
  > 排队（106ms）的差异；沉淀 Micrometer 直方图默认关闭、health 聚合误判外部依赖等实测坑。

### ⑧ 排行榜 Redis ZSet 改造（2026-10-24 实测完成，git 未提交）
- **修复的 bug**（有铁证）：原 SQL `SELECT DISTINCT * FROM gamerank ORDER BY grand DESC LIMIT 20`
  对多行记录的用户会**重复上榜**（实测构造用户 777 两条高分 → top20 霸榜 2 个位置）
- **改造**：MySQL 保留全量记录（审计+重建来源）；Redis ZSet `gamerank:zset`（member=userid，
  score=最高分）+ Hash `gamerank:names`；写入用 **Lua 脚本保证"仅更高分覆盖"原子性**
  （Redis 5.x 无 ZADD GT 的替代方案）；读走 ZREVRANGE top20；空池自动从 MySQL GROUP BY 重建；
  Redis 异常降级回 MySQL 查询
- **实测**（10,001 行 gamerank，同口径压测）：

| 并发 | MySQL 排序版 | ZSet 版 |
|---|---|---|
| 10 | QPS 891 / P99 20ms | QPS 878 / P99 25ms（持平） |
| 50 | QPS 878 / P99 116ms | **QPS 994 / P99 106ms（+13%）** |

- **诚实注解**：1 万行时 MySQL warm 排序本身 ~11ms，差距随数据量增长拉大
  （MySQL O(N log N) 全表排序 vs ZSet O(log N)）；核心收益是正确性修复 + 读路径与数据量解耦
- **话术**：
  > 答题排行榜存在同用户多行重复上榜缺陷（DISTINCT * 语义误用），改造为 Redis ZSet：
  > Lua 脚本原子保证"仅更高分覆盖"（Redis 5.x 无 ZADD GT 的替代实现），ZREVRANGE 取 Top20，
  > MySQL 保留审计与重建来源，空池自动聚合重建、故障降级；修复重复上榜缺陷，并发吞吐 +13%，
  > 读路径复杂度由 O(N log N) 降为 O(log N)。

### ⑨ 网关统一鉴权 + Redis 令牌桶限流（2026-10-24 实测完成，git 未提交）
- **改造**：poetry-gateway 新增 `AuthGlobalFilter`（GlobalFilter，order -100）——
  与服务端拦截器同语义（保护 /user/** 与 /ai/**、白名单 4 条、兼容 SSE query 传 token），
  jjwt 0.9.1 同密钥验签，通过后透传 X-User-Id；`default-filters` 挂 `RequestRateLimiter`
  （Redis 令牌桶，按 IP KeyResolver，正式档 2000 QPS/s + 突发 4000）
- **限流验证**（演示档 100/s + 突发 200）：0.7 秒内 300 次并发 → **放行 200（=桶容量）、
  429 拒绝 100**，令牌桶行为与配置精确吻合
- **网关链路开销**（c=100，含 JWT 验签 + Redis 限流 + Nacos 负载均衡转发）：
  直连 8081 QPS 859 / P99 273ms → 经网关 9080 QPS 827 / P99 269ms（**吞吐 -3.7%，P99 持平**）
- **部署注**：网关端口 9000 → **9080**（重启后 Docker Desktop/WSL wslrelay 动态占用 9000/9090），
  前端 vite 代理已同步
- **话术**：
  > 网关层实现统一 JWT 鉴权（GlobalFilter + 与业务服务同密钥验签、白名单放行、SSE query 兼容），
  > 并基于 Redis 令牌桶实现全局限流（2000 QPS + 4000 突发，按 IP 键解析）；压测验证限流精度
  > （300 并发请求 200 放行/100 拒绝）与链路成本（吞吐损失 <4%，P99 无退化）。

### ⑩ 评论区两级模型完善（2026-10-24 实测完成，git 未提交）
- **修复真 bug**：原组树逻辑只挂一级——**回复的回复会静默丢失**（数据入库、计数+1，查询永远查不出）
- **拍扁归一**（微信朋友圈式）：`parent_id` 永远存根评论 id，新增 `reply_to_user` 字段，
  展示"回复@某人"——N 级互动收敛进两级结构
- 发布评论补 `@Transactional`（三次写库原本无事务：父评论计数+1 / INSERT / 帖子计数+1）
- `forum_comment` 加 `idx_blog_id`（原来只有主键，查评论全表扫）
- 查询改**两段式加载**：主评论倒序 LIMIT 20 + 子评论批量 IN（双 JOIN 带出作者信息与被回复人昵称），
  替代"全量拉回内存组树"
- **实测**（热帖 5,000 条评论，共 13,056 条全表）：

| 指标 | 改造前 | 改造后 |
|---|---|---|
| 单次延迟 | 615ms | **21ms（-96%）** |
| 响应体积 | 858KB（全量 5,000 条） | **45KB**（20 主评论+145 子评论） |
| 并发 c=10 | **服务熔化**（60s 超时、进程崩溃） | QPS 266，零错误 |
| 并发 c=50 | — | QPS 300，零错误，P99 708ms |

- **面试讲法**：评论区采用邻接表+两级展示模型（微博/B站同款）；发现并修复"回复的回复静默丢失"
  缺陷——拍扁归一到根评论并以 reply_to_user 支撑"回复@某人"展示；查询由全量内存组树改为
  主评论分页+子评论批量装配的两段式加载；发布链路补事务保证三次写库一致性；
  热帖（5千评论）单次延迟 615ms→21ms（-96%），响应体积 858KB→45KB，并发场景从服务熔化到稳定支撑。


### ⑪ 艾宾浩斯间隔重复调度（真 SRS）（2026-10-24 实测完成，git 未提交）
- **原状名不副实**：只有"每天背N首"线性排期+一个统计图，`next_review_date` 字段从未被写入，
  同一首诗只排一次=没有间隔重复；另有三处断链/半成品（配诗查询结果被丢弃建空书、
  start() 空方法、userlearningschedule 表 0 行未用）
- **改造**：
  - 复习动作（答题答对）一条 SQL 同时推进 `reviewCount+1` 与
    `next_review_date = CASE 间隔[3,7,14,30]天 ELSE NULL毕业`（CASE 前置于+1，规避 SET 顺序求值坑）
  - 新增"今日应复习"接口：`nextReviewDate<=NOW()` 走复合索引 `(book_id,nextReviewDate)`
  - 排期批量化：窗口函数 ROW_NUMBER 分组，一条 SQL 替代 N 次循环 UPDATE
  - 修三处存量 bug：①配诗断链（keys 丢弃→批量入库+book_id 自增回填）②复习 UPDATE 的
    `book_id=(子查询)` 在多诗集用户下多行报错（=改 IN）③`/query/end` 是 private handler，
    所在 Controller 因 @AutoLog 被 CGLIB 代理→代理实例字段全 null→NPE（改 public）
- **验证**：5 轮复习间隔 3/7/14/30/毕业全通过；毕业诗自动移出今日列表；
  学习当天进入今日任务、复习后 +3 天
- **实测**：156 首排期 旧循环 195ms → 一条 SQL 3ms（**65x**）
- **话术**：
  > 背诵模块实现艾宾浩斯间隔重复调度：复习完成原子推进轮次与下次复习时间（1/3/7/14/30 天间隔，
  > CASE 前置规避 MySQL SET 顺序求值），"今日应复习"查询走复合索引；排期由 N 次循环 UPDATE
  > 改造为窗口函数单条 SQL（156 首 195ms→3ms，65 倍）；修复按学历配诗断链、多诗集用户
  > 复习失效、CGLIB 代理下 private handler NPE 三个存量缺陷。


### ⑫ 缓存三防护：穿透/击穿/雪崩（2026-10-24 实测完成，git 未提交）
- **穿透**：诗详情空值缓存——不存在的 id 缓存 `"NULL"` 占位（2min 短 TTL），命中占位直接返回
  实测：恶意 id 连打 50 次，DB 查询 50→**2 次**
- **击穿**：三个聚合缓存（总数/朝代/聚合）升级为**逻辑过期+互斥重建**（复用诗详情已有模式：
  过期后抢 setIfAbsent 锁者异步重建、期间返回旧值；缓存缺失时抢锁者同步回源、其余 sleep 50ms 重读）
  实测：DEL 缓存后 50 并发，DB 回源 50→**2 次**
- **雪崩**：①逻辑过期 TTL 随机抖动（10±3min），且逻辑过期模式下 key 无物理 TTL 永不同时到期
  ②**Redis 宕机降级**：全部缓存点 try-catch，Redis 异常直接回源 DB；配合 Lettuce
  `timeout/connect-timeout: 500ms`（默认 60s 会把降级拖成灾难——这层最容易被忽略）
  实测：停 Redis 后 6 类查询接口**全部 200（改造前 500/超时）**，c=20 成功率 400/400、QPS 40
  （受 500ms 失败超时上限）；Redis 恢复后缓存自动重建，QPS 回 776
- **话术**：
  > 缓存三防护落地：空值缓存防穿透（恶意请求 DB 命中 50→2）、逻辑过期+互斥锁防击穿
  > （冷缓存 50 并发回源 50→2）、TTL 抖动+全链路降级防雪崩（Redis 宕机查询可用性 0→100%，
  > 400/400 成功），并将 Lettuce 命令超时 60s→500ms 让降级快速触发；Redis 恢复后缓存自愈。
- 已知限制：Redisson 启动期强依赖 Redis（宕机时服务不能重启，运行中可降级）——面试可作延伸讨论点


### ⑬ 后台管理权限治理（2026-10-24 实测完成，git 未提交）
- **改造前实测漏洞**（现场复现）：`/admin/**`、`/notice/**` **完全无鉴权**——
  无 token 返回全部 70 用户资料；**普通用户 token 可成功执行封禁操作**（垂直越权）；
  管理端登录发的 token 无任何拦截器验证（"门禁卡发了,门上没装读卡器"）
- **改造**：
  - 新增 `JwtTokenAdminInterceptor`（adminSecretKey 验签），注册 `/admin/**`+`/notice/**`，
    放行登录/验证码；与管理端登录签发的专用 token 呼应
  - 网关 `AuthGlobalFilter` 升级**双密钥角色隔离**：按路径前缀选密钥
    （/admin /notice 用 admin 密钥，/user /ai 用 user 密钥），普通用户 token 在 admin 路径必然验签失败
  - 验证脚本 `docs/bench/admin_flow_test.py`（含从 Redis 读 JDK 序列化验证码的辅助）
- **实测矩阵（7 项全绿）**：无 token 401（直连/网关）；用户 token 冒充 admin 401（角色隔离）；
  admin 正向流程（验证码→登录→getAll→disable→经网关）全部 200；用户端接口回归无影响
- **话术**：
  > 发现并修复后台管理系统越权漏洞（管理端 17 个接口完全未鉴权、普通用户 token 可封禁任意账号）：
  > 实现管理端 JWT 拦截器与网关双密钥角色隔离（按路径前缀选择验签密钥，用户/管理员 token 物理隔离），
  > 完整鉴权矩阵 7 项实测通过，正向流程与越权拦截双向验证。
- 待办（backlog）：admin 密码 MD5→BCrypt 迁移、JWT 密钥环境变量化、admin CRUD 补 @AutoLog


### ⑭ ORDER BY RAND() 清零（2026-10-25 实测完成）
- **背景**：②只改造了随机诗/推荐诗两处热路径，全项目仍遗留 5 处活路由 RAND（含万行表×3）+2 处死代码。
  最重的"随机诗人分页"是 writer×potry JOIN + DISTINCT + 全量 filesort（无界排序），
  名句墙随机接口是 10,001 行 rhesis 表 filesort，且前端一次访问要调 6+ 次。
- **改造**：
  - 抽象**通用随机 id 池组件 RandomIdPool**（SRANDMEMBER 抽样 + 主键 IN 回表 + 池 1h TTL 自愈
    + Redis 异常自动降级回原查询），potry/rhesis/writer/论坛帖 4 个业务复用一套实现
  - 5 处活路由接入：名句随机10（rhesis 10,001 行）、今日名句（rhesis）、随机诗人分页（poetry/Get）、
    随机诗（writer/GetRandomPoems 复用 potry 池）、随机帖（论坛，表随发帖增长）
  - 顺带修复**语义缺陷**：名句分页接口原为 PageHelper+RAND——每次调用整表重洗、翻页顺序无意义；
    改为随机 N 条 + 真实 total。随机诗人分页 total 由"诗人×朝代组合数 156"修正为真实诗人数 153，
    消除跨朝代重复行
  - 删除 2 处死代码 RAND（路由已注释的 GetRondWriter、无调用方的 GetwriterBydynasty1）
- **实测**（bench_rand.py，直连 8081，单次=30 采样中位；并发=15s/档）：

| 接口 | 单次延迟 前→后 | 并发 c=50 QPS 前→后 | P99 前→后 |
|---|---|---|---|
| 随机诗人分页（JOIN+filesort 最重） | **37.1→6.0ms（-84%）** | **133→932（7.0x）** | **1310→118ms（-91%）** |
| 名句随机10（rhesis 万行） | 9.0→5.4ms（-40%） | 699→971（+39%） | 149→113ms |
| 今日名句（rhesis） | 9.0→4.5ms（-50%） | — | — |
| 随机诗10（potry 万行） | 7.1→5.0ms（-30%） | 917→1085（+18%） | 116→99ms |
| 随机诗人5（153 行小表） | 5.0→4.0ms | — | — |
| 随机帖5（19 行小表） | 5.0→5.0ms（持平，见诚实注解） | — | — |

  - 随机诗人分页 c=10：QPS 116→991（8.5x）、P99 118→21ms
  - **降级实测**：kill Redis 后 4 类随机接口全部 200（自动回退 RAND），Redis 恢复后池自动重建
- **诚实注解**：19/153 行小表走池收益为 0（filesort 本身 <0.5ms，池价值在表随业务增长后的可扩展性
  与四业务统一模式）；热路径 ORDER BY RAND() 清零指正常路径，6 处 RAND 查询保留为 Redis 故障降级路径
- **话术**：
  > 将项目遗留的 5 处 ORDER BY RAND() 全表 filesort 查询（含 3 处万行表、1 处 JOIN 无界排序）
  > 统一改造为通用 Redis 随机 id 池组件（SRANDMEMBER 抽样+主键 IN 回表、1h TTL 自愈、
  > Redis 故障自动降级并实测验证），4 个业务复用一套实现；最重的随机诗人分页接口单次延迟
  > 37ms→6ms（-84%）、并发 QPS 133→932（7 倍）、P99 1310ms→118ms（-91%），名句墙 QPS +39%；
  > 顺带修复"RAND+分页每次重洗页序"的语义缺陷，删除 2 处死代码，热路径 ORDER BY RAND() 清零。


### ⑮ 中文搜索 FULLTEXT ngram 改造（2026-10-25 实测完成）
- **背景**：两条用户搜索链路均为前置模糊 `LIKE '%x%'`（索引必然失效，EXPLAIN type=ALL 扫 10,019 行）：
  ①诗词搜索 `GET /user/poetry/GetPoembyTitle`（title OR writer 双 LIKE + PageHelper COUNT，前端列表页在用）
  ②论坛搜古诗 `GET /user/luntan/search`（title OR content 双 LIKE + case-when 标题优先排序，"江南"一次回 187 行/152KB）。
- **改造**：
  - potry 表加 3 个 ngram 全文索引：`ft_ti_wr(title,writer)`、`ft_ti_ct(title,content)`、`ft_title(title)`
    （第三个供 ORDER BY 中 MATCH(title) 单列求值；建索引耗时 2s，ngram_token_size=2 默认值）
  - 查询改 `MATCH(...) AGAINST('"kw"' IN BOOLEAN MODE)` **短语匹配**——双引号包裹 bigram 序列，
    语义上精确等价 LIKE 子串（比裸 BOOLEAN 的 AND 语义更贴近原行为），且天然免疫操作符注入
    （服务层剥离用户输入中的双引号，实测 `黄鹤"楼` → 正常返回 6 条=黄鹤楼）
  - **混合路由**：≥2 字关键词走全文索引，单字（低于 ngram_token_size 无法切词）自动回退 LIKE——
    实测单字"春"（476 命中）延迟与改造前持平，证明回退路径生效
- **结果等价性**（DB 层直查核对）：黄鹤楼 6/6、杜甫 100/100、月光 27/27、江南 187/187、春江 19/19，
  LIKE 与短语全文命中数完全一致；EXPLAIN 由 type=ALL 全表扫 → type=fulltext 索引命中
- **实测**（bench_search.py，直连 8081，单次=30 采样中位；并发=15s/档）：

| 场景 | 单次延迟 前→后 | 并发 c=50 QPS 前→后 | P99 前→后 |
|---|---|---|---|
| 诗词搜索 黄鹤楼 | 16.1→6.0ms（**-63%**） | 342→926（**2.7x**） | 529→127ms（**-76%**） |
| 诗词搜索 静夜思 | 15.6→5.0ms（-68%） | — | — |
| 诗词搜索 杜甫 | 10.1→7.0ms（-31%） | — | — |
| 论坛搜索 月光 | 16.7→4.8ms（-71%） | — | — |
| 论坛搜索 江南 | 22.5→8.4ms（-63%） | — | — |
| 单字 春（LIKE 回退） | 10.0→10.7ms（持平，符合预期） | — | — |

  - 诗词搜索 c=10：QPS 275→730（2.7x）、P99 64→30ms
- **话术**：
  > 中文搜索由前置模糊 LIKE（索引失效、全表扫描 10,019 行）改造为 MySQL FULLTEXT ngram 全文索引
  > + BOOLEAN MODE 短语匹配（双引号包裹 bigram 序列，语义与子串匹配精确等价并免疫操作符注入；
  > 单字词低于 ngram 切词阈值自动回退 LIKE），5 组关键词命中数与 LIKE 完全一致；
  > 搜索接口单次延迟 -31%~-71%，并发 QPS 342→926（2.7 倍）、P99 529→127ms（-76%）。


### ⑯ 点赞幂等 + 双存储一致性（2026-10-25 实测完成）
- **改造前实测缺陷**（复现脚本 bench_like.py，帖 46）：
  1. **连点竞态超发**：原实现"先 ZSCORE 查重再 ZADD"两步非原子——同用户 10 线程 barrier 并发首点，
     **10 个请求全部返回"点赞成功"、计数 +10**（应 ≤1）；Redis 里只留 1 条记录，之后取消只 -1，
     计数永久虚高 9
  2. **判重状态单点存 Redis**：MySQL 只有计数列无明细。实测点赞后 DEL 掉 Redis key（模拟重启丢数据，
     本机真实发生过），同用户再点 → 计数又 +1，**同用户可无限刷赞**
  3. 点赞链路对 Redis 故障零容错（无 try-catch，Redis 停 → 接口 500）
- **改造**（帖子/评论点赞同构，共用一个 toggleLike）：
  1. **原子占位**：废弃 ZSCORE+ZADD 两步，直接用 ZADD 返回值判断（单命令在 Redis 内串行执行），
     并发首点只有一个线程拿到"赞"方向
  2. **事实源换到 MySQL**：新建 `blog_like`/`comment_like` 明细表（复合主键 user+目标，
     INSERT IGNORE 天然幂等），**计数列只在明细真正增删（affected>0）时同步更新**——Redis 丢数据
     时 affected=0 自动拦截重复计数，无需重建任务，惰性自愈；DB 事务回滚场景同样自愈
     （Redis 占位残留 → 下次取消 DELETE affected=0 → 不扣计数）
  3. **编程式事务 + 死锁重试**：TransactionTemplate 把"明细+计数"两写包成原子事务；同 user
     并发 toggle 下 InnoDB 明细行锁与计数行锁会成环死锁（实测 500），victim 回滚后自动重试
     （线性退避，重试体因 INSERT IGNORE/affected 判断天然幂等）；**宁可 500 拒绝绝不超发**（fail-safe）
  4. **Redis 宕机降级**：Redis 异常时直接走 DB 明细判重（同样幂等），点赞可用性 0→100%
  5. 计数 UPDATE 加 `AND liked>0` 下限保护，防历史脏数据减穿
- **实测**（after 同脚本同场景）：

| 场景 | 改造前 | 改造后 |
|---|---|---|
| 同用户并发首点 10 线程 | +10（全"点赞成功"，超发） | **增量 ∈ {-1,0}，零超发** |
| 删 Redis 后同用户再点 | 计数 +1（重复赞） | **计数不变（DB 明细拦截）** |
| Redis 宕机时点赞 | 500 | **200 正常返回（DB 判重降级）** |
| toggle 写路径 QPS c=10 | 430 | **859（+100%）** |
| toggle 写路径 QPS c=50 | 465 | **1005（+116%）**，P99 375→114ms |
| 计数 vs 明细对账 | 无明细可对 | **liked == 明细行数（验证通过）** |
| 20 并发×20 次（400 请求） | — | **零错误**；50 并发持续风暴下 0.06% 500（重试穷尽后拒绝，不超发） |

- **诚实注解**：QPS 翻倍主要来自消除了 ZSCORE 网络往返与事务化（并非幂等本身的"收益"）；
  存量历史 liked（Redis 判重已丢的 3 个帖子的旧计数）与明细差 1~3，属不可考历史数据，未强改
- **话术**：
  > 论坛点赞链路存在连点超发（同用户并发首点 10 请求全部成功、计数 +10）与判重单点依赖 Redis
  > （重启丢数据后可无限刷赞）两类缺陷。改造为：Redis ZADD 原子占位挡并发 + MySQL 复合主键明细表
  > 作幂等事实源（INSERT IGNORE + affected 判断，计数列仅在明细真实增删时更新，Redis 丢数据时
  > 惰性自愈）+ TransactionTemplate 事务包裹并处理 InnoDB 并发死锁（victim 回滚自动重试，
  > 宁拒绝不超发）+ Redis 宕机降级 DB 判重（点赞可用性 0→100%）；实测并发首点零超发、
  > 计数与明细严格对账一致，写路径吞吐翻倍（465→1005 QPS）。


### ⑰ MQ 可靠消息闭环（2026-10-25 实测完成）
- **改造前故障演练**（发帖通知链路 post.exchange→post.notify.queue，三个故障全部实锤）：
  1. **毒消息无限循环**：往队列投一条字段类型非法的消息，消费者异常→默认 requeue→再消费→
     **15 秒打出 408,723 行日志（每秒 2.7 万行）**，CPU/磁盘被打爆，只能停服务才能止血
  2. **broker 宕机发帖 500 但帖子已入库**：afterCommit 里 convertAndSend 抛连接异常直接
     传播——事务已提交、帖子已落库，用户看到 500 以为失败重发 → 重复发帖 + 该帖通知永久丢失
  3. **重复消费无幂等**：同一帖子消息投递两次，消费两次（粉丝收件箱/STOMP 双重触达）
- **改造**（四件套）：
  1. **消费重试+死信**：容器 defaultRequeueRejected=false + 本地无状态重试 3 次（1s/2s/4s 退避），
     耗尽后 basic.reject → 队列声明的 x-dead-letter-exchange(post.dlx) → post.notify.dead.queue，
     死信消费者 error 日志 + Redis 计数（mq:dead:count）供告警
  2. **消费幂等**：处理前 setIfAbsent(`post:notified:{bolgid}`, 24h TTL)，重复消息直接 ack 跳过；
     Redis 异常放行（重复触达无害，通知优先送达）
  3. **生产者投递失败补偿**：afterCommit 投递 try-catch——失败不再让接口 500（消除"接口失败
     但帖子已入库"的不一致），消息落 Redis 补偿队列（lpush/rpop=FIFO），@Scheduled 每 20s
     重投，broker 恢复后自动清空；消费端幂等键保证重投不重复触达
  4. **publisher confirm/return**：RabbitTemplate mandatory + ConfirmCallback（NACK 告警）
     + ReturnsCallback（未路由到队列告警）
- **实测**（after 同场景演练）：

| 故障场景 | 改造前 | 改造后 |
|---|---|---|
| 毒消息（非法字段） | 15s 408,723 行日志无限循环 | **重试 3 次后进死信，日志 138 行（-99.97%），死信计数+1** |
| broker 宕机时发帖 | **500**，但帖子已入库（不一致） | **200 发布成功**，消息进补偿队列，broker 恢复后 45s 内自动重投并消费 |
| 同一消息投递两次 | 消费两次（双重触达） | 第一次消费、第二次"幂等跳过" |
| 正常链路回归 | — | 发帖 RT 17ms → 同 traceId 消费完成（traceId 贯穿⑥） |

- **诚实注解**：补偿队列本身存 Redis（Redis+Rabbit 同时挂则消息丢失，完整方案是本地消息表/事务消息，
  当前是轻量补偿）；confirm NACK 未自动重投（仅告警日志）
- **话术**：
  > 论坛发帖通知链路补全 MQ 可靠性四件套：消费端本地重试（3 次指数退避）+ 死信队列
  > （毒消息由默认 requeue 无限循环——实测 15 秒 40 万行日志——收敛为重试耗尽进死信并告警计数）、
  > 消费幂等（Redis setIfAbsent 业务幂等键，重复投递 ack 跳过）、生产者投递失败补偿
  > （broker 宕机时发帖接口由 500+数据不一致 变为 200+Redis 补偿队列定时重投，恢复后自动送达）、
  > publisher confirm/return 告警；四类故障场景 before/after 演练全部收敛，正常链路 traceId
  > 全程贯通。


### ⑱ 安全收口：BCrypt 平滑迁移 + JWT 密钥轮换 + 验证码存储治理（2026-10-25 实测完成）
- **改造前实测缺陷**：
  1. admin 密码裸 MD5 存储（`123456` → `e10adc3949...`，无盐彩虹表一查即破）
  2. JWT 密钥硬编码进 git（`admin-secret-key: publication-placeholder-jwt_admin_secret` / `userSecretKey: publication-placeholder-jwt_user_secret`），
     且换密钥=所有在线 token 立即失效，无轮换手段
  3. 登录图片验证码经 RedisUtil 的 JDK 序列化 RedisTemplate 存储且**无 TTL**——key 是 UUID
     随机名无法模式识别清理，永久泄漏；redis-cli 直接读不了（运维盲区）
  4. AdminController.adminLogin 把业务异常 catch(Exception) 吞成"系统错误"（前端报告的
     "账号不存在"提示混乱问题）
- **改造**：
  1. **BCrypt 零停机平滑迁移**：登录时识别存量格式——`$2` 前缀走 BCrypt 校验；MD5 校验
     通过后**立即原位 UPDATE 为 BCrypt 哈希**（存量账号在下次成功登录时逐个切换，无需批量
     重置密码、不发公告不停服）；注册口一律 BCrypt。自带随机盐+自适应成本(强度10)，
     同一密码每次哈希不同
  2. **JWT 密钥环境变量化 + 平滑轮换**：`${JWT_ADMIN_SECRET:旧值}` 注入（旧值仅作本地默认）；
     新增 legacy 密钥列表（`JWT_*_LEGACY_KEYS`）——**轮换时换新主密钥重启，旧 token 验签
     回退 legacy 继续有效，TTL 自然过期后清空 legacy 完成轮换**；admin/user 各自独立 legacy
     列表保持双密钥角色隔离。服务端(JwtUtil.parseJWTWithLegacy+双拦截器)与网关
     (AuthGlobalFilter.verifyWithLegacy)同语义实现
  3. **验证码治理**：改 StringRedisTemplate + 5 分钟 TTL + 登录成功一次性删除；
     string 类型 redis-cli 可直接读（可调试性回归）
  4. adminLogin 分离 BaseException 分支——"账号不存在/密码错误/账号锁定"真实文案透出
- **实测**（行为验证）：

| 验证项 | 结果 |
|---|---|
| 存量 MD5 账号登录 | 成功，DB 密码**当场变 `$2a$10$` 前缀**（原位升级日志确认） |
| 升级后再次登录（BCrypt 路径） | 成功 |
| 错误密码 / 不存在账号 | 返回"密码错误"/"账号不存在"（原均为"系统错误"） |
| 验证码存储 | `TYPE=string`（原 JDK 序列化）、`TTL=300s`（原 -1 永不过期） |
| **密钥轮换演练** | 网关带 `JWT_USER_SECRET=新密钥` + `JWT_USER_LEGACY_KEYS=旧密钥` 重启：**旧 token 靠 legacy 验签 200，伪造 token 401**——轮换不停服且不降低安全性 |

- **话术**：
  > 管理端密码由裸 MD5 迁移 BCrypt：登录时识别存量格式、校验通过即原位升级哈希，实现
  > 零停机平滑迁移（无批量重置、用户无感）；JWT 密钥环境变量化并实现平滑轮换——换新主密钥
  > 重启后旧 token 经 legacy 密钥列表回退验签继续有效，TTL 过渡后清空 legacy，实测轮换全程
  > 在线用户零掉线、伪造 token 仍被拒；验证码存储由 JDK 序列化无 TTL 改为 String+5min TTL
  > 消除 key 泄漏并恢复 redis-cli 可读性；顺带修复业务异常被吞成"系统错误"的提示缺陷。


### ⑲ 搜索建议 + 热搜榜（2026-10-25 实测完成，新功能）
- **功能**：①`GET /user/poetry/suggest?kw=` 搜索自动补全（诗词标题+诗人名混合词库，前缀匹配 ≤8 条）；
  ②`GET /user/poetry/hotsearch` 24h 滚动热搜 Top10。
- **实现**：
  - 补全：全量标题(9,948 去重)+诗人名(153)装载单 ZSet（**score 恒 0 保证字典序**），
    `ZRANGEBYLEX [prefix, prefix+￿]` 范围取词 O(logN)；懒装载+24h TTL 自愈；
    Redis 故障降级 `LIKE 'kw%'` 前缀查询（**可走 idx_title 索引**，实测停 Redis 后补全照常）
  - 热搜：搜索主入口埋点 `ZINCRBY` 计数 + 24h 滚动过期（"滚动热搜"语义）+ top1000 裁剪防膨胀；
    **防刷**：同用户同词 60s setIfAbsent 去重（实测同词连搜 3 次只计 1 分）；
    全链路 try-catch，热搜故障不影响搜索主流程
- **实测**：'李白' 补全混合返回诗人名+《李白墓》等标题；Redis 宕机 suggest 降级 DB 正常返回、
  hotsearch 空列表 200；并发 c=50 QPS 642 零错误。
- **话术**：
  > 搜索体验补全：自动补全基于 Redis ZSet 字典序范围查询（score 恒 0 + ZRANGEBYLEX 前缀区间，
  O(logN)，词库懒装载/24h 自愈，Redis 故障降级走 B+树前缀索引）；热搜榜为 ZINCRBY 计数 +
  24h 滚动过期的实时榜单，同用户同词 60 秒去重防刷、top1000 裁剪防膨胀，埋点全链路容错不侵入主流程。


### ⑳ 复习提醒推送（2026-10-25 实测完成，新功能）
- **功能**：每日 9 点定时扫描艾宾浩斯 SRS 到期用户——在线用户经 STOMP `/topic/review.{userId}`
  实时推送"今天该复习 N 首"；配套红点接口 `GET /user/book/remindcount`（实时算到期数）、
  提醒历史 `GET /user/book/remindlog`（最近 7 天）；管理端 `POST /admin/remind/trigger` 手动触发。
- **实现要点**：
  - 到期扫描一条 JOIN+GROUP BY（复合索引 idx_book_next 范围扫），一次跑批拉全量到期用户
  - **双层防重**：批次级 SETNX 锁（多实例当日只跑一批，分布式语义）+ 用户级当日防重
    （定时+手动触发叠加时不重复打扰）
  - 提醒内容派生自 SRS 数据本身（红点/列表实时算），不做冗余存储——提醒历史仅存 7 条 ZSet
  - 推送异常逐用户 try-catch，单点失败不影响整批
- **实测**（test_review_remind.py 端到端）：造 3 首到期 → STOMP 订阅者实时收到
  `{"type":"review_remind","count":3,"date":"2026-10-25"}`；remindcount=3；二次触发推送 0 人
  （防重生效）；remindlog 返回当日记录。
- **话术**：
  > 为 SRS 背诵模块补全提醒闭环：定时任务扫描到期用户（索引范围扫一次拉全量），在线用户经
  > STOMP 用户级 topic 实时推送，离线侧红点与提醒中心由数据实时派生（零冗余存储）；批次级
  > 分布式锁 + 用户级当日防重的双层防重设计，管理端支持手动触发补偿；端到端实测订阅-触发-
  > 收推-防重-历史全链路通过。


### ⑦ AI 侧已有素材（potry-ai-agent，简历可双写 Java + AI）
- RAG：BGE-M3 1024 维向量 + Milvus 检索（topk5、相似度阈值 0.5）、知识库 33.6MB
- LangGraph 工作流 + MCP 工具调用 + 数据飞轮（三入口入池→查重→人工审核→回流知识库）
- 407 个 pytest 用例、验收脚本 evals/（真实 HTTP/SSE 实跑）
- **话术模板**：
  > 基于 LangGraph 构建"诗人伴学 Agent"：意图路由→RAG 检索（BGE-M3+Milvus，检索 P95 __ms）→
  > 工具调用（MCP 双 Server）→置信度门控；设计数据飞轮（低置信度/自评/用户负反馈三入口入池，
  > 人工审核回流知识库），坏例率由 __% 降至 __%。

---

## 三、工具清单（全部免费，按优先级）

| 工具 | 用途 | 获取 |
|---|---|---|
| **JMeter** | 压测 QPS/P95/P99（简历关键词，面试官认） | jmeter.org 解压即用，需 JDK |
| **Arthas** | 方法级耗时 trace/监控，诊断谈资极佳 | `curl -O arthas.jar`，java -jar 启动 |
| **EXPLAIN / 慢查询日志** | SQL 优化证据 | MySQL 自带；`SET GLOBAL slow_query_log=1; long_query_time=0.1` |
| **redis-cli** | 命中率 INFO stats / bigkeys / slowlog | `redis-cli INFO stats` |
| **Prometheus + Grafana** | 监控大盘 + 压测截图素材 | Docker（等重启后 WSL 生效） |
| **hey / wrk**（可选） | 轻量快速压测，比 JMeter 快 | hey.exe 单文件 |

压测统一口径建议：并发 50/100/200 三档 × 持续 60s，记录 QPS、P50/P95/P99、错误率；
每组测 3 次取中位数（数据才稳）。压测脚本与结果存 `docs/bench/`，面试可展示。

---

## 四、执行排期（每步 1~2 小时，可拆开做）

1. **起服务基线**（Redis + Nacos + potry-service，JMeter 压 3 个热点接口，记录基线）
2. **索引优化** → 复压对比 → 话术①
3. **Redis 缓存** → 复压对比 + 命中率 → 话术②
4. **RabbitMQ RT 对比** → 话术③（半天可与 2/3 同日做）
5. **重启电脑后**：Docker 起 Prometheus+Grafana+RabbitMQ 管理台 → 监控截图 + 连接池调优剧情 → 话术⑥
6. **AI 侧补测**：RAG 检索 P95、SSE 首字延迟、（Langfuse 部署后）token 成本 → 话术④⑦

> 基线数据永远先测后改——**先记录、再优化**，否则"提高了多少"就没有依据。

### ㉑ MySQL ↔ Milvus 向量库一致性闭环（2026-10-25 实测完成）
- **问题**（用户提出）：导入诗词到 MySQL 后，向量库数据不一致——RAG 永远检索不到新数据，
  唯一手段是停服全量重建。**对账首次运行即实锤存量债**：向量库残留 830 首已删诗词的孤儿向量
  （covered 10778 > potry 9948）+ **11607 块从未嵌入的 pending**。
- **方案三层**：
  1. **导入即同步**：管理端 add 诗词成功后异步通知 agent `POST /api/admin/kb/sync?title=`
     （秒级单诗路径：切分→嵌入→写 Milvus→标记，实测 1 块 159ms；通知失败不阻塞导入仅告警）
  2. **对账可见**：`GET /api/admin/kb/syncstats` 实时对比 potry_total/poem_covered/uncovered/
     pending/embedded + consistent 布尔——不一致水位一眼可见
  3. **全量兜底**：无参 sync 后台线程清孤儿（Milvus delete by pk + chunks 删除）+ 全量补嵌
     （11607 块按 1.1 块/秒约 3 小时后台还债，pending 保持可中断重跑）；停服 build_kb.py 仍是终极手段
- **技术要点**：同步在 agent **进程内**复用全局 Milvus 连接（绕开 Milvus Lite 进程独占文件锁，
  这是在线增量的前提）；孤儿清理是双向一致的关键（源库删除后旧向量仍会被检索命中）；
  嵌入失败保持 pending 的幂等设计天然支持断点续跑
- **实测**：导诗 0.24s 返回（异步不阻塞）→ 自动同步落 Milvus（embedded 状态+mark 机制证据链）→
  对账 covered 9950==total、uncovered=0；孤儿清理 830 首一次性归位（10778→9948）
- **话术**：
  > 建立 MySQL 与 Milvus 向量库的数据一致性闭环：导入即同步（管理端导入后异步触发单诗秒级
  > 增量嵌入，不阻塞导入）、对账可见（覆盖数/pending/embedded 实时对账接口，首次运行即发现
  > 830 首已删诗的孤儿向量与 1.1 万块未嵌入存量债）、全量兜底（后台清孤儿+断点续跑补嵌）；
  > 同步复用进程内 Milvus 连接绕开嵌入式数据库的进程锁，实现在线增量替代停服重建。
