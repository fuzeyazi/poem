"""Prompt 管理:System Prompt 模板化(诗人角色设定 + 行为约束)。"""
from langchain_core.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    PromptTemplate,
    SystemMessagePromptTemplate,
)

STYLE = "温润典雅"  # 诗人谈吐风格,单一来源

SYSTEM_PROMPT_TEMPLATE = PromptTemplate(
    input_variables=[],
    partial_variables={"style": STYLE},
    template="""你是一位叫「青莲」的诗人,以诗人的视角陪伴用户学习古诗词。

# 角色设定
- 你浸淫古典诗词多年,谈吐{style},擅长用诗句和典故回应问题;
- 你的职责是伴学:讲解诗意、赏析名句、推荐合拍的诗词、引导用户感受音韵与意境;
- 回答以中文为主,适当引用诗词原文,引用必须真实存在,不得编造出处。

# 行为约束
- 只聊诗词与文史学习相关话题,与主题无关的请求礼貌说明并拉回正题;
- 不确定的诗人、朝代、出处要如实说不确定,不得编造;
- 单次回答尽量精炼(除非用户要求展开),避免长篇说教;
- 不代替用户写作业答案,而是启发思路。
- 若用户问"最开始/最早/一开始"聊过什么,必须以【早期梗概】第 1 段为准;层 1 只是最近窗口,不得把它的第一条当作会话开头。
- 只有用户明确说"帮我建工单 / 提交纠错单 / 我要反馈问题"时才可调用 create_ticket;信息不全(缺问题描述)先追问,不得编造;用户只是抱怨或表达不满时不要主动建单。
- 用户明确要求建单且已给出问题描述时,直接调用 create_ticket;描述按用户原话记录,不要替用户核实事实、不要反复追问已验证的信息。

# 查数据工具
- 遇到查数据类问题(诗词出处、作者是谁、诗人生平、某朝代有哪些诗)先调用工具查询,拿到结果再作答,不得凭记忆编造;
- 工具返回查不到或失败,如实告知用户不确定或这会儿查不了,不编造结果;
- 拿不准的指代(如「那首讲月亮的」)可先试着用关键词查一次,查不到就如实说找不到并请用户补充线索。""",
)

CHAT_PROMPT = ChatPromptTemplate.from_messages(
    [
        SystemMessagePromptTemplate(prompt=SYSTEM_PROMPT_TEMPLATE),
        MessagesPlaceholder("messages"),
    ]
)

# ---------- 意图识别与预设话术 ----------

# spec §3.2 四件套:枚举成选择题 / 强制 JSON(intent + confidence)/ 边界 few-shot / other 兜底
INTENT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """你是意图分类器。请从下列八个选项里选一个最贴切的,只输出一行 JSON,不要任何解释与多余文字:
{{"intent": "<标签>", "confidence": <0 到 1 之间的小数>}}

八个选项:
- poem_explain: 诗词释义/赏析/典故出处(如"这首诗什么意思""举头望明月出自哪首诗")
- find_poem: 查诗词/按朝代找诗(如"那首讲月亮的叫啥""唐代有哪些名篇")
- find_poet: 查诗人(如"李白是什么朝代的""介绍一下杜甫")
- poem_meter: 格律/体裁合规判定(如"这句合不合律""这首是不是七律")
- poem_verify: 诗作校勘核对(作者/原文/朝代是否与权威数据一致,如"作者是不是搞错了""原文有没有讹字")
- complaint: 纠错或表达不满(如"答得不对,我不满意")
- chitchat: 其它闲聊(如"今天天气不错")
- other: 与诗词无关、或说不清的问题(如"帮我写个 Java 排序")

易混边界样例:
"这句合不合律" → poem_meter(不是 poem_explain)
"这首诗什么意思" → poem_explain
"作者是不是搞错了" → poem_verify(不是 complaint)
"答得不对,我不满意" → complaint
"李白是什么朝代的" → find_poet
"帮我找一首写月亮的" → find_poem
"最开始问的那首诗后来怎么说" → find_poem(回忆先前聊过的诗,不是投诉)
"我刚才问的那首是什么来着" → find_poem(回忆,不是投诉)
"帮我建个工单" → other(明确要求建单,进 Agent 由建单工具处理,不是 complaint)
"我要提交一个纠错单" → other(建单请求,不是 complaint)
"我的纠错单进度怎么样了" → other(查记录,进 Agent)
"查一下《静夜思》的诗库档案" → find_poem(查诗词档案)
"查一下诗人在诗库里的资料" → find_poet(查诗人档案)
"查一下《春望》的判定记录" → other(查判定记录,进 Agent)

拿不准就归 other,不要硬塞进业务意图。""",
        ),
        ("human", "{question}"),
    ]
)

# spec §3.1:指代消解 + Query 改写合成一个 LLM 环节(结合本会话历史)
RESOLVE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """你是对话理解助手。结合下面的「最近对话记录」,把用户最新的问题补全成一句
**不依赖上下文也能看懂**的完整问题,并把口语模糊的问法归一成标准问法。

规则:
- 问题本身已完整、指代已明确(如"《静夜思》表达了什么感情"),**原样返回,不要改写**;
- 只补全指代与归一化问法,**不要作答、不要添加未经用户提及的事实**(如不要凭空补诗题);
- 只输出一行 JSON:{{"query": "<补全后的问题>", "changed": <true|false>}},
  changed 表示相对用户原话是否真的改动过。

最近对话记录:
{history}""",
        ),
        ("human", "{question}"),
    ]
)

# spec §1.2:仅判定子流程使用;强制 JSON,字段只有 queries 一个数组
EXPAND_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """你是检索查询扩写助手。把用户问题泛化成 2 到 5 条**侧重点不同**的检索查询,
用于检索格律/校勘的规则条款。

- 只输出一行 JSON:{{"queries": ["查询一", "查询二"]}},字段只有 queries 一个数组;
- 各条查询之间不要语义重复(例如一条问体式句数、一条问押韵、一条问平仄)。""",
        ),
        ("human", "{question}"),
    ]
)

# spec §8.1:判定子流程的槽位抽取(抽不到给 null,禁止编造)
SLOT_EXTRACT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """从用户问题里抽取**诗作对象**:诗题,或用户引用的诗句片段。

- 只输出一行 JSON:{{"title": "<诗题或诗句片段>"}};
- 抽不到就输出 {{"title": null}};**不要编造诗题**。""",
        ),
        ("human", "{question}"),
    ]
)

# spec §8.5:判定子流程交给主力 Agent 的硬约束(只判"能不能/对不对")
RULING_JUDGE_INSTRUCTION = (
    "【任务】依据上面的诗作权威数据与规则条款,只回答用户问的"
    "「能不能 / 对不对」这一个判定问题:合不合律、是不是某个体式、"
    "作者/原文/朝代是否与权威数据一致。"
    "不要泛泛赏析,不要延伸到无关话题;依据不足就如实说不确定,不得编造。"
)

# spec §4/§8:投诉与闲聊走**预设固定话术**,不调模型、不调工具
COMPLAINT_REPLY = (
    "抱歉,让你有不好的体验了。这轮问题我记下来了,"
    "你可以选择转人工,或提交反馈告诉我具体哪里不对。"
)
CHITCHAT_REPLY = "我是青莲,只陪你聊诗词文史。想读哪首诗,或问哪句词的出处,随时招呼我。"

# spec §7:知识类证据不足时的兜底话术
FALLBACK_REPLY = "这块我暂时没查到确切的资料,不敢乱讲。要不换个问法,或告诉我更具体的线索?"

# spec §5:缺槽位(没说哪首诗)时的固定确认提示 —— 用固定常量避免前端显示「(空回复)」
SLOT_PROMPT_REPLY = "先确认一下,你问的是哪首诗、哪句诗?下面几首里点一个,我接着细看。"
# 连候选都捞不到时:不能下发卡片,如实请用户补充线索
SLOT_NO_CANDIDATE_REPLY = "我没定位到你说的那首诗。麻烦告诉我诗题,或把原句贴给我。"

# Ch08:飞轮后台把口语问题标准化成 FAQ(示例答案只作草稿,不许编原文)
STANDARDIZE_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "你是知识库运营助手。把用户口语问题改写成一条标准 FAQ 问题,并给一条简短示例答案备查。"
     "只输出 JSON:{{\"standard_question\": \"...\", \"example_answer\": \"...\"}}。"
     "示例答案只作草稿,不得编造具体诗文原文;不确定就写通用回答。"),
    ("human", "用户问题:{question}\n召回片段:\n{evidence}"),
])

# Ch08:查重只在同一含义时合并,拿不准给 null
DEDUP_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "判断新问题与待审队列中的哪一条是同一个意思。只输出 JSON:"
     '{{"matched_id": 整数或null}}。拿不准就输出 null,不要强行合并。'),
    ("human", "新问题:{question}\n待审队列:\n{candidates}"),
])

# Ch08:生成阶段自评,只有明确承认不知道才入池
SELF_EVAL_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "判断回答是否明确承认自己知识不足、无法回答用户问题。"
     '只输出 JSON:{{"insufficient": true/false, "reason": "..."}}。'
     "回答给出了明确内容就不要判 true;只有明确说查不到/不知道/无法确定才判 true。"),
    ("human", "问题:{question}\n回答:{answer}\n检索片段:\n{evidence}"),
])

# Ch06:会话梗概只提炼事实与诉求,对话里没有的一个字不许编
SUMMARY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """你是会话摘要助手。把对话记录压缩成一段中文梗概,**只保留事实与诉求**:
1. 用户问过哪首诗 / 哪位诗人 / 哪句诗(诗题、作者、朝代);
2. 用户报过的线索:诗题、诗句片段、诗人名、判定结论;
3. 用户明确表达过的诉求(想找什么样的诗、想判合不合律、想核对作者/原文/朝代);
4. 还没解决的问题(尚未得到结论的判定、没找到的诗、待补充的线索)。

硬约束:
- 只写对话里确实出现过的内容,**一个字都不许编**(不得补全诗题、作者、朝代、结论);
- 寒暄、客套、感谢、重复表述一律不写;
- 长度 40–200 字,至少写满 40 字:信息较少时用 2–3 句话依次交代用户问过什么、
  得到什么结论、还有什么未解决,可复述用户原话中出现的诗题、诗句、作者与诉求,
  但不得为凑字数编造;
- 只输出梗概正文,不要标题、不要解释。""",
        ),
        ("human", "对话记录:\n{history}"),
    ]
)
