# Ch02 工具调用评估样例(真实模型人工比对)

前置:服务 + 本机 MySQL(poem 库)已起,`curl` 打 `/agent/chat`(或浏览器聊天页)。

| # | 用户输入 | 期望工具 | 期望行为 | 通过 |
|---|---|---|---|---|
| 1 | 《静夜思》是谁写的 | query_poem | 带 tool_status 帧,回答"李白"且基于返回内容 | ✅(2026-10-14,deepseek-chat) |
| 2 | 李白是什么样的诗人 | query_poet | 带 tool_status 帧,按 writer 表简介作答 | ✅(2026-10-14,deepseek-chat) |
| 3 | 那首讲月亮的叫啥 | query_poem(可能) | 关键词查不到,如实说不确定并请补充线索(漏召回,预期) | ✅(2026-10-14,deepseek-chat) |
| 4 | 今天天气真好 | (不调工具) | 无 tool_status 帧,直接流式闲聊回应并拉回诗词 | ✅(2026-10-14,deepseek-chat) |

实测记录(2026-10-14,与 Task 10 验收同批数据):
- #1:事件序列 `meta → tool_status(query_poem) → token* → done`,回答"乃唐代大诗人李白所作"并引全诗。
- #2:tool_status(tool=query_poet),回答含库内简介(701—762、字太白、号青莲居士、诗仙)。
- #3:query_poem(keyword=明月)命中含"明月"的他诗(裴相如《游洞霄山》),模型如实说"单凭一词实难锁定"并追问五言/七言、诗句、主题等线索——漏召回行为留档,语义检索留给下一步升级(RAG,本章不做)。
- #4:无 tool_status 帧,纯闲聊回答。

结论:4/4 通过,prompt 无需微调。
