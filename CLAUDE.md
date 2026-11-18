# CLAUDE.md — poetry-spring2 项目速查(给 AI 会话)

> 生成于 2026-10-25 codebase-xray 全量探索;详细证据见 `docs/ARCHITECTURE.md`,逐接口设计与主流对比见 `docs/TECH-REPORT.md`,阅读路线见 `docs/READING-PATH.md`。用户手写笔记在 `dev-notes/`(ch01~ch08 章节笔记、project-api-map.md、interview-quickcard.md)——**这是用户的面试简历项目,按章节推进,近期由 AI 高频代改**。

## 项目是什么

诗词文化学习平台:Java 单体业务后端 + Python AI 伴学 Agent + Vue3 前端,网关统一入口。仓库根 pom 聚合名是历史 scratch 名 `tt1`(groupId com.nhky),与"poetry"无关。

## 服务拓扑与端口

| 服务 | 端口 | 启动 |
|---|---|---|
| MySQL 8.4(datadir C:\Users\fuze\mysql-data) | 3306 | start-all.bat 依序拉起 |
| Redis | 6379 | 〃 |
| Nacos standalone(E:\javatexts\nacos-dl) | 8848 | 〃 |
| potry-service(Spring Boot,Nacos 名 `potry-service`) | 8081 | 〃(需先 `mvn -pl potry-service -am package -DskipTests`) |
| poetry-gateway(统一入口) | 9080 | 〃 |
| potry-ai-agent(FastAPI,uvicorn main:app) | 8000 | **不在 start-all 内**,由 agent session 自行管理 |
| frontend(vite dev) | 5173 | `npm run dev` |

停全部:`stop-all.bat`。全栈健康:`curl :8000/health`、`:8081/actuator/health`、`:9080/notice/getList`(该链通了=网关+服务+MySQL 都活)。

## 常用命令

```bash
# Java 构建(不在 PATH,用 IDEA 自带)
"/e/java/IntelliJ IDEA Ultimate/plugins/maven/lib/maven3/bin/mvn" -pl potry-service -am package -DskipTests
# Java 单测(离线可跑,不碰中间件;改 toggleLike/JwtUtil 轮换/随机id池/异常契约必跑)
"/e/java/IntelliJ IDEA Ultimate/plugins/maven/lib/maven3/bin/mvn" -pl potry-service -am test -Dtest='PoemLunTanServiceLikeTest,JwtUtilLegacyRotationTest,RandomIdPoolTest,GlobalExceptionHandlerTest' -Dsurefire.failIfNoSpecifiedTests=false
# Agent 测试(离线可跑,48s)
cd potry-ai-agent && ./.venv/Scripts/python.exe -m pytest -q     # 基线:429 passed(含 6 例真流式契约)
# Agent 新增依赖后必须同步 requirements.txt(2026-10-25 已补齐 PyJWT/langfuse/onnxruntime/requests,移除未用的 modelscope)
# 前端测试(离线,5s)
cd frontend && npm test           # vitest,基线:8 passed
# 前端构建含类型检查
cd frontend && npm run build      # vue-tsc --noEmit && vite build
```

## 目录地图

- `potry-service/` 业务主体(controller/{admin,user,Ai}+service+mapper+task+mq);实体在 `poetry-pojo`
- `poetry-common/` Result/JwtUtil/RedisUtil 等公共件(仅 potry-service 用)
- `poetry-gateway/` 路由全在 yml;AuthGlobalFilter 第一道 JWT
- `potry-ai-agent/` FastAPI:main.py(装配)、workflow/(LangGraph 12 节点)、tool_system/(新工具引擎)、tools/(旧+插件)、knowledge/build_kb/vector_store(RAG)、tests/(离线 pytest)、evals/(**联机真模型验收,勿与 pytest 混淆**)
- `frontend/src/` router、api/、store/(user+admin 双 Pinia)、views/
- `docs/bench/` 压测脚本;`docs/superpowers/` 设计文档;`deploy/observability/`
- **忽略/勿引用**:target/、node_modules/、根目录 build*.log、run-*.log、hs_err*、mp3、练手 java(k.java 等)、`-m`/out/work/data/standalone 目录、potry-ai(死模块)、根 src/(空)

## 代码现状与实际约定(以观察为准,非理想规范)

- 持久层:**注解 SQL 为主(~170 处)+ 7 份 XML**(resources/Mapper/);MyBatis-Plus 只用了 StringUtils,无 @TableName/BaseMapper;分页真实配置在 `MyBatisConfig.java:16-34`(yml 里 pagehelper.* 是幽灵配置)
- 返回:统一 `Result`/`PageResult`(poetry-common);但分页实际有三套写法并存
- 鉴权:双 JWT 体系(用户端 sky.jwt.user / 管理端 sky.jwt.admin,密钥分离+legacy 轮换),三个落点:网关 AuthGlobalFilter → 后端 JwtToken*Interceptor → Agent auth.py(header 名 `token`);Agent 密钥与 Java 同值
- Agent 两代实现并存:`/agent/chat`(旧,内存会话)与 `/agent/workflow`(新,生产主链路);改 Agent 一律基于 workflow 链
- 通信:发帖走 RabbitMQ(post.exchange/post.created)→ STOMP `/topic/newpost`;复习提醒直接 STOMP `/topic/review.{userId}`;前端 STOMP 无 SockJS,brokerURL 直连 `/ws/websocket`

## 雷区(改代码前必读)

1. ~~`/build/bulid` 裸路由~~ **已删除(2026-10-25)**。若需重建数据库,手动执行 `potry-service/src/main/resources/sql/` 下的转储,不要再把重建接口挂回代码。
2. **密钥已出库(2026-10-25)**:全部真实密钥集中在 `potry-service/src/main/resources/application-secret.yml` 与 `poetry-gateway/src/main/resources/application-secret.yml`(均 gitignore)。主配置只留 `${ENV:}` 占位,**secret 文件的键名 = 配置里引用的环境变量名**(JWT_USER_SECRET/JWT_ADMIN_SECRET/MYSQL_PASSWORD/MAIL_PASSWORD/SPRING_AI_API_KEY + spring.rabbitmq.* + sky.alioss.*)。**克隆/换机后必须重建这两个文件(或注入同名环境变量),否则 MySQL/MQ 连不上、JWT 全 401**。轮换密钥只改这两个文件,三端(网关/服务/Agent)同步。
3. **vite 代理陷阱**:`/notice`、`/ai` 前缀与 Vue 路由冲突,后端在这两个前缀下**新增端点必须手工登记** vite.config.ts:23-33,否则 dev 下打到 Vue 页面;`/api/**` 直连 :8000 绕过网关(vite.config.ts:35)。
4. **网关 `/agent/**` 不剥前缀**:Agent 必须自己持有 `/agent/*` 路径;网关→Agent 的路由没有 StripPrefix。
5. **Milvus Lite 文件锁单进程**:跑 build_kb 离线建库前必须先停 Agent 服务(vector_store.py:8-16)。
6. UserMapper.xml 有 `UPDATE your_table` 占位与 `updachatId` 无效 SQL——别当真实现抄。
7. QuestionGameController.score() 信任前端 userId 且单例 sum 计数——并发与作弊双坑,改造勿参照。
8. 拼写双轨:搜代码 `potry` 与 `poetry` 都要试;`/user/book/statr`、`/user/AI/draow`、`selectConmmets`、`messsage` 是历史拼写,改了会破坏前端契约。
9. 根 pom mainClass `com.nhky.MainClass` 指向不存在的类;fastjson 根属性双声明均未生效——以模块 pom 实际声明为准。
10. `dev-notes/`、`evals/`、`naive_agent.py` 是用户有意保留的笔记与教学对照,**不要清理**。
11. **网关 `/agent/**` 已强制用户 JWT(2026-10-25)**:任何新增的走网关的 Agent 调用必须带 `token` 头;直连 :8000 无 token 仍走遗留回退(evals/static 页依赖此模式),生产收紧用 Agent `.env` 的 `AUTH_STRICT=1`。

## 测试基线(2026-10-25)

Agent pytest 429 passed(离线,conftest 全替身;含流式契约 6 例)· 前端 vitest 8 passed · Java 单测 23 passed(点赞幂等 9/JWT 轮换 7/随机 id 池 4/异常契约 3,Mockito 纯离线;src/test 里另有 1 个需真实中间件的 contextLoads,不在默认跑批)。
**注意**:①PoemLunTanServiceLikeTest 的 deadlock_exhausted 用例固化了"toggleLike catch(Exception) 吞死锁耗尽异常并再走一轮降级重试(10 次事务)"的现状——窄化 catch 时同步改断言为 times(5)。②SSE 已改真流式:改 workflow 节点/工具时必须保持 config 透传到 LLM 与 BaseTool 调用,否则 token/工具事件断流(测试替身的 ainvoke 也要带 config=None 形参)。
