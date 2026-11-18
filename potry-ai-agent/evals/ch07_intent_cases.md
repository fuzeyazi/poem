# Ch07 意图路由标注样例(用于 INTENT_PROMPT 真实模型评估)

| 用户问句 | 允许标签 | 说明 |
|---|---|---|
| 查一下《静夜思》的诗库档案 | find_poem | 档案 MCP 接管查诗 |
| 查一下诗人在诗库里的资料 | find_poet | 诗人档案 MCP |
| 帮我建个工单 | other | 建单请求进 Agent,不得归 complaint |
| 我要提交一个纠错单 | other | 建单请求,不得归 complaint |
| 我的纠错单进度怎么样了 | other | 查记录进 Agent |
| 查一下《春望》的判定记录 | other / find_poem | 查判定记录 |
| 答得不对,我不满意 | complaint | 纯抱怨才归投诉 |
| 《静夜思》表达了什么感情 | poem_explain | 赏析走 RAG |
| 唐代有哪些名篇 | find_poem | 按朝代找诗 |
| 这句合不合律 | poem_meter | 格律判定 |
