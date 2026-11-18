# AI 伴学系统 · 第三章(知识库与向量语义检索)设计

日期:2026-10-14
状态:已定稿(brainstorm 分节设计逐节通过)
落地位置:`potry-ai-agent/`(延续 Ch01/Ch02,就地扩展)

## 1. 目标与范围

把古诗词的内部实现从**关键词查表**升级成**向量语义检索**,三个工具的**入参出参契约保持不变**。

1. **离线建库 · 文档处理**:按标题层级做结构感知切分;超长内容递归切;块间加重叠且裁到最近句号,不留半截话;
2. **离线建库 · 对话挖知识**:一条从历史对话挖知识的定时任务,分批喂 LLM 抽取问答对,先进暂存表、再整体去重入库;
3. **落库结构**:每条知识带 metadata 前缀,拼成一段文本做向量化;
4. **双写落库**:MySQL 建 `knowledge_chunks` 表当原文权威源、Milvus 建 `knowledge` 集合;先写 MySQL 记「待向量化」,再写 Milvus 拿 vector_id 回填、状态转「已向量化」;按主键幂等,挂了能重跑;
5. **在线检索**:问题向量化后到 Milvus 按相似度取 Top-K,替换掉原来的关键词查表实现。

### 非目标(本章不做)

- 关键词召回、混合检索、重排——本章只跑 dense 向量单路;
- 大表格按行切、每块复制表头(诗词库无此类素材,YAGNI,经用户拍板不做);
- 多轮自动循环 Agent Loop(沿用 Ch02 单轮收敛语义);
- 独立嵌入微服务(经用户拍板采方案 1「单进程内嵌」)。

### 验收标准(诗词域映射,经用户确认)

1. 问「那首讲月亮的叫啥」(Ch02 留档的漏召回句)→ **现在能语义召回《静夜思》并答对**;
2. 故意中断建库任务再重跑,**漏向量化的块能被捡起补齐**。

需求原文中的「`query_faq` / 邮费是多少 / 历史客服对话」为客服域模板话术,经用户确认映射为本项目诗词域:`query_faq` → `query_poem`;历史客服对话 → `potry-ai-agent` 的 `conversations`/`messages` 表;验收句沿用 Ch02 留档的漏召回句。

## 2. 技术选型(用户定死,不得自行更换)

| 项 | 结论 | 说明 |
|---|---|---|
| 嵌入模型 | **BGE-M3**(dense 1024 维) | 本地跑模型(用户拍板);模型源走 **modelscope**(实测 `huggingface.co` 与 `hf-mirror.com` 均超时,`modelscope.cn` 可达) |
| 向量库 | **Milvus**(`knowledge` 集合) | 本机 Docker 引擎起不来(WSL 装不上),Milvus 官方 Windows 方案依赖 Docker Compose → 经用户拍板**先用 Milvus Lite 嵌入式文件库**,并已冒烟验证:`pymilvus 3.0.2` + `milvus-lite 3.2.2` 建集合/插入/检索全通过,无需 Docker |
| 原文权威源 | **MySQL**(沿用 Ch02 本机 MySQL 8.4,库 `poem`) | `knowledge_chunks` 表存原文 |
| 上游模型 | 沿用 Ch01/Ch02(DeepSeek,OpenAI 协议,.env 配置) | 对话挖知识复用 `build_llm` |
| 编排 | 沿用 Ch02 单轮 Function Calling | 三工具内部换实现,编排不动 |
| 定时任务 | **APScheduler** | 版本与 API 在实现前经 Context7 核对(3.x 与 4.x API 差异大) |

> **库用法核对要求(用户工作要求 3)**:Milvus/pymilvus 用法已过 Context7 官方文档核对(`MilvusClient` 本地 uri、`create_collection` schema 路径、`insert`/`search`/`query` 签名);BGE-M3 与 APScheduler 的 Context7 文档偏薄,**实现前必须实测核对**并写回 spec 偏差记录。

## 3. 架构与数据流

**架构:方案 1「单进程内嵌」**——FastAPI 进程内懒加载 BGE-M3 + Milvus Lite(本地文件)+ MySQL 权威源;离线建库走**同一个 venv 的 CLI 独立进程**(可中断续跑,不在 FastAPI 进程内跑)。

模块划分(`potry-ai-agent/` 内,延续 Ch01/Ch02 扁平风格):

| 模块 | 动作 | 职责 | 依赖 |
|---|---|---|---|
| `embeddings.py` | Create | BGE-M3 封装:懒加载单例,`embed(texts: list[str]) -> list[list[float]]`(1024 维 dense) | FlagEmbedding/sentence-transformers |
| `vector_store.py` | Create | Milvus Lite 封装:`knowledge` 集合建/写/查;字段 `id`(INT64 主键)、`vector`(1024)、`source_type`、`title`、`writer`、`dynasty` | pymilvus |
| `knowledge.py` | Create | MySQL `knowledge_chunks`(权威源)+ `knowledge_staging`(暂存)模型与读写 | sqlalchemy |
| `chunking.py` | Create | 文档切分:标题层级结构感知 → 超长递归切 → 块间重叠裁到最近句号 | 无 |
| `mining.py` | Create | 对话挖知识:取历史消息 → 分批喂 LLM 抽问答对 → 暂存 → 去重入库 | langchain-openai |
| `build_kb.py` | Create | 离线建库 CLI:potry/writer → 切分 → MySQL(待向量化)→ 嵌入 → Milvus → 回填 + 已向量化;支持续跑 | 上述模块 |
| `scheduler.py` | Create | APScheduler cron,挂 FastAPI lifespan;手动触发走 CLI | apscheduler |
| `config.py` | Modify | 追加 §3.1 配置项 | 无 |
| `tools/poetry_tools.py` | Modify | 三工具内部改向量检索,**签名与返回结构不变** | 上述模块 |
| `main.py` | Modify | 装配 embedding/vector store/scheduler;`/agent/chat` 不动 | fastapi |

### 3.1 新增配置项(`config.py` + `.env`)

| 配置 | 默认 | 说明 |
|---|---|---|
| `EMBEDDING_MODEL_PATH` | 无(必填 fail-fast) | 本地 BGE-M3 模型目录 |
| `MILVUS_DB_PATH` | `potry-ai-agent/milvus_data/knowledge.db` | Milvus Lite 文件 |
| `MILVUS_COLLECTION` | `knowledge` | 集合名 |
| `MILVUS_TOPK` | `5` | 在线检索 Top-K |
| `SIMILARITY_THRESHOLD` | `0.5` | 低于阈值视为未命中(found:false) |
| `CHUNK_SIZE` | `400` | 块大小上限(字) |
| `CHUNK_OVERLAP` | `60` | 块间重叠(字) |
| `MINING_BATCH_SIZE` | `20` | 挖知识每批对话轮数 |
| `MINING_CRON` | `0 3 * * *` | 挖知识定时 cron |

模型目录与 Milvus 文件**不入 git**(加入 `.gitignore`)。

### 3.2 离线建库数据流

```
build_kb.py
  → 读 potry 全表 + writer 全表
  → chunking:每行构成结构化文档 → 按标题层级切 → 超长递归切 → 重叠裁句号
  → 每块拼 metadata 前缀得 chunk_text
  → MySQL upsert knowledge_chunks(status='pending'),按唯一键幂等
  → (续跑点:重跑时只取 status='pending' 的块)
  → embeddings.embed(chunk_text 批量)
  → Milvus upsert(主键 = MySQL 行 id;按主键幂等)
  → 回填 vector_id + status='embedded'
```

### 3.3 在线检索数据流(工具契约不变)

```
query_poem(keyword)
  → embeddings.embed([keyword])
  → Milvus search(topk=MILVUS_TOPK, COSINE, filter source_type=="poem")
  → 命中块的 id(= knowledge_chunks.id)
  → MySQL 读 knowledge_chunks 该行,拿 source_id + section/raw_text
  → 回查 potry WHERE id == source_id
  → 组装原契约 dict 返回
```

命中为空或最高相似度低于 `SIMILARITY_THRESHOLD` → `{"ok":true,"found":false}`。Milvus 的 COSINE 返回**相似度**(越大越相似),阈值比较为「大于等于」。

`meta → tool_status* → token* → done` 的 SSE 契约不变,聊天页不改(Ch02 的「来源标识」继续有效)。

## 4. 离线建库 · 文档处理(`chunking.py`)

**输入**:`potry` 每行 → 一篇结构化文档。

文档层级:`# {诗题}`(一级)→ `## 原文`(content)、`## 译文`(translation)、`## 赏析`(shangxi)、`## 注释`(remark);`dynasty`/`writer`/`type` 作为文档属性(不单独成块)。

**切分规则**:

1. **结构感知**:按 `##` 子节切,一个子节 = 一个候选块;诗题作块前缀标题,**不单独成块**;
2. **超长递归切**:块超过 `CHUNK_SIZE` 时,按句号/换行递归切到 ≤ `CHUNK_SIZE`;
3. **重叠与裁句**:相邻块保留 `CHUNK_OVERLAP` 重叠;**重叠边界向前裁到最近句号,不留半截话**;找不到句号则整段不裁;
4. **块向量化文本** = `{title}|{dynasty}|{writer}|{type}\n{子节名}\n{正文}`(metadata 前缀,用户拍板),metadata 四字段随块入库。

**大表格按行切:本章不做(YAGNI,已拍板)。**

## 5. 离线建库 · 对话挖知识(`mining.py`)

- **数据源**:`conversations`/`messages`(Ch02 已有)。用独立单行表 `knowledge_mining_cursor`(`last_mined_message_id`)记**已挖水位**,增量取未挖会话;
- **分批**:按 `MINING_BATCH_SIZE` 取 user+assistant 配对 → 喂 LLM(复用 `build_llm`)→ 要求输出 JSON 数组 `[{question, answer, tags}]`;抽不到返回空数组;
- **暂存**:先落 `knowledge_staging`(question/answer/tags/source_session_id/created_at);
- **整体去重**:挖完整轮后,对暂存全表按**归一化 question**(去空白/标点、小写)去重,并剔除与既有 `knowledge_chunks`(`source_type='qa'`)重复的;去重后 upsert 进 `knowledge_chunks`(`status='pending'`)。

  **向量化的责任划分(实现后明确)**:定时挖知识**只负责产出 `pending` 块,不内联做嵌入**——嵌入是 CPU 重活(实测 BGE-M3 约 0.39 s/块),若塞进每日定时任务会长时间占满 CPU、并与 API 抢资源。因此 qa 块的向量化与诗词块统一走 **`build_kb.py --skip-chunk`**(只补 `pending`,不进 Milvus 前先停 API 释放 Milvus Lite 的进程独占锁)。运行手册须写明"挖完需补跑一次 `build_kb --skip-chunk`"。
- **定时**:APScheduler `CronTrigger`(`MINING_CRON`);**手动触发走 CLI**(`python mining.py`),**不新增 HTTP 路由**(保持 API 面最小改动)。

## 6. 落库结构

### 6.1 `knowledge_chunks`(MySQL,原文权威源)

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | bigint PK auto | Milvus 侧主键同此值 |
| `source_type` | varchar(16) | `poem` / `poet` / `qa` |
| `source_id` | bigint | 来源业务键(poem→potry.id;poet→writer.id;qa→staging.id) |
| `chunk_text` | text | 向量化用文本(带 metadata 前缀) |
| `raw_text` | text | 原文正文(权威原文,回查用) |
| `title` | varchar(255) | metadata |
| `writer` | varchar(100) | metadata(诗人名;与源表 `potry.writer` 同宽) |
| `dynasty` | varchar(32) | metadata |
| `section` | varchar(32) | 子节名(原文/译文/赏析/注释;qa 为固定值) |
| `seq` | int | 同来源内块序号 |
| `status` | varchar(16) | `pending`(待向量化)/ `embedded`(已向量化) |
| `vector_id` | bigint null | Milvus 回填 |
| `created_at` / `updated_at` | datetime | |

**幂等**:唯一索引 `(source_type, source_id, section, seq)` + upsert,重跑不重复插入。

按 `source_type` 的三列取值约定:

| source_type | source_id | section | seq | raw_text |
|---|---|---|---|---|
| `poem` | `potry.id` | 子节名(原文/译文/赏析/注释) | 同来源内块序号(0 起) | 该子节正文 |
| `poet` | `writer.id` | 简介节名(简简介/详简介) | 同来源内块序号(0 起) | 该子节正文 |
| `qa` | `knowledge_staging.id` | 固定 `qa` | 固定 `0` | 抽取的 answer |

### 6.2 `knowledge_staging`(暂存表)

| 列 | 说明 |
|---|---|
| `id` | bigint PK auto |
| `question` / `answer` | 抽取的问答对 |
| `tags` | 标签(JSON 文本) |
| `source_session_id` | 来源会话 |
| `created_at` | |

另设**已挖水位表** `knowledge_mining_cursor`(单行):`last_mined_message_id` bigint + `updated_at`,保证只挖一次、可续跑。

### 6.3 双写顺序与幂等

先写 MySQL 记 `pending` → 拿主键 → 嵌入 → Milvus 插入(主键同 MySQL id)→ 回填 `vector_id`、状态转 `embedded`。

**续跑**:`SELECT ... WHERE status='pending'` 分批补做。

> ✅ **已实测确认(2026-10-14,原为"未验证风险项")**:Milvus Lite 用**操作系统级文件锁**(Windows `msvcrt.locking`),**同一 `.db` 同一时刻只允许一个进程打开**——第二个进程无论读还是写,都在 `MilvusClient(db_path)` **构造期**抛 `DataDirLockedError`(pymilvus 包装为 `ConnectionConfigException`,属 `MilvusException` 子类);写完成后释放锁,数据跨进程持久可见。
>
> 因此运行模型是硬约束:**建库 CLI 必须独占运行(此时 API 服务不能开着)**;API 侧在线检索与进程内定时 mining 共享同一单例 client(同进程内无冲突)。锁冲突时由**工具层**捕获 `MilvusException` 降级返回 `ok:false`,服务不崩。

### 6.4 Milvus `knowledge` 集合

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | INT64(主键) | 同 MySQL `knowledge_chunks.id` |
| `vector` | FLOAT_VECTOR(1024) | BGE-M3 dense |
| `source_type` / `title` / `writer` / `dynasty` | VARCHAR | 过滤与展示用 metadata |

索引:`AUTOINDEX` + `COSINE`(Milvus Lite 数据量小,够用)。

## 7. 在线检索(三个工具都换,契约不变)

| 工具 | 签名(不变) | 内部实现(换) | 返回(不变) |
|---|---|---|---|
| `query_poem` | `keyword: str` | embed → Milvus search(topk, COSINE, filter `source_type=="poem"`)→ 回查 `potry` 行 | `{"ok":true,"found":true,"poem":{title,dynasty,writer,type,content,translation,shangxi,remark}}`;未命中/Top-K 空/低于阈值 → `{"ok":true,"found":false}` |
| `query_poet` | `name: str` | embed → Milvus search(filter `source_type=="poet"`)→ 按命中 `id` 回查 `knowledge_chunks` 拿 `source_id` → 回查 `writer` 行;`works` 仍按 `Potry.writer == name` 取 5 条 | 同 Ch02(name/simpleIntro/detailIntro/headImageUrl + works) |
| `query_dynasty_poems` | `dynasty: str` | **Milvus filter 查询**(`filter dynasty == X`,非向量排序)取块 → 按 `title` 去重后取标题 | 同 Ch02(`count` + `titles`) |

- 截断规则(`_MAX_CONTENT=300` / `_MAX_TITLES=20`)保持不变;
- `query_poet` 走向量要求建库管线**同时索引 `writer` 表**(`source_type='poet'`,`simpleIntro`/`detailIntro` 各成子节);
- `query_dynasty_poems` 是精确枚举列表,向量排序无意义 → 走 Milvus 过滤查询(经用户拍板);同一首诗会切成多块,故须**按 `title` 去重**后再组标题列表(实现后明确:Milvus 集合只存 `id/source_type/title/writer/dynasty`、**未存 `source_id`**,故只能按 title 去重;极少数"同名不同诗"会被并成一条,属可接受的召回取舍);块数不足时**翻倍重扫**(`_DYNASTY_SCAN_MAX` 上限),避免长诗多块把标题挤没;
- 三个工具在 Milvus 不可用或嵌入失败时,返回 `{"ok":false,"error":...}`,契约与 Ch02 一致。

## 8. 错误处理与降级

- 工具内部异常一律返回 `{"ok":false,"error":...}`(沿用 Ch02 ToolRegistry 契约),不抛;
- 嵌入模型加载失败 / Milvus 不可用 → 降级为该失败分支,服务本身不崩;
- 建库脚本:单块嵌入失败跳过并保持 `pending`,结束打印统计(成功/失败/待重跑),可重跑补齐;
- LLM 抽取非 JSON → 该批跳过并记日志,不污染暂存表;
- Milvus Lite 文件锁冲突 → 工具降级返回 `ok:false`;
- 日志不打印密钥;异常串截断 `[:200]`。

## 9. 测试与验证策略

**TDD(可单测代码)**:

- `chunking`:结构切分 / 超长递归切 / 重叠裁句号(含找不到句号的兜底);
- `knowledge`:upsert 幂等、按 `status` 取待处理、staging 去重;
- `vector_store`:用 Milvus Lite 临时文件真实建集合/写/查;
- 三工具契约:**Fake embedder + Fake Milvus 注入**,断言出入参形状与 Ch02 完全一致;
- `build_kb` 续跑:先造 `pending` 块,断言重跑后 `pending` 归零。

**评估样例 / 标注样例(纯 Prompt、数据类,替代 TDD 那步)**:

- 对话挖知识 Prompt:一批**标注样例**(历史对话片段 → 期望抽取的问答对),跑真实 LLM 比对抽取质量;
- 端到端检索:评估集(换说法句 / 原句 / 负例),比对 Milvus Top-K 命中与最终回答。

**验收**:① 「那首讲月亮的叫啥」语义召回《静夜思》并答对;② 中断建库重跑,`pending` 归零且 Milvus 条目数与 MySQL `embedded` 数一致。

**回归**:Ch01/Ch02 全量 44 条测试保持绿。注意 pymilvus 安装引入了 `numpy 2.4.6`/`pandas 3.0.6`/`faiss-cpu`/`pyarrow`,**需复核不破坏现有环境**。

## 10. 已确认的决策记录

| 决策点 | 结论 |
|---|---|
| 领域映射 | 需求文本的「query_faq / 邮费 / 客服对话」为客服模板话术,经用户确认映射为本项目**诗词域** |
| 知识来源(文档) | **`potry` 表**(每首诗词当一篇结构化文档);`writer` 表一并索引以支撑 `query_poet` |
| 向量化文本 | **带 metadata 前缀拼接**(`{title}\|{dynasty}\|{writer}\|{type}\n{子节名}\n{正文}`),需求原文缺失的字段名即 metadata |
| Milvus 部署冲突 | 本机 Docker 引擎起不来(WSL 装不上),经用户拍板**先用 Milvus Lite**;已冒烟验证通过 |
| BGE-M3 运行方式 | **本地跑模型**(用户拍板);因 HF/hf-mirror 被墙,模型源改 **modelscope** |
| 架构方案 | **方案 1 单进程内嵌**(用户拍板);建库作为执行细则永远走 CLI 离线跑 |
| 大表格按行切 | **不做**(YAGNI,用户拍板) |
| 升级范围 | **三个工具都换**(用户拍板) |
| `query_dynasty_poems` | 走 **Milvus filter 查询**(非向量排序),保留精确枚举语义(用户拍板) |
| 定时任务 | **APScheduler 进程内**;手动触发走 CLI,不新增 HTTP 路由(用户拍板) |
| 验收句 | 沿用 Ch02 漏召回句「那首讲月亮的叫啥」(用户拍板) |
| 本章检索范围 | 只跑 dense 向量单路,不含关键词/混合/重排 |
