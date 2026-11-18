# 技术报告:逐接口设计与方案剖析(详解版)

> 基于 2026-10-25 两轮 codebase-xray 探索(第二轮为方法级深挖:Controller→Service→Mapper→表 全链)。
> 所有 `文件:行号` 为当日工作区实证;标注【推测】处为未完全实证。
> 配套:`docs/ARCHITECTURE.md`(架构与风险总账)、`CLAUDE.md`(AI 会话上下文)、`dev-notes/interview-quickcard.md`。

## 二轮深挖新发现(执行摘要,均为本轮方法级考古新查出)

| # | 级别 | 发现 | 证据 |
|---|---|---|---|
| 1 | 🔴 | `/agent/workflow/resume` **完全无用户鉴权**(不调 resolve_user_id),知道 sessionId 即可确认/取消他人工单 | main.py:605 |
| 2 | 🔴 | **Vue 主聊天页未实现 `confirm_ticket`→resume 链路**(仅 static/chat.html 有):Vue 用户遇"建单确认"帧后无法续跑,该 thread 后续请求全部 409 卡死 | AiChat.vue 无 resume 调用;main.py:549-555 |
| 3 | 🔴 | `/admin/potry/delete` 前后端契约不符:前端发 query params+空 body,后端要求 @RequestBody → **实际调用必 400** | adminApi.ts:55 vs PotryController.java:83 |
| 4 | 🔴 | `/admin/login/code` **把验证码原样放响应体返回**,且无图片验证码/限流前置 | AdminController.java:154-160 |
| 5 | 🔴 | `/agent/feedback/negative`、`/agent/correction` 无验签;`/agent/chat` 验签结果被丢弃(不落归属) | main.py:642,688,362 |
| 6 | 🟡 | `login` 里 `System.out.println(password)` 明文打印密码进日志 | UserController.java:71 |
| 7 | 🟡 | `/user/forget` GET+@RequestBody 组合,axios GET 不发 body → **接口实际不可用** | UserController.java:155-159 |
| 8 | 🟡 | 关注流接口 `select/guanzhu` 判空条件写反(`if (typedTuples != null) return "压根没有关注任何人"`)→ **该功能实际永远返回这句话** | PoemLunTanServiceimpl.java:308 |
| 9 | 🟡 | "AI 出题"功能已残缺:出题本体 `query` 是死接口,线上只有 `query/end` 被调用且**恒传 kk=1**(只推进、不判题);AI 答案写 Redis `woko:{id}` 无任何消费者 | PoetryController.java:394-436 |
| 10 | 🟡 | `/admin/command/handle` 把 LLM 返回的 JSON **直接驱动删诗/改诗**,无确认白名单(死接口但危险设计) | CommandServiceimpl.java:34 |
| 11 | 🟡 | `getAllFeedBack`(读全站反馈)、`updatefeedback`(伪造官方回复)、`game/delete`(删他人成绩)管理功能全部挂在 `/user/**` 下,用户 token 即可调用 | FeedBackController、QuestionGameController |
| 12 | ⚪ | 死接口规模超预期:**约 150 个端点中前端活跃仅 ~40 个**,`/user/Comment` 全组、`/user/game` 全组、admin 半数为死接口 | 各域"前端"标注 |

---

# Part I 系统总览

| 维度 | 本项目 | 主流参照 | 一句话差异 |
|---|---|---|---|
| 后端 | Spring Boot 3.3.4 单体 + SC Gateway | 微服务全家桶 | 业务单体+网关+Python Agent 三进程,不引入重注册治理 |
| 鉴权 | 自研双 JWT(用户/管理密钥隔离),三端共享 | Spring Security / Sa-Token | 自研 ~100 行拦截器 + legacy 无缝轮换 |
| ORM | MyBatis 注解 SQL(≈170 处)+ 7 份 XML | MyBatis-Plus / JPA | 手写 SQL 换可控性 |
| 缓存 | Redis(逻辑过期+互斥+空值缓存+降级四件套) | Spring Cache / 多级缓存 | 手搓缓存模式,可逐讲 |
| 消息 | RabbitMQ + confirm/DLX/补偿重投 | RocketMQ 事务消息 / Outbox | 无事务消息引擎的手搓闭环 |
| 实时 | STOMP over WebSocket(2 topic) | Socket.IO / SSE | 标准子协议,简单 broker 单机 |
| AI 编排 | LangGraph 12 节点显式状态图 | Dify/Coze、纯 FC | 代码级编排,423 测试护城河 |
| 向量 | Milvus Lite + BGE-M3 onnx(51ms/条) | pgvector / 托管 Milvus | 零成本全本地,文件锁换单进程 |
| 可观测 | Prometheus 直方图 + TraceId MDC + Langfuse | OTel / SkyWalking | 按需拼装 |

**接口总账**:Java 后端 20 Controller ≈ **130 端点**(旧 AI 孤岛 11 文件已删不计)、Agent **18 端点**、网关 6 路由 3 过滤器、WS 2 topic、MQ 1 拓扑+死信、定时 2。前端 Vue 活跃调用约 40 端点,死接口 ≈70(两代前端迭代遗留)。

**通用调用范式**:前端 → 网关(AuthGlobalFilter 按前缀选密钥验 JWT,透传 X-User-Id)→ Controller(JwtToken*Interceptor 第二道)→ Service → Mapper(MyBatis)→ MySQL `poem` 库;用户身份经 ThreadLocal `BaseContext`(claims: userId、dgarreId 学历)贯穿。统一返回 `Result{code,data,msg}` / 分页 `PageResult{total,list}`(但实际存在 PageInfo/裸 List 三种风格并存)。

---

# Part II 逐接口手册

> 条目格式:`### 方法 路径 — 一句话` 下接 参数/调用链(→表)/机制/位置/注意/前端调用方。
> 标注:🔴高危 🟡注意 ⚪死接口(前端零调用,但后端路由仍活)。机制列只写有信息量的点。

## 2.1 认证、账号与公告域

### 域级思路
登录三通道(密码/图片验证码/邮箱验证码)+ JWT 签发;身份 claims={userId, dgarreId(学历 1-4)};验证码统一 Redis 一次性消费。邮箱验证码用独立线程池异步发(不拖登录 RT);管理员存量密码 MD5 → 登录时原位升级 BCrypt(平滑迁移的加分点)。

### 对比主流
主流是 Spring Security 表单登录 + Session/JWT,或 Sa-Token 注解。本域差异:①自研无过滤器链;②验证码自研(Redis 一次性消费,图形码 hutool LineCaptcha);③无 OAuth2/第三方登录;④管理端与用户端完全独立的两套登录(密钥隔离)而非 RBAC。

### 优缺点
优点:全链路可手讲;邮箱验证码 60s 限流+10min TTL+一次性消费是规范做法;MD5→BCrypt 原位升级思路成熟。缺点:无 refresh token;🟡`login` 明文打印密码(UserController.java:71);🟡`forget` GET+body 不可用;🔴`/admin/login/code` 回显验证码;⚪邮箱登录/注册通道是死接口(前端只用密码+图形码两条)。

---

### POST /user/login — 账号密码登录
- 参数: body `UserLoginDto{username,password}`
- 调用链: login→UserServiceimpl.login1:68→UserMapper.loginbyusername1→**poem.user**(BCrypt.matches;status==0 抛锁定)
- 机制: JWT claims={userId, dgarreId 学历文本映射};TTL 取 sky.jwt.userTtl
- 位置: UserController.java:62-103 | 🟡:71 打印密码;:94 登录日志打的是 ThreadLocal 残留值非本人
- 前端: Login.vue

### POST /user/login/code — 发邮箱验证码 ⚪
- 参数: query `phone`(实为邮箱,形参名误导)
- 调用链: →Redis `login:code:{email}`(6 位码,10min TTL)+ `login:code:limit:{email}` 60s 限流;mailThreadPool 异步发信
- 位置: UserController.java:105-109 | 🟡无图形验证码防护(可被刷邮件)
- 前端: 无(user.ts sendCode 死代码)

### POST /user/login/email — 邮箱验证码登录(自动注册)⚪
- 参数: body `{email,code}`
- 调用链: Redis 校验后**立即 delete 一次性消费**;查无此人→findByEmail→adduser 建号(默认学历/头像/随机昵称"不吃香菜(哈基米版#xxxxxx)")→签发 token→回查 **poem.user** 构造 UserVo
- 位置: UserController.java:111-129 | 🟡注册与回查两次查库无事务,理论竞态
- 前端: 无(死接口)

### POST /user/register — 用户名密码注册
- 参数: body `UserDto{username,password,…}`
- 调用链: 查重 **poem.user**→adduser:95 BCrypt→INSERT
- 位置: UserController.java:133-153 | 🟡username 重复抛 AccountNotFoundException(异常语义错位);注释称"注册赋予 AI 角色"但无此逻辑
- 前端: Login.vue

### GET /user/forget — 邮箱验证码重置密码 🔴不可用
- 参数: body `{email,code,password}`(**GET 带 body**)
- 调用链: Redis 校验并一次性消费→新旧同密拒绝→BCrypt→UPDATE **poem.user**
- 位置: UserController.java:155-159 | 🔴axios GET 不发 body,接口实际不可用(死接口)
- 前端: 无

### GET/PUT /user/getmassagebyid、/user/updatemessagebyid — 资料读改
- 调用链: GET `SELECT * FROM poem.user WHERE id=#{id}`;PUT 动态 UPDATE;🟡PUT 里头像字段若传 URL 文本会被按字节当 jpg 传 OSS 覆写
- 位置: UserController.java:163-176 | 前端: UserCenter.vue(两个都活)

### 收藏(8 端点,UserController 内 /user/collect*)
- addpem POST:收诗,服务端强制覆写 userid,**先 count 查重再 INSERT poem.usercollectionpoem**(✓做对了)| 前端: PoemDetail/PoetryList
- deletepem DELETE / ids GET / (bare)GET /user/collect(联表 usercollectionpoem×potry 出详情):均以 JWT 身份查删 ✓ | 前端: 同上+UserCenter
- 🔴addrhesis/deleterhesis POST/DELETE:userid **取自请求体不覆写、不查重**→可替他人收藏/重复插(与 addpem 双标)| ⚪死接口
- 🔴rhesisids/{id} GET:path 传任意 userid 可遍历他人收藏(无属主校验)| ⚪死接口
- collectRhesis/{id} GET:联表 userlikerhesis×rhesis | 前端: UserCenter.vue(传自己 id)

### 诗集本与 SRS(10 端点,/user/book*)
- book/add POST:建空书(书名空校验)→INSERT **poem.userbook** | 前端: UserCenter.vue
- book/addpoem POST:入书(幂等:count 查重跳过)→INSERT **poem.userbookpoem**(reviewCount=0)+`userbook.sum+1`;🔴bookid 无属主校验,可往任何人的书塞诗 | 前端: PoemDetail.vue
- book/show、book/showpoem/{bookid} GET:书架/书内诗列表(showpoem XML 只 select title→前端要的 writer/content 全 null 🟡;bookid 无属主校验)| 前端: 多页活
- **book/start POST(query bookId,much=每日每组新学数)**:窗口函数 SQL 一次排期——userbookpoem 按 id 序每 much 首一组,learnDate=今天+组序号,重置 reviewCount/last/next(当天即进今日任务) | 前端: UserCenter.vue(bookStartReview)
- book/showplan/{bookid} GET:服务层 TreeMap 按日聚合出复习曲线(isReview/time 为服务层造的近似值 🟡)| 前端: UserCenter.vue
- book/today GET(query bookid):**今日到期队列**——联表 userbookpoem×potry,`nextReviewDate<=NOW()` 走 idx_book_next,Controller 补文案"第{n}轮·间隔1/3/7/14/30天" | 前端: UserCenter/ReviewToday
- book/remindcount GET:红点数(子查询圈本人书→count 到期)| 前端: AppNav.vue
- book/remindlog GET:Redis ZSet `remind:log:{uid}` 取最近 7 条(由 ReviewRemindTask 写入)| 前端: ReviewToday.vue
- book/statr POST:按学历自动配诗建书(遗留拼写版,⚪死接口)

### SRS 推进(挂载点,详见 §4.4)
- **GET /user/poetry/query/end?kk&poemid**:kk=1→`UPDATE poem.userbookpoem SET nextReviewDate = CASE reviewCount WHEN 0 THEN +3天 WHEN 1 THEN +7天 WHEN 2 THEN +14天 WHEN 3 THEN +30天 ELSE NULL END, reviewCount+1`(PotryMapper.java:80-88)——第 5 次复习后 nextReviewDate=NULL 毕业 | 🟡kk 语义:任何非 0 值都算"答对",无真实判题;前端恒传 kk=1 | 前端: UserCenter.vue reciteDone

### 管理员登录与用户治理(AdminController,8 端点)
- **POST /admin/login**:图形验证码(Redis 一次性消费)+BCrypt(存量 MD5 命中后原位升级)→JWT claims={adminId} | 前端: Console.vue
- **GET /admin/getCode**:hutool LineCaptcha 200×100→base64;Redis codeKey(UUID)5min | 前端: Console.vue
- POST /admin/register ⚪:🟡验证码校验后不删除(可重复注册);Redis null 直接 equals→NPE 吞成"注册失败"
- POST /admin/login/code ⚪:🔴**验证码明文放响应体返回**,无限流,安全形同虚设
- POST /admin/remind/trigger ⚪:手动触发背诵提醒跑批(force=true 跳批次锁,仍受用户级防重)→GetDueReviewUsers(联表圈到期用户 GROUP BY)→逐用户 STOMP `/topic/review.{uid}`+ZSet 日志 | 位置: ReviewRemindTask.java:47-86(运维/演示用)
- POST /admin/disable/{status}(query id):启停用户账号,@AutoLog 落 **poem.log** | 前端: ContentAdmin.vue(userDisable)
- GET /admin/getAll(PageHelper 分页)、/admin/getUserCount ⚪ | 前端: ContentAdmin.vue(userPage)

### 公告(NoticeController,/notice,管理端密钥)
- POST add(body NoticeDto)/POST update/POST delete(query ids 批量,🟡循环单条删无事务)/GET getList(分页)/GET get ⚪
- 前端: getList 与 add/update/delete 活(ContentAdmin.vue、Notice.vue)
- 🟡vite 代理陷阱:`/notice` 前缀与 Vue 路由冲突,新端点必须逐个登记代理(vite.config.ts:22-27)


## 2.2 内容检索域(诗词 / 名句 / 诗人)

### 域级思路
读多写少的经典内容库:检索全 MySQL(FULLTEXT ngram 复合索引 + like 回退)、分页 PageHelper、热点走 Redis——但这里的 Redis 用法是全项目的**缓存设计亮点**:`GetContentById` 一套"逻辑过期+互斥锁+空值缓存+宕机降级"四合一;`suggest` 用 ZSet 字典序前缀匹配做联想;随机推荐用 **Redis Set 随机 id 池替代 ORDER BY RAND()**(避免全表 filesort)。

### 对比主流
主流会加 ES(分词/拼音/纠错)或多级缓存(Caffeine+Redis)。本项目 like/FULLTEXT 在 1 万级语料下够用,FULLTEXT ngram 已经是"半个搜索引擎"。联想/热搜/随机三件套全是 Redis 原语活用,讲得出为什么不用 ES。

### 优缺点
优点:缓存四合一模式完整(可逐层讲击穿/穿透/雪崩对策);随机 id 池与热榜截断(top1000)是真实压过规模的写法。缺点:🟡同一 Controller 里新旧接口成堆(27 个端点 16 个是死接口,同功能多版本并存:GetPoemBydynasty/GetPoemsByDynasty、GetContentById/GetPoemContbyid **共用同一 Redis key 但 TTL 不同互相踩**);🟡全文检索单字回退 like 全表;🟡AI 出题(query)整条链死代码。

---

### PoetryController(/user/poetry,27 端点)

### GET suggest — 搜索联想
- 参数: kw → 调用链: ZSet `poetry:suggest:zset` rangeByLex [prefix,prefix+￿] limit 8;词库懒装载(全部标题+诗人名,24h);Redis 异常降级 DB like | PotryServiceImpl.java:601-643 | 前端: PoetryList.vue
### GET hotsearch — 热搜 Top10
- 纯 Redis ZSet `poetry:hotsearch`;写入在搜索时:同用户同词 60s setIfAbsent 去重→incrementScore→key 24h 滑动过期→removeRange 只留 top1000 | PotryServiceImpl.java:645-687 | 前端: PoetryList.vue
### GET GetPoembyTitle — 标题/诗人搜索(记热搜)
- ≥2 字走 FULLTEXT ngram 短语匹配(ft_ti_wr 复合索引),单字回退 like;PageHelper 分页 | PotryMapper.java:71-75 | 前端: PoetryList/PoemDetail
### GET GetContentById/{id} — 诗详情【缓存样板间】
- key `poem:context:{id}`:命中返回/逻辑过期抢锁异步重建/miss 回源 **poem.potry**/不存在写 "NULL" 空值缓存 2min 防穿透/Redis 宕机直查 DB(PotryServiceImpl.java:144-235)| 前端: PoemDetail.vue
### GET GetPoemPage / GetPoemsByDynasty / GetPoemByType / GetwriterBywriter 等 — 检索矩阵
- 全是 PageHelper + 单条件 SQL(potry 表);GetPoemPage 额外查 usercollectionpoem 内存标记 islike;GetPoemByType 是 type like 全表
- ⚪死接口:GetPoemBydynasty(小写变体)、GetPoemByDynasty/{dynasty}(无分页 like 全表)、GetPoemByWriter、GetAllPoemName(全量吐 title 无缓存)
### GET GetCount / GetAllDynasty — 统计与元数据
- cacheWithResilience("potry:count"/"potry:allDynasty"):逻辑过期+setIfAbsent 互斥+TTL 抖动(10±3min)+宕机降级 | 🟡GetCount 挂了 @Autozuru 切面——GET 计数带"补默认头像"隐秘写副作用(MorentouAspect.java:19)| 前端: PoetryList.vue
### GET GetDynastyandpoem ⚪ / GetTypeDotaVo ⚪ — 聚合类
- group_concat 聚合(🟡group_concat_max_len 默认 1024 会截断标题串)/ 全表拉 type 列内存去重
### GET GetPoemDateRondom / GetVeryGoodPoem — 随机【id 池模式】
- Redis Set `potry:idpool` SRANDMEMBER 抽 id→主键 IN 回表(替代 ORDER BY RAND());池空回源装载 1h,异常降级 `order by rand()`;GetVeryGoodPoem 额外过滤挽词/悼亡类标题(重抽≤4 轮)| PotryServiceImpl.java:268,508 | 前端: GetVeryGoodPoem 活(PoetryList.vue 每日推荐);GetPoemDateRondom 被 Writer 随机复用
### GET GetPoemContbyid / GetPoemWrier ⚪ — 旧版详情(双版本互踩)
- 🟡GetPoemContbyid 与 GetContentById 共用 key 但 TTL 不同(30min/1min)且加工顺序相反;锁 key 拼成 "lock:shop:"(复制粘贴痕迹);GetPoemWrier 用 Redisson bucket+递归自旋抢锁(无上限),detailIntro 按引号硬 split 极脆
### GET query?id= — AI 出题本体 ⚪【已残缺】
- Spring AI ChatClient(AiConfig.java:51 装配,xiaoai.plus OpenAI 兼容);system prompt 要求提取≥5 个生僻字按序排列→原文挖空成 `_` 返回 {question,options};InMemoryChatMemory 按用户留 10 轮
- 🟡AI 答案写 Redisson+StringRedisTemplate **双客户端同 key `woko:{id}`(2min)且全项目无消费者**;挖空不避标点;question 用 Arrays.toString(char[]) 带括号逗号怪格式 | 前端: 无(只有 query/end 活)
### GET query/end?kk&poemid — 背诵推进(唯一活的 AI 域端点)
- kk=1→UPDATE userbookpoem CASE reviewCount 0→+3d/1→+7d/2→+14d/3→+30d/ELSE NULL(毕业),reviewCount+1(PotryMapper.java:80-88)🟡kk 任何非 0 值都算对,无真实判题 | 前端: UserCenter.vue reciteDone(恒 kk=1)

### 用户名句(/user/rhesis,7 端点)——结构同诗词,薄封装
- GetCount(名句总数)、GetAllRhesisName ⚪(全量名句)、GetRhesisContentById/{id}、GetVeryGoodRhesis(随机今日名句)、GetRhesisByKey/{keyword}(关键词 like)、GetRhesisDateRondom(随机 10 条)、GetRhesisPage(分页;旧版曾整段注释后重写,RhesisController.java:64-75)| 前端: Rhesis.vue 用 Key/Random/Count/Page 四个 | 表 **poem.rhesis**(name=名句,fromm=出处)

### 用户诗人(/user/writer,13 端点)——前端主力迁移地(旧 /user/poetry 的诗人类接口全死在这)
- GetWriterCount / GetAllWriterNames / GetAllDynasties:计数与下拉 | 前端: Writers/PoetryList
- imageAndSimpleIntro(name)/ detailIntro(name):卡片与详情两粒度,按 name 精确查 **poem.writer** | 前端: Writers.vue
- GetWritersByDynasty(名单)/ GetWritersByDynastyFull(卡片全量):朝代两粒度 | 前端: Full 版活
- GetPoemsByWriter / GetWriterAndPoemsById(id 聚合诗人+诗):关联查询 **poem.potry** | 前端: 活
- GetRandomPoems / GetRandomWriters:复用 RandomIdPool(WRITER_POOL,抽 5 个 id 回表;WriterServiceImpl.java:97)| 前端: 活(Writers.vue)
- GetFamousLinesByWriterId / GetWritersByPage(PageInfo 风格,与全局 PageResult 不一 🟡):名句联动/分页 | 前端: Page 活


## 2.3 社区域(诗坛/评论)

### 域级思路
发帖→**事务提交后(afterCommit)发 MQ**→消费者幂等落粉丝收件箱(Redis ZSet `fan:{uid}` 推模式 feed)→STOMP 广播;点赞是**"Redis ZSet 原子占位 + DB 明细表 INSERT IGNORE 事实源 + 编程式事务 + 死锁重试 4 次"**的完整 toggle 实现。这两块是后端含金量最高的社区设计。

### 对比主流
feed 流:推模式(写扩散到粉丝收件箱)vs 拉模式(读时聚合)vs 混合——本项目纯推,粉丝量小成立,大 V 写放大是天花板。点赞幂等:主流做 (user,item) 唯一约束 + 计数异步汇总,本项目 ZSet+INSERT IGNORE+计数列同构。MQ 触达:事务消息/Outbox 的轻量替代(见 §4.2)。

### 优缺点
优点:dianzan 幂等闭环完整(明细表为事实源,重复点击只翻转);MQ 全链路 traceId 透传(header 带 traceId);消费端幂等键 `post:notified:{bolgid}` 24h。缺点:🔴**关注流接口判空写反,功能实际失效**(PLTS:308);🟡guanzhu 无自关注/重复校验(脏数据+fans 计数漂移);🟡MQ+Redis 全挂时消息丢失(注释自认);18 端点 7 个死接口。

---

### PoemLunTanController(/user/luntan,18 端点)

### POST fabutiezi — 发帖【MQ 链源头】
- body `PoemBlogDto{title,images,content,type,poemId,poemWord}` → INSERT **poem.poem_blog**(useGeneratedKeys 回填)→ afterCommit 发 JSON(带 traceId header)→ direct **post.exchange**/`post.created` → post.notify.queue(durable,DLX=post.dlx);投递失败→Redis list `mq:pending:post.notify`,20s 定时任务 rightPop 重投(broker 仍挂则推回队尾)| 消费者 PostNotifyListener:幂等 setIfAbsent `post:notified:{bolgid}`→粉丝收件箱 ZSet `fan:{fanId}`→缓存 `blog:{id}` 1h→STOMP /topic/newpost | PLTS:56-92 | 前端: Forum.vue:109、AiChat.vue:117(AI 生成诗话一键发帖)
### GET selecttiez — 分类帖子分页(type1 1-6 硬编码映射;🟡非法值直接 throw→500)| 前端: Forum.vue
### GET selectxiangxi — 帖详情+作者+我的点赞状态(ZSet 读)| 前端: Forum.vue
### GET dianzan — 帖点赞 toggle【幂等样板】
- ZADD `blog:like{blogid}` 原子占位→事务内 **poem.blog_like** INSERT IGNORE(复合主键,affected>0 才)**poem_blog.liked±1**;Redis 异常降级 DB 判重;InnoDB 死锁重试≤4 | PLTS:147-183 | 前端: Forum.vue
### GET commentdianzan — 评论点赞(同构复用)| 前端: Forum.vue
### GET dianzanrank ⚪ — 🟡ZSet 升序 range 取的是最早 5 人而非"前 5 名"
### GET guanzhu — 关注/取关(isFollow 由前端传,🟡无重复/自关注校验,fans±1 计数漂移风险)⚪
### GET isguanzhu ⚪ / select/user/{followid} ⚪ / select/blog/{followid} ⚪ — 关注关系与个人页(**poem.tb_follow**:user_Id 关注者/follow_user_id 被关注者)
### GET select/guanzhu — 关注流(推模式收件箱)🔴功能失效
- ZSet `fan:{uid}` reverseRangeByScore→IN 回查 **poem.poem_blog**;🟡🟡PLTS:308 `if (typedTuples != null) return "压根没有关注任何人"`——非 null(几乎恒真)即提前返回,后续解析全死代码 | ⚪前端已导出未调用
### POST fabacomment — 评论/回复(拍扁挂根评论;**forum_comment.conment+1**、poem_blog.conmments+1;🟡这条线没有敏感词过滤,旧 Comment 线反而有)| 前端: Forum.vue
### GET selectConmmets — 两级评论组树(主评论最新 20+子评论 IN 批量)| 前端: Forum.vue
### GET selectConmmets11 ⚪ / select/forum ⚪(内存 BLOG_POOL 随机 5 帖)/ updateImage ⚪(OSS 直传,无类型大小校验,注释自称"上传什么都可以")
### GET search — 内容搜索(复用诗词 FULLTEXT/LIKE 双路)| 前端: Forum.vue

### CommentController(/user/Comment,5 端点全死 ⚪——被 luntan 线取代的旧版)
- addcomment/reply:**userid 取自请求体→可冒充任何人发帖**(🔴越权,虽是死接口但路由活);reply 是唯一有 SensitiveWordFilte 敏感词过滤的写接口 | **poem.comment**
- thumb:无幂等可无限刷;mapper 方法名 deletethumb 实为踩+1(误导);service 死分支
- getcomment/getcommentxaingxi/{id}:递归子评论树(visitedIds 防环,N+1 查询)

### 管理端帖子治理(/admin/blog,4 端点)
- getAllBlog GET(分页 **poem.poem_blog**)| comments GET(🟡Controller 直调 Mapper 跳过 Service,分层破例自认)| deleteComment POST(🟡删评论不联动减帖计数,自认)| deleteBlog POST(🟡for 循环逐条删无事务)
- 前端: ContentAdmin.vue 四个全活(adminApi.ts:173-235)

## 2.4 反馈与游戏域

### 域级思路与对比
反馈是单表留言+管理员回复;游戏是答题排行榜(Redis ZSet+Hash,空则 MySQL GROUP BY 重建)。两者的问题模式一致:**管理动作与越权参数放在用户路径下**。

### 优缺点
优点:排行榜 rebuildIfEmpty(空则回源重建)与 Lua 更高分覆盖是标准做法。缺点:🔴下面列的越权三连;🟡feedback 表列名 `messsage`(三 s)拼写遗留;**整个游戏域 9 个端点前端零调用**(表 questionsgame 链路也是死的)。

### FeedBackController(/user/FeedBack,7 端点)
- POST addfeedback:body{userid,message}→**poem.feedback**;🟡写前把 DTO 塞 Redisson 全局单键 bucket "feedback"(每次覆盖,调试遗留);🟡userid 取自 body 可冒名 | 前端: Feedback.vue
- GET getAllFeedBack:🔴**任意用户可读全站反馈**(管理功能挂 /user/)| 前端: Feedback.vue:38(用户页里居然在用)
- GET getReply/{id} ⚪:🟡只返回第一条回复,多条丢失
- GET addfeedback/{id} ⚪(GET 挂在 addfeedback 路径下,URL 语义事故)/ GET Getpage ⚪
- DELETE deletefeedback/{id} ⚪:🔴无归属校验 IDOR(任何登录用户删任何反馈)
- PUT updatefeedback ⚪:🔴注释写"管理员回复"但路径在 /user/**,用户 token 可伪造官方回复(写 **poem.reply**)
### QuestionGameController(/user/game,9 端点全死 ⚪)
- GET questions:随机诗取首联下句为答案,**答案以 Redis key 名存放**(`question{答案}` 1min)→keys 枚举即泄露;`if(false)` 死分支(questionsgame 表整链死码);HttpSession 计时(无状态 JWT 架构下基本失效)
- GET check:🟡🟡判对逻辑形同虚设(key 存在时 daan==answer 恒等必"对");答错 daan=null→NPE→500(以 500 暴露);**sum 是 Controller 单例字段,全用户共享串分**
- GET score:🔴userId 由前端传→代刷他人成绩(INSERT **poem.gamerank**+ZSet `gamerank:zset` Lua 更高分)
- getLatest/getRank/(空则 MySQL 重建)/SelectPage(管理功能挂 /user/)/delete/{id}(🔴IDOR,且不清 ZSet 脏数据)/getAllRecord/{userid}
- 前端: 全组无调用(游戏入口未接线,半成品)

## 2.5 管理内容 CRUD 域(/admin/potry|rhesis|writer|log|command,约 25 端点)

### 域级思路与对比
模板化 CRUD:PageHelper 分页 + 动态 XML update + 批量删除。对比主流:一般会用 MBP 的 ServiceImpl 泛型 CRUD 或代码生成器;本项目手写但高度重复。特殊点:**add 诗词触发 Agent 知识库增量嵌入**(内容域与 AI 域的唯一联动点)。

### 优缺点
优点:统一 Result/PageResult、@AutoLog 切面自动记操作日志(**poem.log**)。缺点:🔴**delete 契约 bug(前端必 400)**;🟡批量删除全是 for+N+1;🟡多端点返回风格混用(PageInfo vs PageResult);🟡AICommand 的 LLM 直驱写库设计。

### /admin/potry(7 端点,前端用 3 个)
- **POST add**:先 title+dynasty+writer 三元组查重→INSERT **poem.potry**→**notifyKbSync**(:60-79):CompletableFuture.runAsync 异步,自签 60s admin JWT(claims{user_id:1},注释解释 jjwt 写 exp 须可变 Map)→HttpClient POST `http://localhost:8000/api/admin/kb/sync?title=...`(120s 超时),失败仅 warn 不阻塞,对账兜底 | 前端: ContentAdmin.vue poemAdd
- **POST delete** 🔴:body `List<Long> ids`,但前端 poemDelete 发 params(query)+null body(adminApi.ts:55)→**必 400**;且后端是 for 循环逐条删 | 前端: ContentAdmin.vue(现状:删除功能坏的)
- POST update(动态 XML 五字段)/ GET GetPoemPage(分页)| 前端: 活
- GET GetCount ⚪ / getPoem ⚪(五字段 OR 模糊)/ deletePoem ⚪(按 title 删,title 非唯一全删;**删诗不清 Milvus 向量** 🟡)

### /admin/rhesis(6 端点,前端用 4 个)
- GetAll(分页)/add(INSERT name,fromm)/update(动态 XML)/delete(🟡前端未加 paramsSerializer,axios 默认 `ids[]=` Spring 绑不上,疑似静默失败)
- 🟡类上 @Slf4j 误导 `groovy.util.logging.Slf4j`(Java 下无效,log 字段不存在)
- getRhesisByPoemName ⚪ / getCount ⚪ | 表 **poem.rhesis**

### /admin/writer(8 端点,前端用 4 个)
- GetWritersByPage(返回 PageInfo 风格 🟡)/add(🟡insert 无 useGeneratedKeys,声明返回恒 null)/update(全字段覆盖,DTO 缺列置 null)/delete(🟡N+1+TODO 自认未校验名下是否还有诗)
- updateImage ⚪:OSS 上传 lun/{UUID};🔴private 方法(反射仍可映射);无类型/大小校验
- {id}/getWriterByName/getCount ⚪ | 表 **poem.writer**

### /admin/log(2 端点 ⚪)+ /admin/command(2 端点 ⚪)
- log/get、log/delete:**poem.log**(数据源 @AutoLog 切面);🟡@RequestMapping 未限定方法;循环删无事务
- command/handle:🟡🟡LLM 返回 JSON **直接驱动** add/update/delete/count/search **poem.potry**,无确认白名单;API key 曾硬编码(后迁 secret 文件);prompt 要求"联网搜索补全诗"不可靠
- command/forum:取帖评论喂 LLM→结论 INSERT **poem.suggestion**(拿业务 id 当主键,重复分析必主键冲突)


## 2.6 AI Agent 域(potry-ai-agent,18 端点)

### 域级思路
对话入口 `/agent/workflow` = LangGraph 12 节点确定性行程 + SSE 帧协议(meta→trace→tool_status*→token*→action*→done);管理三件套(审核/成本/审计)+ 知识库对账同步构成数据闭环。鉴权三态:用户 JWT(claims 优先)、管理 JWT(resolve_admin)、遗留回退(无 token 信 body,`AUTH_STRICT=1` 可关)。

### 对比主流
Dify/Coze 把编排做成可视化,本项目做成代码图——换来节点级单测(423 例)与审计粒度;SSE 帧协议自定义(对比 OpenAI Assistants 的事件协议,本项目多了 trace/action 两类业务帧);成本按意图归因直查 Langfuse ClickHouse,是商业平台才有的粒度。

### 优缺点
优点:状态可恢复(sqlite checkpoint,thread_id=sessionId)、写操作 interrupt 人工确认、trace 帧把意图/闸门/召回数/耗时全量回传前端(前端能画出"这轮为什么这么答")。缺点:🔴resume/negative/correction 三个端点鉴权缺口;🔴Vue 未实现 confirm_ticket 链路(409 卡死);🟡/agent/chat 旧链未退役。~~伪流式~~ **已于 2026-10-26 改造为 astream_events 真流式**:LLM delta 实时成 token 帧、工具执行实时成 tool_status 帧(calling→done),实测首 token 由"全图跑完"(≈总耗时 9~10s)提前至 6.2~7.9s(前置链路完成后立即开始逐字输出),前端帧协议零改动;429 测试全绿(新增 6 例流式契约用例)。

---

### GET /health、/nav、/metrics
- /health:常量 UP(不触依赖)| /nav:运维导航页(Grafana/Prometheus/MQ/Nacos 入口聚合)| /metrics:自写 middleware(main.py:194-220,绕开 instrumentator 7.x 兼容 bug——曾实测把 admin API 全打 500),`http_requests_total{method,handler,status}`+duration Histogram | 均无鉴权

### POST /agent/chat ⚪(旧单轮,建议退役)
- 鉴权:🟡resolve_user_id 结果被丢弃(不落归属);body `{userId?,sessionId?,message,selectedPoemId?}`
- 流程:内存 SessionStore+trim→llm.bind_tools().ainvoke→有 tool_call 走旧 ToolRegistry(最多 1 轮)→astream 产 token 帧→finally persist_turn
- SSE:`meta{sessionId}→tool_status*→token*→done`;流前失败 502(不含密钥) | main.py:351 | 前端: 无(仅 evals+测试)

### POST /agent/workflow — 主对话入口
- 鉴权:resolve_user_id(claims 优先,遗留回退);503 图未就绪;**409 该 thread 有未决 interrupt**
- body `ChatRequest{userId?,sessionId?,message,selectedPoemId?}`(selectedPoemId=Ch05 两段式点选的诗词卡 id,进 slot 槽位)
- 节点:resolve(指代消解)→classify(八类意图+置信度)→route→知识类 retrieve(三源召回+MySQL 回查)→gate(0.46 阈值,不足→兜底话术+pending_questions)→agent(ReAct+tool_node);判定类 slot_check(槽位+诗词卡片候选,两段式)→expand_query→retrieve_policy;写工具经 ticket_confirm interrupt;log 落库+层2摘要投递
- **SSE 帧协议**:`meta{sessionId}`→`trace{intent,route,gate,score,retrievedCount,iters,tokens,elapsedMs,fallbackReason,confidence,queryChanged,subflowKind,policyCount,poemId}`→`tool_status*{tool,status,args,durationMs}`→`token*{content}`(8 字符切片)→`action*`(forum_draft/pick_poem/open_correction_form/confirm_ticket{preview,toolCallId})→`done{sessionId,source,status}`;source∈preset|fallback|tool|rag|model,status∈ok|awaiting_confirmation|awaiting_slot
- 流式实现:**2026-10-26 已改造为真流式**——`astream_events(v2)` 事件流直驱:agent 节点 LLM delta 实时转 token 帧,on_tool_start/end 实时转 tool_status 帧(calling→done),trace/action 帧图结束后从最终状态补发;帧序实测 `meta → tool_status* → token* → trace → action? → done`(token 先于 trace 是实时性的必然代价,前端按事件名分发与顺序无关)。config 全链透传(agent_react→LLM、tool_node→catalog→engine→BaseTool)是事件流生效的前提,同时让 Langfuse generation 正确挂载。preset/fallback 等不经 agent LLM 的答案在图结束后按前缀规则补发,发散不补帧防前端文本重复;测试替身等无 astream_events 的装配自动回退伪流式,旧帧序契约由 6 个新单测固化(tests/test_workflow_streaming.py)
- 位置: main.py:557 | 前端: AiChat.vue:167(fetch SSE)、static/chat.html:1034

### POST /agent/workflow/resume — 工单确认续跑 🔴无鉴权
- body `{sessionId,confirmed}`;无挂起 interrupt→409;`ainvoke(Command(resume={confirmed}))` 恢复 ticket_confirm(节点开头重算预览,无副作用)→confirmed 回 tool_node 决定是否执行写工具→ReAct 继续→同款帧序返回
- 🔴不调 resolve_user_id:知道 sessionId 即可确认/取消他人工单
- 🔴**Vue AiChat.vue 未实现 confirm_ticket→resume 链路**:Vue 用户遇确认帧后无法续跑,该 thread 永久 409(只有 static/chat.html 能走通)| main.py:605

### 反馈三端点
- POST /agent/feedback(👍/建单):resolve_user_id(匿名也收)→app_storage.add_feedback→**feedback 表**(复用 Java 表,列名 messsage 照抄)| 前端: AiChat.vue:329
- POST /agent/feedback/negative(👎)🔴无鉴权:aget_state 回捞快照(user_input 匹配才带召回快照)→pending_questions(source_entry=user_dislike)+flywheel.schedule | 前端: AiChat.vue:329
- POST /agent/correction(纠错单)🔴无验签(同族唯独这里漏了):body{userId?,sessionId?,poemId?,category,detail}→**corrections 表**;400 类目非法 | 前端: 仅 static/chat.html(Vue 未接)

### 会话回载(2 端点,已加固)
- GET /api/conversations(list)/ GET /api/conversations/{id}/messages:resolve_user_id→无身份 401(旧"匿名拉全部"已封);只返回 user/assistant 两类,userId 不匹配视同不存在 | 前端: AiChat.vue:241,251

### 管理三件套 + KB(6 端点,resolve_admin)
- GET /api/admin/review?status=pending&limit=50(待审列表)/ GET /{id}(详情+召回快照)/ POST /{id}/approve(body{standard_question,approved_answer}:写 qa chunk→embed→Milvus upsert→mark_embedded;向量失败 **503 状态保持 pending 可重试**)/ POST /{id}/reject(409 已处理防重复审)| 前端: adminApi.ts 全接(Vue 管理台)+ static/admin_review.html
- GET /api/admin/cost?days=7(1..90 外 400):**直查 Langfuse ClickHouse events_full**,trace metadata.intent JOIN GENERATION 按 intent+model 聚合三类 token;价格表仅 deepseek-flash(0.30/0.006/1.20 USD/M token),未知模型只计数不计价;503 CH 不可达 | 前端: 管理台成本报表页
- GET /api/admin/audit?tool_name&status&session_id(limit 钳 1..200):**tool_audit_logs 只读流**,参数/结果截 400 字符 | 前端: 管理台工具审计页

### 知识库同步(2 端点)
- GET /api/admin/kb/syncstats:三数口径——potry_total(全表 count)/ poem_covered(chunks 表 source_type=poem 的 **distinct source_id**,🟡只算"有块"不校验内容一致)/ pending、embedded;consistent=potry==covered && pending==0 | 前端: 管理台对账卡
- POST /api/admin/kb/sync?title=:**两种模式**——带 title:同步单首(查 Potry→切分→embed→Milvus→mark_embedded,秒级;🟡诗不存在返回 200+error 字段而非 4xx);无参:后台全量线程+Lock 非阻塞抢占,三步幂等(清孤儿向量→全量 upsert→嵌 pending,失败保持 pending 可重跑);**调用方:Java 导入回调(PotryController:64)+ 管理台手动**| milvus-lite 文件锁:全量重建须停服(vector_store.py:8-16)

---

# Part III 核心技术方案深剖

> 每节:思路 → 与主流对比 → 优缺点 → 改进点。伪代码为真实逻辑的浓缩。

## 4.1 三端 JWT 鉴权体系

**思路**:一套 HS256、两个物理隔离密钥(用户/管理);三道防线同语义实现——网关 AuthGlobalFilter(按前缀 `/user|/ai|/agent` 用户密钥、`/admin|/notice` 管理密钥,白名单放行登录注册公告,验签透传 X-User-Id)→ 服务 JwtToken*Interceptor → Agent auth.py;legacy 密钥列表做无缝轮换(主密钥失败依次试旧密钥,过渡完清空即完成轮换);网关侧支持 EventSource 用 query 传 token(SSE 无法自定义头的现实妥协)。

**对比主流**:Spring Security 全家桶(过滤器链+Provider,通用但黑盒、重);Sa-Token(注解式,轻但引入框架)。自研换来:代码 ~100 行、面试全可手写、三端一套语义。代价:**语义改动要同步三处**(本次探索即发现 resume 端点漏接)。

**优点**:角色隔离=密钥隔离(用户 token 打 /admin 必验签失败);轮换零停机;网关透传 X-User-Id 免下游重复解析。
**缺点**:无 refresh token(TTL 11.92 天,泄露窗口大);无登出吊销;无 RBAC;密钥 11 字节(RFC 7518 建议 ≥32,pytest 有 InsecureKeyLengthWarning);🟡网关新增受保护路径靠人肉记(本次就漏了 /agent)。
**改进**:强密钥+短 TTL+refresh;Redis 黑名单登出;受保护路径清单收进网关配置文件而非代码常量。

## 4.2 MQ 可靠消息闭环(发帖通知)

**思路**(全链,经方法级实证):
```text
发帖事务 INSERT poem_blog
  └─ afterCommit(事务真提交后才发,防脏消息)
      └─ convertAndSend(post.exchange, post.created, json[带traceId])
          ├─ 成功 → PostNotifyListener 消费
          │    ├─ 幂等:setIfAbsent post:notified:{bolgid} (24h)
          │    ├─ 粉丝收件箱:ZADD fan:{fanId}(推模式 feed)
          │    ├─ 缓存预热 blog:{id} 1h
          │    └─ STOMP 广播 /topic/newpost
          └─ 失败 → Redis list mq:pending:post.notify
               └─ 每 20s 定时任务 rightPop 逐条重投(仍挂则推回队尾)
消费失败 → 本地重试 3 次(1s/2s/4s 退避)→ reject 不 requeue → DLX post.dlx → 死信消费者告警计数
```
**对比主流**:RocketMQ 事务消息=半消息+回查的强一致;Outbox 表=本地事务+轮询投递的通用解。本方案是 RabbitMQ 上手搓 Outbox 的 80% 效果——区别在投递窗口(20s 扫描)与无对账界面。
**优点**:发帖 RT 与推送解耦;毒消息防护有真实演练记录(15s 打 40 万行日志教训写在 RabbitMQConfig 注释里);全链 traceId 串联。
**缺点**:at-least-once 需消费端幂等(已做);MQ+Redis 双挂丢消息(注释自认);补偿扫描延迟秒级。
**改进**:Outbox 状态表正规化;死信告警接通知渠道;批量发布合并投递。

## 4.3 实时推送(STOMP)

**思路**:STOMP 端点 /ws,broker 前缀 /topic、应用前缀 /app;两个 topic:新帖广播(MQ 驱动)、定向复习提醒 `/topic/review.{userId}`(定时任务驱动);前端封装指数退避重连(封顶 120s)+登录后才订阅。
**对比**:Socket.IO 有房间/ACK/降级全家桶但非标准协议;SSE 更轻但单向且 EventSource 不能带头(网关为此专门支持 query 传 token)。
**优点**:一套代码覆盖广播+定向;MQ→STOMP 解耦生产与推送。
**缺点**:**连接与订阅无鉴权**(可订阅他人 review topic 听提醒);simple broker 单机;后端 SockJS 配置是幽灵配置。
**改进**:CONNECT 握手带 JWT+订阅目标校验;生产换 RabbitMQ STOMP 插件或 Redis pub/sub 外部 broker。

## 4.4 艾宾浩斯 SRS 调度

**思路**:固定轮次 1/3/7/14/30 天。三条腿:
1. 排期展开(book/start):窗口函数一条 SQL 按组错峰(每天 much 首),learnDate=今天+组序号;
2. 到期查询(book/today / remind):`nextReviewDate<=NOW()` 走 idx_book_next;
3. 推进(query/end kk=1):`CASE reviewCount 0→+3d 1→+7d 2→+14d 3→+30d ELSE NULL`,第 5 次毕业;
提醒:每日 9:00 cron+手动 trigger(force),Redis 批次锁+用户级防重双层幂等,ZSet 提醒历史留 7 条。
**对比主流**:SM-2/FSRS 按回忆质量(0-5 评分)自适应间隔与难度系数;本项目固定轮次,不感知正确率。
**优点**:全部透明可单测;双层防重是分布式幂等的好教材;窗口函数排期一条 SQL 解决批量错峰。
**缺点**:不会的与会的同节奏;kk 无真实判题(恒 1);排期提前展开,增删诗需重算。
**改进**:quality 因子动态间隔(把 check 结果接进 CASE);提醒加邮件降级通道。

## 4.5 LangGraph 对话编排

**思路**:12 节点显式状态图(详见 §2.6 workflow 条目),三道质量闸:意图分类置信度、证据置信度闸(0.5·top1+0.3·margin+0.2·条数,阈值 0.46 经金标校准)、ReAct 步数/token 上限强制收敛;写操作 interrupt 人工确认;AsyncSqliteSaver 跨轮状态(thread_id=sessionId);trace 帧全量回传(前端可解释"这轮为什么这么答")。
**对比主流**:Dify/Coze=可视化快但黑盒难测;纯 Function Calling=简单但幻觉直出;AutoGen=多智能体但状态难管。本质差异:**把 LLM 的不确定关进确定性的 FSM 骨架**——每个节点可单测,423 例离线回归。
**优点**:幻觉有业务出口(兜底话术+喂飞轮);写操作安全;审计可回放(tool_audit_logs);成本按意图归因;真流式(2026-10-26 改造:astream_events 直驱,实测首 token 6.2~7.9s、生成期逐字实时、工具进度实时)。
**缺点**:意图八类硬编码;sqlite 单机;resume 链路鉴权缺口(本轮发现)。
**改进**:~~astream_events 真流式~~已落地(2026-10-26,含 config 全链透传);意图路由配置化/小模型化;checkpoint 迁 Postgres;resume 补 resolve_user_id。

## 4.6 RAG 与知识库对账

**思路**:MySQL 语料→按子节切块(400/60,句号裁剪)→knowledge_chunks(pending)→BGE-M3 onnx 1024 维→Milvus `knowledge`(COSINE)→mark_embedded;三条同步路径(导入回调秒级/syncstats 对账/无参全量幂等重建三步:清孤儿→全量 upsert→嵌 pending);判定类语料走 policy 文档固定 source_id。
**对比主流**:pgvector 运维最简、托管 Milvus 分布式、RAGFlow 开箱即用;本方案"文件级向量库+显式对账"是零成本务实解,代价是文件锁单进程。
**优点**:幂等可断点重跑;三数对账让一致性可见(9948/0/10804 曾是对话素材);嵌入本地化零 API 成本。
**缺点**:建库须停服;纯向量无 BM25 混合;无 rerank;covered 只算"有块"不校验内容一致。
**改进**:独立向量服务;混合检索+reranker;对账加内容 hash 抽检。

## 4.7 上下文三层工程

**思路**:层1 近窗原文→层2 旧消息(assistant 截前缀/大块换标识)→层3 摘要表;预算按模型窗口七三倒推;层2 超限触发后台 LLM 摘要推进锚点;全部双写 context_log 审计;启动时预算自检。
**对比主流**:LangChain Memory/MemGPT 是通用组件;本项目是对话产品定制的三层预算制,与生产 Chat 产品同构,且有审计可回放。
**优点**:摘要异步不阻塞;预算自检防配置漂移。
**缺点**:摘要质量无评估;token 计数近似;魔法数多。
**改进**:摘要忠实性 eval;精确 tokenizer;参数全配置化(部分已做)。

## 4.8 工具系统与 MCP

**思路**:新一代 ToolCatalog+ToolEngine:jsonschema 校验→**写权限门(interrupt 确认)**→仅瞬时错误重试(旧版无差别重试的修正)→枚举翻译→tool_audit_logs 审计;身份一律取验签上下文不信 LLM 传参;MCP client(TTL 5s 缓存,失败保留上次清单)+ 两个自带 mock MCP server(9101/9102);插件目录 mtime 热加载(需 register(catalog))。
**对比主流**:OpenAI FC schema 是事实标准;MCP 是收敛中的协议——本项目 client 端已接,策略表只认本侧声明,未知 server 默认"写+需确认"(保守但激进并存)。
**优点**:写操作双保险;审计可回放;重试语义分型。
**缺点**:新旧两代并存(/agent/chat 还挂旧 ToolRegistry);工具结果无缓存。
**改进**:旧 ToolRegistry 下线;MCP server 白名单;结果缓存。

## 4.9 知识飞轮(数据闭环)

**思路**:四个入口(点踩/纠错/自评"是否承认不知道"/mining 抽取)→ pending_questions → flywheel LLM 标准化+查重 → review_queue → 人工审核 → approve 即入 qa 语料+向量;APScheduler 双 job(mining cron 3 点、flywheel 5min 兜底);水位表 knowledge_mining_cursor 幂等。
**对比主流**:商业 RAG 平台内建数据回流;自研且带人工审核位的少见——审核挡住 LLM 抽取的脏数据。
**优点**:负反馈有出口;审核位保护语料纯度;闭环完整(问题→答案→向量→检索)。
**缺点**:审核界面两套(Vue 控制台+静态页);查重靠 LLM 提示词稳定性。
**改进**:embedding 相似度硬查重;审核批量操作。

## 4.10 Redis 使用全景(缓存/计数/去重/分布式锁)

**思路**:按场景选结构——字符串(验证码/空值缓存/幂等键/批次锁)、ZSet(热搜/点赞占位/提醒历史/收件箱/排行榜)、Set(随机 id 池)、List(MQ 补偿队列)、Hash(排行榜名字)、Redisson bucket+lock(诗人详情缓存)。
**对比主流**:Spring Cache 注解 vs 手搓——手搓才有"逻辑过期+互斥+空值+降级"四合一与 TTL 抖动这些可讲的细节。
**优点**:每个 key 有明确 TTL 与语义;宕机降级路径全都有(DB 兜底)。
**缺点**:🟡`woko:{id}` 双客户端双写无消费者;🟡`woko:{id}` 语义混乱(出题答案却叫点赞前缀);🟡GetContentById 与旧版接口共用 key 不同 TTL 互踩;部分 key 无统一命名规范(blog:like{blogid} vs woko:{id})。
**改进**:key 规范文档化;死 key 清理;双写收敛单客户端。

## 4.11 网关与限流

**思路**:SCG 三过滤器(AuthGlobalFilter order=-100 / RateLimiterConfig IP 令牌桶 2000/s burst 4000 / TraceIdGlobalFilter)+ 统一 CORS。
**对比主流**:对标 Kong/APISIX 三件套;无熔断降级、限流无用户维度是差距。
**优点**:角色隔离一次做对;限流参数经压测背书。
**缺点**:IP 限流 NAT 误伤;/actuator 与 /ws 不过滤;受保护路径硬编码。
**改进**:有 token 时按 userId 限流;接 Sentinel;actuator 收内网。


---

# Part IV 改进总账

## 已落地(可讲"发现→修复→验证"完整故事)

| 改进 | 类别 | 验证方式 |
|---|---|---|
| 删 /build/bulid 整库 DROP 裸路由 | 安全 | 重启后 404 实测 |
| 删旧 AI 孤岛 11 文件(含 /aiaiaai 付费 AI 裸路由) | 安全/卫生 | 全仓引用清零+404 |
| 密钥全部出库至 gitignored secret 文件(service+gateway,键名对齐环境变量占位) | 安全 | 三服务重启后全链 JWT/MySQL/MQ 正常 |
| 网关 /agent/** 纳入 JWT 强制 | 安全 | 无 token 401/伪造 401/真 token 200 |
| Agent conversations 验签优先(封匿名拉全会话) | 安全 | pytest 423 绿(3 契约用例同步更新) |
| Agent requirements 补 PyJWT/langfuse/onnxruntime/requests,删 modelscope | 工程 | venv 实装版本钉入 |
| 前端死文件清理(ai.ts/comment.ts/5×.vue.bak/vite 死代理) | 卫生 | vitest 8 绿+vue-tsc build 通过 |
| RabbitMQ 可靠闭环(confirm+DLX+补偿+毒消息防护) | 可靠性 | 注释留实测记录 |
| 背诵提醒批次锁+用户级双防重 | 正确性 | ReviewRemindTask.java |
| Hikari 10→20(压测定位 700 QPS 瓶颈) | 性能 | application.yml:50-55 |
| Redis 超时 500ms 快速失败防雪崩 | 稳定性 | application.yml:86-95 |
| BGE-M3 onnx(51ms vs torch 142ms,对齐验证) | 性能 | EMBEDDING_ENGINE |
| 置信度阈值 0.46 金标校准 | 效果 | evals/calibrate_confidence.py |
| Agent 离线测试 423 例(全替身,CI 可跑) | 质量 | pytest -q 66s |
| Java 首批单测 23 例(点赞幂等 9/JWT 轮换 7/随机 id 池 4/异常契约 3,纯 Mockito 离线) | 质量 | mvn test 全绿;**顺手抓到两个真问题:toggleLike 的 catch(Exception) 吞死锁耗尽异常并多走一轮降级重试(共 10 次事务);JwtUtil legacy 循环吞异常导致过期 token 误报 SignatureException** |

## 待办(二轮深挖后重新排序)

**P0 安全**
1. `/agent/workflow/resume` 补 resolve_user_id(当前知道 sessionId 即可动他人工单)
2. Vue AiChat.vue 实现 confirm_ticket→resume 链路(否则 Vue 用户建单确认即 409 卡死)
3. 水平越权三连:FeedBack 的 delete/update/getAll 迁 /admin 或加校验;game 的 delete/SelectPage 同;名句收藏 userid 改服务端覆写
4. `/agent/feedback/negative`、`/agent/correction` 补验签;`/agent/chat` 退役
5. `/admin/login/code` 去掉响应体回显;login 删 System.out.println(password)

**P1 正确性**
6. /admin/potry/delete 前后端契约对齐(前端改发 body);rhesis/writerDelete 补 paramsSerializer
7. select/guanzhu 判空条件反转修复(关注流才真正可用)
8. 计分服务端权威化(若游戏域要救活);guanzhu 补唯一约束+自关注校验
9. /user/forget 改 POST;删 login 密码打印
10. toggleLike 的 catch(Exception) 窄化为 Redis 专用异常(当前会吞死锁耗尽的 DB 异常并重复重试 10 次事务,单测已固化现状,PoemLunTanServiceLikeTest deadlock_exhausted 用例注释里写了修法);JwtUtil legacy 循环不吞 legacy 分支异常(过期误报 SignatureException)

**P1 架构**
10. ~~真流式(astream_events)~~**已落地(2026-10-26,含 config 全链透传与 6 例流式契约测试)**;/agent/chat 旧链下线+ToolRegistry 收敛一代
11. AI 出题链路决策:接回前端或整体退役(woko:{id} 死 key 清理)

**P2 质量/卫生**
12. 38 个前端死 API 函数回收(练手);后端 ~70 死端点分批下线(先删 /user/Comment、/user/game 全组)
13. Java 测试从 0 到 1(优先 /user/book SRS 链路与点赞幂等);命名规范统一(potry/poetry、getmassage、Conmmets、Rondom…)
14. 根目录杂物清理(ARCHITECTURE §9 清单)

---

# Part V 面试 Q&A 弹药库

**Q1:为什么用 RabbitMQ 而不是 RocketMQ 事务消息?**
答:发帖推送是"尽量送达"而非强一致业务。我用 publisher confirm+本地重试退避+DLX+20s 补偿重投,在 RabbitMQ 上实现了 Outbox 的主要语义;真要强一致(如订单)我会换 RocketMQ 事务消息或正规 Outbox 表。补充:我处理过毒消息无限重投把日志打到 40 万行/15s 的实战问题,解法是本地重试 3 次后 reject 不 requeue 进死信。

**Q2:缓存怎么防击穿/穿透/雪崩?**
答:诗详情接口四合一——逻辑过期(过期不阻塞,异步重建)+setIfAbsent 互斥锁+不存在值写 2min 空值缓存防穿透+TTL 10±3min 抖动防雪崩,Redis 宕机全部降级直查 DB。搜索联想用 ZSet 字典序前缀匹配,随机推荐用 Set 随机 id 池替代 ORDER BY RAND() 避免全表 filesort。

**Q3:点赞怎么保证幂等?**
答:三层——Redis ZSet 原子占位(快速判断)→DB 明细表 (user,item) 唯一约束 INSERT IGNORE(事实源,affected>0 才动计数)→编程式事务+死锁重试 4 次。Redis 只是加速层,Redis 挂了降级 DB 判重,数据不丢不重。

**Q4:JWT 无状态怎么登出/轮换?**
答:轮换做了——三端共享 legacy 密钥列表,新密钥上线旧密钥继续可验,过渡完清空即完成轮换,全程无感。登出没做(诚实回答),方案是 Redis 黑名单+jti,这是我的待办。另外我承认 TTL 11.92 天太长,应该短 TTL+refresh。

**Q5:LLM 幻觉怎么控?**
答:三道闸:意图分类置信度、证据置信度闸(0.46 阈值是拿金标集校准出来的,不是拍脑袋)、ReAct 步数/token 上限强制收敛。闸门不过给兜底话术并把问题写入待审池,人工审核通过的答案变成 qa 语料重新嵌入——幻觉有了业务出口而不是简单拦掉。写操作(发帖建单)走 interrupt 人工确认。

**Q6:RAG 的数据一致性怎么保证?**
答:三个数对账——MySQL 总数、向量库覆盖数(有块的诗数)、pending/embedded 块数。三条同步路径:管理端导入后异步回调单诗秒级嵌入、对账接口暴露差异、全量重建三步幂等可断点重跑(清孤儿→全量 upsert→嵌 pending)。嵌入从 torch 换 onnx 后单条 51ms,一首诗秒级完成。

**Q7:上下文超限怎么办?**
答:三层结构——近窗原文、旧消息截短(assistant 留前缀防半句话)、更早的进摘要表;预算按模型窗口七三倒推;层2 超预算触发后台异步摘要推进锚点,不阻塞对话。所有拼装有审计日志,启动时自检预算配置。

**Q8:AI 改造把项目改陌生了,你怎么办?**
答:我给自己建了一套"重新认领"流程:方法级接口考古(全部结论带 file:line)→一致性体检(死代码/幽灵配置/契约不符/越权面)→落三份文档(架构全景/CLAUDE.md/阅读路线)→按风险排序修复并全部实测回归。本轮就修了整库 DROP 裸路由、密钥出库、网关 /agent 鉴权缺口,423 个测试保持全绿。

**Q9:这个项目最大的技术债是什么?**(主动示弱题)
答:三件:一是 AI 迭代留下的双实现(旧 /agent/chat vs workflow、旧 /user/poetry 诗人类接口 16 个死端点),我已开始分批回收;二是 Java 侧零有效测试(对照 Agent 侧 423 例,梯度刺眼);三是部分越权面(反馈删除/成绩删除挂在用户路径下),我在文档里全部实名定位了,修复是机械工作。

**Q10:如果重做,你会改什么?**
答:三件:一开始就用 Spring Security+短 TTL refresh,不自研;二是 LLM 流式从第一天就用 astream_events,伪流式是我最想拆的雷;三是先写测试再让 AI 改代码——AI 改得快,但没有回归网的情况下每一轮都是赌博,423 个测试后来救了我很多次。
