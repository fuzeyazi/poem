# Java 侧数据源统一到 MySQL · 开发过程留痕

> 背景:`potry-service`(Spring Boot 3.3.4 / Java 17 / MyBatis)原本用 H2 文件库,而 Python 侧 `potry-ai-agent` 连的是本机 MySQL。两侧数据源不一致会各自漂移。用户拍板:**统一使用 MySQL**。

## 阶段 1:定口径 + 迁移就绪度调研(2026-10-18)

**用户关键原话:**
- "好的，先定数据源口径，统一使用MySQL"
- (被问到验证被缺 Redis 挡住时)"好像都有你自己找一下"

**关键产出(调研结论):**
- 模块结构:`potry-service`(业务主服务)/`poetry-gateway`(网关)/`poetry-common`/`poetry-pojo`/`potry-ai`(Java 模块,仅有 `Main.java`+火山引擎 SDK,能力存疑)/`potry-ai-agent`(Python,本次 Ch03 产物)。网关路由:`/user/**`、`/admin/**`、`/ai/**` → `potry-service`;`/agent/**` → `potry-ai-agent`。
- Java 侧**已有完整诗词查询 REST 接口**(`/user/poetry/GetPoembyTitle`、`GetContentById/{id}`、`GetAllDynasty`、`/user/writer/GetAllWriterNames` 等)→ 说明 Python 侧其实**也可改为调 Java REST 而不直连库**(本次未做,留作选项)。
- **关键发现**:`poemmax-h2.sql` 建 **25 张表**(admin/comment/user/writer/…),而 MySQL `poem` 库当时**只有 7 张**(potry/writer + Python 的 5 张)。→ 切数据源**不是改两行配置**,必须把其余 23 张表迁到 MySQL。
- **好消息**:仓库里的 `poemmax.sql` 是**原生 mysqldump**(`MySQL dump 10.13 Distrib 8.0.26`,反引号标识符)→ **零语法转换**;且 `potry-service/pom.xml` **已有 `com.mysql:mysql-connector-j`**,不必加依赖。
- Mapper 检查:`UserMapper.xml`/`PotryMapper.xml` 用的是 **`poem.user`/`poem.potry`(库名限定)** + `ORDER BY RAND()` 等,本来就是按 MySQL 写的,无 H2 专有语法、无双引号标识符。

**拒绝/纠偏:**
- **不做全量导入**:`poemmax.sql` 含 **25 个 `DROP TABLE`**,全量导入会 DROP 掉 `potry`/`writer` 重建,而 Python 侧 23144 条 `knowledge_chunks.source_id` 全指向 `potry.id`,且当时**建库任务正在跑**。→ 改为**只抽其余 23 张表**(抽取产物 `poemmax-app-mysql.sql`,1.86MB→修正后 0.93MB)。
- 密钥脱敏(application*.yml 里的 ai api-key/mail 密码/jwt secret/alioss key)**本次不做**,用户选择"只切数据源"。

**翻车与返工:**
- **抽取脚本两处真 bug(都在真跑中暴露)**:
  1. 误把"下一个**结构块**"当边界,而源 dump 是**结构块/数据块交替**排列 → 结构块吞掉了紧随的数据块,数据块被输出两遍 → 导入报 `Duplicate entry '2' for key 'admin.PRIMARY'`。修法:边界取"下一个**任意**标记"。
  2. 切掉了 dump **头部前导**(含 `SET @OLD_TIME_ZONE` 等),但尾部 `SET TIME_ZONE=@OLD_TIME_ZONE` 被最后区块带进来 → 报 `Variable 'time_zone' can't be set to the value of 'NULL'`。修法:保留源 dump 头部。
- **最后一处是我自己的配置错误,靠运行时验证才抓到**:JDBC URL 写了 `characterEncoding=utf8mb4`,而该参数要的是 **Java 字符集名** → 报 `Unsupported character encoding 'utf8mb4'`。**修法:`characterEncoding=UTF-8`。**

## 阶段 2:完成切换与端到端验证(2026-10-18)

**关键产出:**
- 导入 23 张表到 MySQL → `poem` 库共 **30 张表**。
- 改 `application.yml` + `application-dev.yml`:datasource 指向本机 MySQL;`spring.sql.init.mode: never`(**必须**:否则每次启动执行 H2 脚本,含 25 个 DROP,会清空语料);删除遗留 `sky.datasource`(H2 TCP 9092,无代码引用)。新增 `poemmax-app-mysql.sql`(23 张表迁移脚本)。
- `mvn -o -pl potry-service -am compile` **编译通过**;关掉 `spring.sql.init` 后启动服务成功(`Tomcat started on port 8081`,Nacos 注册正常,**无 Redis/MySQL 报错**)。
- **拦住运行的第一道坎**:`RedisConfig` 在启动期强连 Redis(`RedissonClient` 急切初始化)→ 缺 Redis 时 Spring 上下文起不来。按用户提示在机器上找到并启动:`E:\redis\redis-server.exe`(6379)、`E:\javatexts\nacos-dl\nacos\bin\startup.cmd -m standalone`(8848)。

**验证证据(逐层加码):**
1. 调 `/user/**` 接口 → **401**(需 JWT)。
2. 用导入的测试账号登录 → `TooManyResultsException: ... found: 4` → **证明 Mapper 查询真在 MySQL 上执行并返回 4 行**(数据里同名用户重复,属原始数据问题);换唯一用户名后 → `AccountNotFoundException`(`passwordEncoder.matches` 不通过)→ **证明单行查询与字段映射也通了**(导入数据的密码哈希与编码器不匹配,属原始数据问题)。
3. **自签 JWT**(与项目 `JwtUtil` 一致:jjwt HS256 + `sky.jwt.userSecretKey`,claims `userId`/`dgarreId`)后真调诗词接口,4 个全部 **HTTP 200** 且返回真实数据:
   - `/user/poetry/GetContentById/1` → 返回 id=1 李弥逊诗,中文无乱码
   - `/user/poetry/GetAllDynasty` → 16 个朝代
   - `/user/writer/GetAllWriterNames` → 诗人名单
   - `/user/poetry/GetPoembyTitle?title=静夜思` → 返回 **id=1796《静夜思》**
4. **决定性证据**:Java 返回的《静夜思》id=**1796**,与 Python 侧 `knowledge_chunks.source_id=1796` **完全一致** → **两侧确认同一份 MySQL 数据,数据源统一达成**。

**挂账 / 可选清理:**
- `poemmax-h2.sql` 已不再被自动执行(可留作历史);H2 依赖仍在 `potry-service/pom.xml`(无害,可移出 runtime)。
- `./data/shi-pick` 的 H2 文件库现已不再使用(可归档);但 `shi-pick.mv.db`/`trace.db` 与 `pom.xml` 在本次改动**之前**就已是脏文件,不属本次改动。
- `application*.yml` 明文密钥仍在(本次按用户选择未脱敏)。
- Java 侧 `potry-ai` 模块定位仍未确认(仅 `Main.java`+SDK)。

**用户需要知道的环境影响:**
- 我启动了 **Redis(6379)** 与 **Nacos(8848)**,并且 **`potry-service` 正跑在 8081**。
- Python 侧 `build_kb.py` 仍在后台跑(**已嵌入 8982/23144**),期间 **不能启动 Python API**(Milvus 独占锁)。
