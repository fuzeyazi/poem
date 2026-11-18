"""Workflow 编排依赖容器:节点通过 get_deps() 取用。

采用"模块级单例 + 测试注入钩子"的写法,与 Ch03 的 embeddings.set_embedder /
vector_store.set_store 保持同一仓库惯例(避免把依赖一路穿参进每个节点)。
"""
from context_budget import derive_budget


class WorkflowDeps:
    def __init__(self, settings, llm, tools, knowledge_storage, chat_storage, flywheel=None) -> None:
        self.settings = settings
        self.llm = llm
        self.tools = tools
        self.knowledge_storage = knowledge_storage
        self.chat_storage = chat_storage
        self.flywheel = flywheel                          # Ch08:数据飞轮(可选,后台异步)
        self.budget = derive_budget(settings)          # Ch06:窗口倒推,单一来源
        self.max_iter = settings.max_agent_steps       # MAX_AGENT_STEPS 优先,未配置回退 WORKFLOW_MAX_ITER
        self.max_tokens = settings.workflow_max_tokens


_deps: WorkflowDeps | None = None


def configure(deps: WorkflowDeps | None) -> None:
    """装配/复位编排依赖(传 None 复位;测试注入 stub 亦走此口)。"""
    global _deps
    _deps = deps


def get_deps() -> WorkflowDeps:
    if _deps is None:
        raise RuntimeError("workflow 依赖未装配,请先在 main.py 调用 workflow.deps.configure()")
    return _deps
