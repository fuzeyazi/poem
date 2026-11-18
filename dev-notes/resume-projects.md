# 简历项目描述(双项目拆分版)

> 生成于 2026-10-26,素材全部来自 codebase-xray 两轮考古(docs/TECH-REPORT.md、docs/ARCHITECTURE.md)。
> 每个数字都能在代码/测试/压测记录里兜底,对应章节标在括号里,面试前过一遍即可。

## 0. 拆分逻辑与诚实边界(先读这个)

- **项目 A** = potry-service + poetry-gateway(Java 业务后端),**项目 B** = potry-ai-agent(Python AI 服务)。二者是同一产品的两个独立服务:独立进程、独立技术栈、独立测试体系(23 例 vs 423 例)、独立启动与部署(start-all.bat 明确分层)。
- 被问"这两个项目什么关系?"——标准答法:**"同一个产品的两个服务,我作为唯一开发者从零负责两端;后端按章节推进业务,AI 服务是独立设计的第二期。拆开讲是因为技术域完全不同。"** 不回避同仓库、不虚构团队。
- 简历上可以写"诗词学习平台(后端服务)"和"AI 伴学 Agent 服务"两个条目,不必写"模块"。
- **不要写的**:"微服务架构"(就是三个进程);游戏域与旧评论域(死代码,不提);120 个接口这种全量数字(说"核心业务链路")。~~伪流式~~**2026-10-26 已改造为 astream_events 真流式**(LLM delta/工具进度实时下发,前端协议零改动,429 测试全绿),现在可以作为亮点写(见项目 B 第 2 条)。

---

## 1. 项目 A:诗词文化学习平台(后端方向)

**技术栈行**:Spring Boot 3 / Spring Cloud Gateway / MyBatis / RabbitMQ / Redis / MySQL 8.4 / Nacos / STOMP / JUnit 5 / Prometheus

### 完整版(7 条,适合技术展开页)

- 基于 Spring Cloud Gateway 构建统一入口:自研双密钥 JWT 鉴权(用户/管理员密钥物理隔离实现角色隔离),支持 legacy 密钥列表实现**三端(网关/服务/Agent)零停机无缝轮换**;IP 令牌桶限流 + TraceId 全链路透传,服务侧拦截器二次校验构成纵深防御(ARCHITECTURE §4.1/§2.14)
- 发帖通知基于 RabbitMQ 实现**可靠消息闭环**:事务提交后投递(防脏读)+ publisher confirm + 本地重试退避 + 死信队列告警 + 20s 补偿重投;消费端幂等键防重,粉丝收件箱(Redis ZSet 推模式 feed)+ STOMP 实时广播;曾定位**毒消息无限重投故障(15s 刷 40 万行日志)**,以重试上限+不 requeue 治理(TECH-REPORT §4.2)
- 设计 Redis 缓存体系:诗详情"**逻辑过期+互斥锁+空值缓存+宕机降级**"四合一,完整覆盖击穿/穿透/雪崩三类问题;热搜榜(ZSet 滑动 24h + top1000 截断 + 同用户 60s 去重)、搜索联想(ZSet 字典序前缀匹配)、随机推荐(**Redis Set 随机 id 池替代 ORDER BY RAND()**,消除全表 filesort)(TECH-REPORT §4.10)
- 点赞场景设计**幂等 toggle**:Redis ZSet 原子占位 + 明细表唯一约束 INSERT IGNORE 作为事实源 + 计数列仅在 affected>0 时更新,Redis 故障时降级 DB 判重零感知;InnoDB 死锁以编程式事务重试治理,并以 **9 个单测固化全部分支契约**(PoemLunTanServiceLikeTest)
- 设计**艾宾浩斯遗忘曲线复习系统**:窗口函数单 SQL 完成按组错峰排期,CASE 轮次推进 1/3/7/14/30 天;每日定时提醒采用 Redis 批次锁+用户级**双重防重**保证幂等,提醒历史用 ZSet 滚动留痕(TECH-REPORT §4.4)
- 检索与性能:MySQL FULLTEXT ngram 复合索引实现标题/诗人联合检索、单字回退 like;**压测定位 Hikari 连接池瓶颈**(QPS 钉在 ~700),调优连接数与 3s 快速失败获取策略;Prometheus 直方图暴露 P95/P99(TECH-REPORT §2.2/§4.11)
- 安全与工程治理:主导一轮安全清零(整库 DROP 裸路由、硬编码密钥、越权面),**全部密钥出库至 gitignored 配置文件**并以环境变量占位对齐;JUnit 单测 23 例固化幂等/轮换/缓存降级契约,离线可跑(TECH-REPORT §5)

### 精简版(4 条,适合单页简历)

- Spring Cloud Gateway 统一网关:双密钥 JWT 角色隔离 + legacy 密钥三端零停机轮换 + 令牌桶限流 + TraceId 全链路透传
- RabbitMQ 可靠消息闭环:confirm + 死信 + 20s 补偿重投 + 消费幂等,治理过毒消息无限重投故障(15s 40 万行日志)
- Redis 缓存与热点设计:逻辑过期+互斥锁+空值缓存+降级四合一;随机 id 池替代 ORDER BY RAND();点赞幂等(ZSet 占位+明细表事实源+死锁重试)并以单测固化
- 艾宾浩斯复习系统:窗口函数错峰排期 + 轮次推进 + 双重防重定时提醒 + STOMP 定向推送

### 深挖预判(被追问时的锚点)

| 追问 | 答法锚点 |
|---|---|
| 轮换怎么做到零停机? | legacy 列表逐个回退验签,旧 token TTL 内有效,过渡完清空;三端同一契约,JwtUtilLegacyRotationTest 7 例 |
| 毒消息是什么? | 消费者默认 requeue=true,坏消息无限循环重投;改本地重试 3 次(1s/2s/4s)+ reject 不 requeue 进 DLX |
| 为什么用明细节表而不只靠 Redis 计数? | Redis 重启丢数据会被无限刷;明细表 INSERT IGNORE 是事实源,affected=0 自动拦截重复计数,惰性自愈 |
| ORDER BY RAND() 有什么问题? | 全表扫描+filesort;id 池 SRANDMEMBER 抽样后主键 IN 回表,池 1h 过期自愈,Redis 挂了降级回原查询 |
| 提醒为什么要两层防重? | 批次锁防多实例重复跑批,用户级防重防手动触发与定时叠加;ZSet score=时间戳天然按序,裁剪留 7 条 |

---

## 2. 项目 B:AI 伴学 Agent 服务(Agent 方向)

**技术栈行**:Python / FastAPI / LangGraph / LangChain / Milvus / BGE-M3 / MySQL / Nacos / Langfuse / Prometheus / pytest(423 例)

### 完整版(8 条)

- 基于 **LangGraph 构建 12 节点确定性对话编排**(指代消解→意图分类→路由→检索→置信度闸→ReAct 工具循环→结构化落库),把 LLM 的不确定性关进可测的状态机骨架;**423 个离线单测**(全替身注入、可 CI、66s 跑完)保障节点级回归(TECH-REPORT §4.5)
- 设计**检索置信度闸门**:0.5·top1 + 0.3·margin + 0.2·召回条数加权评分,阈值 0.46 经金标集校准得出;不达标转兜底话术并写入待审池,**让幻觉有业务出口而非简单拦截**;每轮以 trace 帧回传意图/得分/召回数,回答全程可解释(TECH-REPORT §4.5)
- 将 SSE 输出从"整图跑完后的切片重放"**改造为 astream_events 真流式**:LLM delta 实时下发、工具进度(calling→done)实时可见,首 token 延迟从全图完成时间(9~10s)提前至 6~8s 并逐字输出;补齐 config 全链透传(agent→LLM、tool_node→catalog→engine→BaseTool),同时修正 Langfuse generation 挂载;前端帧协议零改动,新增 6 例流式契约测试(TECH-REPORT §4.5)
- 构建 **RAG 管道与一致性对账**:诗词语料按语义子节切块(400 字/重叠 60),BGE-M3 本地 onnx 推理(**51ms/条,较 torch 降 60%+**,对齐验证)写入 Milvus;MySQL↔向量库**三数对账**(总数/覆盖/待嵌)+ 管理端导入回调秒级增量同步 + 全量幂等重建(清孤儿→补切分→嵌 pending,可断点重跑)(TECH-REPORT §4.6)
- 工具系统:**JSON Schema 校验 + 写操作权限门(interrupt 人工确认)+ 工具调用审计表**,身份一律取验签上下文不信任 LLM 传参;接入 **MCP 协议** client(TTL 缓存+失败保留上次清单),自带 2 个 mock MCP server 验证协议链路,支持插件目录热加载(TECH-REPORT §4.8)
- **上下文三层工程**:近窗原文/旧消息截短/LLM 摘要分层,按模型窗口倒推预算配比;层超限触发后台异步摘要不阻塞对话;拼装全量审计日志可回放(TECH-REPORT §4.7)
- 设计**知识飞轮数据闭环**:点踩/纠错/模型自评/夜间对话挖掘四路入口→LLM 标准化查重→人工审核→质检通过的问答对即时嵌入检索库,水位表保证抽取幂等(TECH-REPORT §4.9)
- **可观测与成本归因**:Langfuse 全链 trace;自研 Prometheus middleware(绕开 instrumentator 兼容缺陷);直查 ClickHouse 实现**按意图聚合的 token/成本报表**(TECH-REPORT §4.10)
- 工程集成:与 Java 后端共享 JWT 三端验签(claims 优先,防伪造 userId);Nacos 注册并手写心跳线程补 SDK 不自动续约缺陷;测试驱动出 3 处契约缺口并同步修复(TECH-REPORT §2.6)

### 精简版(4 条)

- LangGraph 12 节点确定性编排(意图分类→检索→置信度闸→ReAct 工具),423 个离线单测全替身可 CI,节点级回归保障
- 检索置信度闸门(加权评分+金标校准阈值 0.46),幻觉转兜底+待审池,trace 帧全量可解释
- RAG:BGE-M3 onnx 本地推理(51ms/条)+ Milvus,MySQL↔向量库三数对账+导入回调秒级同步+幂等全量重建
- 工具安全与闭环:JSON Schema 校验+写操作 interrupt 人工确认+审计表;MCP client+插件热加载;点踩/纠错→挖掘→人工审核→入库的知识飞轮

### 深挖预判

| 追问 | 答法锚点 |
|---|---|
| 为什么用 LangGraph 不用 Dify/Coze? | 要节点级可测试与审计粒度;423 个单测是护城河;低代码平台黑盒调不了置信度闸这类自定义节点 |
| 置信度公式怎么来的? | 三个信号:最高分(绝对质量)、top1-top2 差距(区分度)、有效条数(证据量);权重初设后拿金标问答集扫阈值,F1 最优取 0.46 |
| 为什么本地 onnx 不调 embedding API? | 成本为零+延迟可控(51ms);做了与 torch 引擎的输出对齐验证;模型文件本地管理 |
| 写操作为什么要 interrupt? | create_ticket 是唯一写工具,两段式:节点抽取预览→interrupt 暂停→前端确认→恢复执行;节点开头重算预览保证无副作用 |
| 检索不准怎么办? | 三源召回(诗/诗人/问答)+MySQL 原文回查;闸门兜底;用户点踩/纠错直接喂飞轮,审核通过即变语料——检索质量随使用自增强 |
| 423 个测试怎么做到离线? | conftest 注入 sqlite 内存库+fake LLM upstream+替身 embedder/vector store,禁预热与 Langfuse;与 evals(联机真模型验收)严格分离 |

---

## 3. 两种投递组合

### 投 Java 后端岗
顺序:项目 A 在前(完整版 7 条),项目 B 在后(精简版 4 条)。自我介绍主线:"业务后端工程能力(可靠性/缓存/幂等/测试),并具备 AI 服务工程化能力"。

### 投 AI 应用/大模型应用岗
顺序:项目 B 在前(完整版 8 条),项目 A 在后(精简版 4 条)。主线:"Agent 工程化全链路(编排/RAG/工具/评测/成本),且有传统后端功底支撑"。

### 通用提醒
- 两个项目都别超过简历半页,完整版留到面试展开;数字(423/0.46/51ms/700QPS/40 万行)宁可少写不可编造——每个都能被要求"打开代码看"。
- 面试前把对应 TECH-REPORT 章节重读一遍,深挖预判表里的每个锚点都能落到 file:line。
- 最强的一张牌:**"我给自己做了 codebase-xray 考古流程,所有结论带 file:line,测试抓出过我自己代码的隐藏缺陷(死锁耗尽被降级路径吞掉重试 10 次)"**——体现工程素养而非背诵。

---

# 简历落地稿(2026-10-26,按实际简历 PDF 定稿,直接可粘贴)

## 背刺预警:原简历项目经历与代码不符的 4 处(已在新稿中全部替换)

| 原简历说法 | 代码实际情况 | 处置 |
|---|---|---|
| 布隆过滤器防缓存穿透 | 无布隆过滤器,实际是空值缓存(PotryServiceImpl.java:144-235) | 新稿改写为"空值缓存+四合一" |
| 三级缓存体系(Redis→MySQL→本地 Caffeine) | 无本地缓存,全工程零 Caffeine | 新稿不再提三级,写缓存四合一样板 |
| RabbitMQ comment.fanout 交换机 | 实际是 direct 交换机 post.exchange,发帖通知场景 | 新稿按真实拓扑写 |
| 覆盖索引(用户ID+时间联合索引) | 未找到证据 | 删除;若实际存在自行恢复 |

## 项目经历(修改版)

**古韵传习堂 —— http://norg.asia/**  2024.10-至今

诗词文化学习平台(已上线):集内容检索、社区互动、AI 伴学于一体,本人为唯一后端开发,负责服务端全部设计实现。
**技术架构**:Spring Boot 3 + Spring Cloud Gateway + MyBatis + RabbitMQ + Redis + MySQL 8.4 + Nacos + STOMP WebSocket

- 基于 Spring Cloud Gateway 构建统一入口:自研双密钥 JWT 鉴权(用户/管理员密钥物理隔离实现角色隔离),legacy 密钥列表实现网关/服务/AI 三端零停机无缝轮换;IP 令牌桶限流 + TraceId 全链路透传,服务侧拦截器二次校验形成纵深防御
- 发帖通知基于 RabbitMQ 实现**可靠消息闭环**:事务提交后投递 + publisher confirm + 本地重试退避 + 死信队列 + 20s 补偿重投,消费端幂等键防重;曾定位毒消息无限重投故障(15s 刷 40 万行日志),以重试上限+不 requeue 根治
- 诗详情缓存实现**"逻辑过期+互斥锁+空值缓存+宕机降级"四合一**,完整覆盖击穿/穿透/雪崩;衍生设计:Redis Set 随机 id 池替代 ORDER BY RAND() 消除全表 filesort、ZSet 字典序搜索联想、滑动窗口热搜榜
- 点赞场景设计**幂等 toggle**:Redis ZSet 原子占位 + 明细表唯一约束(INSERT IGNORE)作为事实源,计数列仅在 affected>0 时更新,Redis 故障降级 DB 判重;InnoDB 死锁以编程式事务重试治理,9 个单元测试固化全部分支契约
- 设计**艾宾浩斯遗忘曲线复习系统**:窗口函数单 SQL 完成按组错峰排期,CASE 轮次推进 1/3/7/14/30 天;每日定时提醒采用 Redis 批次锁+用户级双重防重保证幂等,STOMP 定向推送
- 检索与性能:MySQL FULLTEXT ngram 复合索引实现标题/诗人联合检索;**压测定位 Hikari 连接池瓶颈**(QPS 钉在 ~700),调整连接数与 3s 快速失败获取策略;Prometheus 直方图暴露 P95/P99

**AI 伴学 Agent「青莲」(独立 Python 服务)**  2025.xx-至今(时间按实际填)

为平台构建的 AI 伴学服务:意图识别、知识检索、出题伴学,与 Java 后端共享 JWT 鉴权与业务库。
**技术架构**:Python / FastAPI / LangGraph / LangChain / Milvus / BGE-M3 / MySQL / Langfuse / pytest(420+ 用例)

- 基于 **LangGraph 构建 12 节点确定性对话编排**(指代消解→意图分类→路由→三源检索→置信度闸门→ReAct 工具循环→结构化落库),把 LLM 的不确定性关进可测试的状态机骨架;**420+ 个离线单测**(全替身注入、可 CI)保障节点级回归
- 设计**检索置信度闸门**:0.5·top1 + 0.3·margin + 0.2·召回条数加权评分,阈值 0.46 经金标集校准;不达标转兜底话术并写入待审池——**让幻觉有业务出口而非简单拦截**
- 将 SSE 从"整图跑完后的切片重放"**改造为 astream_events 真流式**:LLM delta 与工具进度实时下发,补齐 config 全链透传,前端协议零改动;实测首 token 从全图耗时(9~10s)提前至 6~8s
- 构建 **RAG 管道与一致性对账**:语料按语义子节切块,BGE-M3 本地 onnx 推理(**51ms/条,较 torch 降 60%+**)写入 Milvus;MySQL↔向量库三数对账 + 导入回调秒级增量同步 + 幂等全量重建
- 工具系统:JSON Schema 校验 + **写操作 interrupt 人工确认** + 调用审计表;接入 MCP 协议 client(自带 mock server 验证协议链路),支持插件热加载
- 设计**知识飞轮数据闭环**:点踩/纠错/模型自评/夜间对话挖掘四路入口→LLM 查重→人工审核→即时嵌入检索库;直查 ClickHouse 实现**按意图聚合的 token/成本归因报表**

## 数学智能回答助手的处置建议
- 推荐 A:删掉,版面让给两个可兜底的项目(RAG 亮点已融入 Agent 项目)
- 选 B 保留则压缩为 2 行,并准备回答"它和青莲 Agent 什么关系、为什么技术栈不同"

## 其他修改提醒
- 专业技能"Langchan4j"→ LangChain4j
- 实习经历里的 Spring AI SSE(单轮流式)与 Agent 项目的 LangGraph 流式是两回事,面试口径:"实习接口是 Spring AI 单轮流式推送,个人项目是 LangGraph 编排下的事件流真流式"
- 新稿所有数字(40 万行/700QPS/0.46/51ms/420+)均可回溯到代码、测试或压测记录,文档锚点见 TECH-REPORT.md
