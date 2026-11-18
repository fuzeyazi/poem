"""诗词 AI 服务（potry-ai-agent）。

职责：承载 AI 能力（意图识别 / RAG 诗词检索 / Agent 编排 / 出题）。
对外提供 FastAPI 接口，启动时注册到 Nacos，
由 poetry-gateway 按 lb://potry-ai-agent 路由转发。

启动：
    uvicorn main:app --host 0.0.0.0 --port 8000
"""
import asyncio
import json
import os
import threading
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

import nacos
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.sse import EventSourceResponse, format_sse_event
from langgraph.types import Command
from pydantic import BaseModel
from sqlalchemy.orm import sessionmaker

from app_storage import AppBase, AppStorage
from chat_service import ChatService, build_llm
from config import load_settings
from context_log import log_budget
from audit_api import create_audit_router
from kb_sync_api import create_kb_sync_router
from cost_api import create_cost_router
from db import get_engine
from flywheel import FlywheelService, snapshot_hits
from knowledge import KnowledgeBase, KnowledgeStorage, ensure_ch08_schema
from memory import SessionStore
from observability import current_trace_id, finish_turn, get_handler, trace_turn
from review_api import create_review_router
from scheduler import build_scheduler
from self_eval import self_eval_after_turn
from storage import ChatBase, ChatStorage, ensure_schema
from summarizer import shutdown as shutdown_summaries
from auth import resolve_user_id
from tools.poetry_tools import query_dynasty_poems, query_poem, query_poet
from tools.forum_tools import draft_forum_post
from tools.user_tools import get_my_collection, get_study_plan
from tools.registry import ToolRegistry
from tools.ticket_tool import create_ticket
from tool_system.audit import AuditWriter
from tool_system.catalog import ToolCatalog
from tool_system.engine import ToolEngine
from tool_system.mcp_provider import McpProvider
from workflow.deps import WorkflowDeps, configure as configure_workflow
from workflow.graph import build_graph, open_checkpointer

NACOS_SERVER = os.getenv("NACOS_SERVER", "localhost:8848")
SERVICE_NAME = "potry-ai-agent"
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8000"))
SERVICE_IP = os.getenv("SERVICE_IP", "127.0.0.1")
HEARTBEAT_INTERVAL = 5  # 秒，需小于 Nacos 的 15s 心跳超时

nacos_client = nacos.NacosClient(NACOS_SERVER)

# 停止心跳线程的信号
_stop_heartbeat = threading.Event()


def _heartbeat_loop() -> None:
    """周期性向 Nacos 发送心跳。

    nacos-sdk-python 注册临时实例后不会自动续约，若不手动发心跳，
    实例会在 15s 后被标记为不健康、30s 后被剔除。
    """
    while not _stop_heartbeat.is_set():
        try:
            nacos_client.send_heartbeat(SERVICE_NAME, SERVICE_IP, SERVICE_PORT)
        except Exception as exc:  # noqa: BLE001 - 心跳失败仅记录，不中断循环
            print(f"[nacos] 心跳发送失败: {exc}")
        _stop_heartbeat.wait(HEARTBEAT_INTERVAL)


def init_db(target_engine) -> None:
    """建表(幂等):对话表 + 知识库表。MySQL 未起时打印中文告警后继续,不阻断服务启动。"""
    try:
        ChatBase.metadata.create_all(target_engine)
        AppBase.metadata.create_all(target_engine)
        KnowledgeBase.metadata.create_all(target_engine)
        print("[db] 表结构就绪(对话 + 知识库 + 应用表)")
    except Exception as exc:  # noqa: BLE001 - 建表失败仅告警,服务照常起,查询时才暴露错误
        print(f"[db] 建表失败(MySQL 不可用?): {str(exc)[:200]}")


def warm_up() -> None:
    """预热嵌入模型与向量库。

    冷启动加载 BGE-M3(约 2.3GB)远超工具体 5s 超时,若等首个请求才懒加载,
    首次工具调用会先被 ToolRegistry 的 asyncio.wait_for 判超时(且取消不了加载线程)。
    故在服务启动时预热;失败仅告警,工具走契约里的降级分支(ok:false)。
    """
    try:
        from embeddings import get_embedder
        from vector_store import get_store

        get_embedder()
        get_store()
        print("[warmup] 嵌入模型与向量库已就绪")
    except Exception as exc:  # noqa: BLE001
        print(f"[warmup] 预热失败(工具将降级为 ok:false): {str(exc)[:200]}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期:启动时建表、预热、起定时任务、注册到 Nacos;关闭时逐项回收。"""
    init_db(engine)
    try:
        ensure_schema(engine)
    except Exception as exc:  # noqa: BLE001 - 迁移失败与 init_db 同语义:仅告警不阻断启动
        print(f"[db] 迁移失败(MySQL 不可用?): {str(exc)[:200]}")
    try:
        ensure_ch08_schema(engine)
    except Exception as exc:  # noqa: BLE001 - Ch08 列迁移失败仅告警
        print(f"[db] ch08 迁移失败(MySQL 不可用?): {str(exc)[:200]}")
    if not os.getenv("MAX_AGENT_STEPS"):
        print(f"[ctx] MAX_AGENT_STEPS 未配置,回退 WORKFLOW_MAX_ITER={settings.workflow_max_iter}")
    log_budget(workflow_deps.budget, settings.turn_steady_tokens)
    flywheel_service.attach_loop(asyncio.get_running_loop())
    if settings.warmup_on_start:
        warm_up()
    else:
        print("[warmup] 已跳过预热(WARMUP_ON_START 关闭)")
    scheduler = None
    try:
        scheduler = build_scheduler(settings)
        scheduler.start()
        print(f"[scheduler] 挖知识定时任务已启动(cron={settings.mining_cron})")
    except Exception as exc:  # noqa: BLE001 - 定时任务起不来不影响聊天(含非法 cron)
        print(f"[scheduler] 启动失败(不影响聊天): {str(exc)[:200]}")
    try:
        nacos_client.add_naming_instance(SERVICE_NAME, SERVICE_IP, SERVICE_PORT)
        print(f"[nacos] 已注册 {SERVICE_NAME} -> {SERVICE_IP}:{SERVICE_PORT}")
        _stop_heartbeat.clear()
        threading.Thread(target=_heartbeat_loop, daemon=True).start()
        print("[nacos] 心跳线程已启动")
    except Exception as exc:  # noqa: BLE001 - 注册失败不应阻断服务启动
        print(f"[nacos] 注册失败: {exc}")
    global _workflow, _checkpoint_conn
    try:
        saver, _checkpoint_conn = await open_checkpointer(settings.workflow_checkpoint_path)
        _workflow = build_graph(saver)
        print(f"[wf] 图已编译(checkpointer=sqlite:{settings.workflow_checkpoint_path})")
    except Exception as exc:  # noqa: BLE001 - 装配失败降级:接口 503,服务照常起
        _workflow = None
        print(f"[wf] 图装配失败(接口将 503): {str(exc)[:200]}")
    yield
    if _checkpoint_conn is not None:
        try:
            await _checkpoint_conn.close()
            print("[wf] checkpointer 连接已关闭")
        except Exception as exc:  # noqa: BLE001
            print(f"[wf] checkpointer 关闭失败: {str(exc)[:200]}")
    if scheduler is not None:
        try:
            scheduler.shutdown(wait=False)
            print("[scheduler] 定时任务已停止")
        except Exception as exc:  # noqa: BLE001
            print(f"[scheduler] 停止失败: {str(exc)[:200]}")
    try:
        await flywheel_service.shutdown()
        print("[flywheel] 后台任务已取消")
    except Exception as exc:  # noqa: BLE001
        print(f"[flywheel] 关闭失败: {str(exc)[:200]}")
    for task in list(_self_eval_tasks):
        task.cancel()
    _self_eval_tasks.clear()
    await shutdown_summaries()
    print("[summary] 后台摘要任务已取消")
    _stop_heartbeat.set()
    try:
        nacos_client.remove_naming_instance(SERVICE_NAME, SERVICE_IP, SERVICE_PORT)
        print(f"[nacos] 已注销 {SERVICE_NAME}")
    except Exception as exc:  # noqa: BLE001
        print(f"[nacos] 注销失败: {exc}")


app = FastAPI(title="诗词 AI 服务", version="0.1.0", lifespan=lifespan)

# Prometheus 指标(与 Java 侧 Actuator 同栈,统一大盘观测; /metrics)
# Prometheus 指标(与 Java 侧 Actuator 同栈,统一大盘观测; /metrics)
# 自写middleware替代 prometheus-fastapi-instrumentator: 7.x在当前FastAPI上遍历路由
# 遇 _IncludedRouter(无path属性)抛AttributeError,致全部admin API 500(2026-10-25实测)。
# 指标命名沿用 instrumentator 约定(http_request_duration_seconds),Grafana面板无需改。
import time as _prom_time
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.responses import Response as _PromResponse

_prom_duration = Histogram(
    "http_request_duration_seconds", "HTTP request duration in seconds", ["method", "handler"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
_prom_total = Counter("http_requests_total", "HTTP requests total", ["method", "handler", "status"])


@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    if request.url.path == "/metrics":
        return _PromResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
    t0 = _prom_time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        _prom_total.labels(request.method, request.url.path, "500").inc()
        _prom_duration.labels(request.method, request.url.path).observe(_prom_time.perf_counter() - t0)
        raise
    route = request.scope.get("route")
    handler = getattr(route, "path", request.url.path)   # getattr兜底,防路由对象无path
    _prom_total.labels(request.method, handler, str(response.status_code)).inc()
    _prom_duration.labels(request.method, handler).observe(_prom_time.perf_counter() - t0)
    return response


class ChatRequest(BaseModel):
    userId: str | None = None     # Ch06 会话归属:落库与会话列表按此过滤
    sessionId: str | None = None
    message: str
    selectedPoemId: int | None = None   # Ch05 两段式续跑:用户点选的诗词卡片 id


# 模块级装配:配置 fail-fast,会话与模型管线就绪;建表移到 lifespan(init_db,失败不阻断启动)
settings = load_settings()
engine = get_engine(settings.mysql_url)  # lazy,不触库
session_factory = sessionmaker(bind=engine)
storage = ChatStorage(session_factory)
registry = ToolRegistry(
    timeout=settings.tool_timeout_seconds,
    max_retries=settings.tool_max_retries,
)
for _t in (query_poem, query_poet, query_dynasty_poems, get_my_collection, get_study_plan, draft_forum_post):
    registry.register(_t)
service = ChatService(settings, SessionStore(), tool_registry=registry, storage=storage)

app_storage = AppStorage(session_factory)
knowledge_storage = KnowledgeStorage(session_factory)
workflow_llm = build_llm(settings)
flywheel_service = FlywheelService(knowledge_storage, workflow_llm)

# Ch08 审核后台:待审列表/详情/通过写库/驳回
app.include_router(create_review_router(knowledge_storage))
app.include_router(create_cost_router())  # Ch08 验收5:按意图 token/成本报表
app.include_router(create_audit_router(session_factory))  # Ch09 管理补全:工具审计流
app.include_router(create_kb_sync_router(knowledge_storage))  # KB在线增量同步(2026-10-25)

# Ch07 工具系统:内置登记在启动时完成;插件与 MCP 在每次 get_tools 时动态刷新。
tool_audit = AuditWriter(app_storage)
tool_engine = ToolEngine(settings, tool_audit)
mcp_provider = McpProvider(
    {
        "poetry_archive": settings.mcp_poetry_archive_url,
        "judgement": settings.mcp_judgement_url,
    },
    ttl=settings.mcp_tool_refresh_seconds,
    connect_timeout=settings.mcp_connect_timeout_seconds,
)
workflow_tools = ToolCatalog(
    engine=tool_engine,
    audit=tool_audit,
    plugin_dir=Path(__file__).parent / "tools" / "extensions",
    mcp_provider=mcp_provider,
)
workflow_tools.register_builtin(
    query_poet, permission="read", result_fields=("ok", "found", "poet", "works"),
)
workflow_tools.register_builtin(
    query_dynasty_poems, permission="read", result_fields=("ok", "found", "count", "titles"),
)
workflow_tools.register_builtin(
    create_ticket, permission="write", result_fields=("ok", "ticket_id", "ticket_no"),
)
workflow_tools.register_builtin(  # Ch09 打通:个性化伴学(读 Java 侧收藏表)
    get_my_collection, permission="read", result_fields=("ok", "found", "data", "summary"),
)
workflow_tools.register_builtin(  # Ch09 打通:艾宾浩斯复习计划(读后端 SRS 表)
    get_study_plan, permission="read", result_fields=("ok", "found", "data", "summary"),
)
workflow_tools.register_builtin(  # Ch09 打通:文坛草稿(只校验回显,发布走前端调 Java)
    draft_forum_post, permission="read", result_fields=("ok", "found", "draft", "error"),
)
workflow_deps = WorkflowDeps(
    settings, workflow_llm, workflow_tools, knowledge_storage, storage, flywheel=flywheel_service,
)
configure_workflow(workflow_deps)
_workflow = None            # 编译产物,由 lifespan 打开 checkpointer 后填充
_checkpoint_conn = None     # aiosqlite 连接,关闭时回收

# Ch08 自评后台任务:请求结束后独立跑,不阻塞 SSE 收尾;关闭时统一取消
_self_eval_tasks: set[asyncio.Task] = set()


def _schedule_self_eval(final: dict, session_id: str, lf_trace_id: str | None = None) -> None:
    if workflow_deps.flywheel is None or workflow_deps.knowledge_storage is None:
        return
    task = asyncio.create_task(
        self_eval_after_turn(final, workflow_deps, session_id, lf_trace_id=lf_trace_id)
    )
    _self_eval_tasks.add(task)
    task.add_done_callback(_self_eval_tasks.discard)


@app.get("/health")
def health() -> dict:
    return {"status": "UP", "service": SERVICE_NAME}


@app.get("/nav")
def nav_page() -> FileResponse:
    """运维导航台: 监控/后台/健康入口聚合(纯静态壳,各系统自行鉴权)"""
    return FileResponse(Path(__file__).parent / "static" / "nav.html")


@app.get("/chat")
def chat_page() -> FileResponse:
    """简易聊天页(第一章 Vibe Coding 产物,静态单页)。

    显式加 `Cache-Control: no-cache`:该页几乎每章迭代都会改(如 Ch04 新增两个按钮),
    若让浏览器按启发式缓存,改造前打开过页面的用户会一直看到旧 UI、误判"新功能没生效"。
    """
    return FileResponse(
        Path(__file__).parent / "static" / "chat.html",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/admin/review")
async def admin_review_page():
    """Ch08 审核后台页:待审问题列表 + 详情 + 通过/驳回。"""
    return FileResponse(Path(__file__).parent / "static" / "admin_review.html")


@app.get("/admin/cost")
async def admin_cost_page():
    """Ch08 验收5 成本报表页:按意图聚合的 token/成本。"""
    return FileResponse(Path(__file__).parent / "static" / "admin_cost.html")


def _sse(event: str, payload: dict) -> bytes:
    """编码一条 SSE 事件(经 fastapi.sse.format_sse_event 生成线上格式)。"""
    return format_sse_event(data_str=json.dumps(payload, ensure_ascii=False), event=event)


@app.post("/agent/chat")
async def chat(request: Request, req: ChatRequest) -> EventSourceResponse:
    """SSE 流式对话:meta → tool_status* → token* → done,中途失败补发 error 事件。

    采用普通协程 + EventSourceResponse(而非生成器路由):生成器体在路由层
    TaskGroup 内消费,流前失败会被包成 ExceptionGroup,无法干净返回 502。

    meta 由路由合成、done 的 sessionId 由路由补齐:服务层 stream_events
    只产 tool_status/token/done(空 payload),但 spec §7 契约与聊天页
    (static/chat.html 从 meta 取 sessionId)都要求首尾两帧带 sessionId。
    """
    resolve_user_id(request, req.userId)  # Ch09:验签,无效 token 一律 401(结果暂不消费)
    session_id = req.sessionId or uuid4().hex
    stream = service.stream_events(session_id, req.message)
    try:
        first = await stream.__anext__()
    except StopAsyncIteration:
        first = None
    except Exception as exc:  # noqa: BLE001 - 未开始流的上游失败按 502 返回
        raise HTTPException(
            status_code=502,
            detail={
                "message": f"上游模型调用失败: {str(exc)[:200]}",
                "upstream": settings.llm_base_url,  # 不含密钥
            },
        )

    async def gen() -> AsyncIterator[bytes]:
        pending = [first] if first is not None else []

        async def drain():
            if pending:
                ev = pending.pop(0)
                yield ev
            async for ev in stream:
                yield ev

        saw_done = False
        try:
            yield _sse("meta", {"sessionId": session_id})
            async for event, payload in drain():
                if event == "done":
                    # 服务的 done payload 为空,按 spec §7 补 sessionId(其余事件原样透传)
                    saw_done = True
                    yield _sse("done", {"sessionId": session_id, **payload})
                else:
                    yield _sse(event, payload)
            if not saw_done:
                # 兜底:流正常耗尽但服务没产 done,契约要求正常收尾必有 done
                yield _sse("done", {"sessionId": session_id})
        except Exception as exc:  # noqa: BLE001 - 中途断流补发 error 事件
            yield _sse("error", {"message": str(exc)[:200]})
            return
        finally:
            # 所有 yield 点(开头 meta 帧、事件透传帧、兜底 done、error 帧)均在本
            # try 内,客户端在任一帧后断开(GeneratorExit)或异常收尾都会立即回收
            # 上游生成器,保证 stream_events 的 finally(落库/落内存历史)立即执行,
            # 与 chat_service.stream_reply 的守护语义一致;其 finally 全同步,aclose 不挂起
            await stream.aclose()

    return EventSourceResponse(gen())


class FeedbackRequest(BaseModel):
    userId: str | None = None
    sessionId: str | None = None
    message: str


def _answer_chunks(text: str, size: int = 8):
    """把整段答案切小块作 token 帧,保留打字机观感。"""
    for start in range(0, len(text), size):
        yield text[start : start + size]


def _answer_source(final: dict) -> str:
    """回答来源标识:预设话术(含等回填的固定提示)/兜底/调工具/基于资料/模型知识。"""
    if final.get("pending_subflow") or final.get("route") in ("complaint", "chitchat"):
        return "preset"
    if final.get("fallback_reason") == "insufficient_evidence":
        return "fallback"          # 仅"检索证据不足"才算兜底;agent_error 之类不冒充
    if final.get("tool_trace"):
        return "tool"
    if final.get("gate_status") == "pass" or final.get("policy_hits"):
        return "rag"               # 知识类过闸 / 判定子流程检索到条款:基于资料作答
    return "model"


def _trace_payload(final: dict) -> dict:
    """编排轨迹:把图跑完后留在 state 里的本轮关键字段汇总成一帧,供前端展示调用链。

    注意本轮是**事后**汇总 —— 图已整体跑完(`ainvoke`)才发帧,故前端拿到的是
    "这轮走完了哪些节点",不是逐节点的实时进度(实时流式是后续迭代的事)。
    """
    started = final.get("started_at")
    elapsed_ms = int((time.monotonic() - started) * 1000) if isinstance(started, (int, float)) else None
    score = final.get("evidence_score")
    return {
        "intent": final.get("intent", ""),
        "route": final.get("route") or ("ruling" if final.get("subflow_kind") else ""),
        "gate": final.get("gate_status", "skip"),
        "score": score if isinstance(score, (int, float)) else None,
        "retrievedCount": len(final.get("retrieved") or []),
        "iters": final.get("iterations", 0),
        "tokens": final.get("tokens_used", 0),
        "elapsedMs": elapsed_ms,
        "fallbackReason": final.get("fallback_reason", ""),
        "confidence": final.get("confidence", 0.0),
        "queryChanged": bool(final.get("query_changed")),
        "subflowKind": final.get("subflow_kind", ""),
        "policyCount": len(final.get("policy_hits") or []),
        "poemId": (final.get("slot_target") or {}).get("poemId"),
    }


@app.get("/api/conversations")
def list_conversations(request: Request, userId: str | None = None) -> list[dict]:
    """会话侧栏:按验签后的 userId 过滤、新在前、首问预览、已摘要标记(只读)。

    身份以 resolve_user_id 为准:带 token 时 claims.userId 优先(裸传 userId 仅在
    无 token 的本地遗留模式下生效),防伪造他人会话列表。
    """
    user_id = resolve_user_id(request, userId)
    if not user_id:
        raise HTTPException(status_code=401, detail={"message": "需要登录"})
    try:
        return storage.list_conversations(user_id)
    except Exception as exc:  # noqa: BLE001 - 查询失败让前端静默降级
        raise HTTPException(status_code=500, detail={"message": str(exc)[:200]})


@app.get("/api/conversations/{session_id}/messages")
def conversation_messages(request: Request, session_id: str, userId: str | None = None) -> list[dict]:
    """切回旧会话时回载原文;只返回 user/assistant,userId 不匹配视同不存在。

    身份以 resolve_user_id 验签结果为准,防伪造 userId 越权读他人会话。
    """
    user_id = resolve_user_id(request, userId)
    if not user_id:
        raise HTTPException(status_code=401, detail={"message": "需要登录"})
    try:
        rows = storage.load_conversation_messages(session_id, user_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail={"message": str(exc)[:200]})
    if rows is None:
        raise HTTPException(status_code=404, detail={"message": "会话不存在"})
    return rows


async def _has_pending_interrupt(config: dict) -> bool:
    """该 thread 是否有未 resume 的 interrupt;测试替身无 aget_state 时视为无。"""
    aget_state = getattr(_workflow, "aget_state", None)
    if aget_state is None:
        return False
    try:
        snapshot = await aget_state(config)
    except Exception as exc:  # noqa: BLE001 - 状态查询失败不阻断主流程
        print(f"[wf] aget_state fail: {str(exc)[:160]}")
        return False
    tasks = getattr(snapshot, "tasks", None) or ()
    return any(getattr(task, "interrupts", None) for task in tasks)


def _done_status(final: dict) -> str:
    if final.get("__interrupt__"):
        return "awaiting_confirmation"
    if final.get("pending_subflow"):
        return "awaiting_slot"
    return "ok"


async def _action_frames(final: dict):
    """action 帧族:actions/诗词点选/文坛草稿/纠错表单/建单确认(依赖最终状态,图结束后发)。"""
    actions = final.get("actions") or []
    if actions:
        yield _sse("action", {"actions": actions})
    if final.get("pending_subflow"):
        yield _sse("action", {"action": "pick_poem", "candidates": final.get("candidates") or []})
    if final.get("forum_draft"):
        yield _sse("action", {"action": "forum_draft", "draft": final["forum_draft"]})
    if final.get("correction_categories"):
        yield _sse("action", {"action": "open_correction_form",
                              "categories": final.get("correction_categories")})
    for item in final.get("__interrupt__") or []:
        value = getattr(item, "value", item)
        if isinstance(value, dict) and value.get("action") == "confirm_ticket":
            yield _sse("action", {
                "action": "confirm_ticket",
                "preview": value.get("preview") or {},
                "toolCallId": value.get("toolCallId"),
            })


async def _final_frames(final: dict, session_id: str) -> AsyncIterator[bytes]:
    """伪流式回退帧序(测试替身/未实现 astream_events 的装配):trace → tool_status* → token* → action?。"""
    yield _sse("trace", _trace_payload(final))
    for trace in final.get("tool_trace") or []:
        yield _sse(
            "tool_status",
            {
                "tool": trace["tool"],
                "status": trace["status"],
                "args": trace["args"],
                "durationMs": trace["durationMs"],
            },
        )
    for piece in _answer_chunks(final.get("answer") or ""):
        yield _sse("token", {"content": piece})
    async for frame in _action_frames(final):
        yield frame


async def _stream_frames(payload, config: dict, session_id: str, out: dict) -> AsyncIterator[bytes]:
    """真流式:订阅图的事件流,agent 节点的 LLM delta 实时发 token 帧,工具执行实时发
    tool_status 帧;trace/action 依赖最终状态,图结束后发。最终状态写入 out["final"],
    供调用方做 finish_turn/self_eval 与 done 帧收尾。

    帧序差异:token 在 trace 之前到达(实时性的必然代价;前端按事件名分发,与顺序无关)。
    兼容处理:preset/fallback 等不经 agent LLM 的答案,图结束后按前缀规则补发 token 帧
    ——未流式则整段重放;已流式为前缀则补差值;发散则打日志不补(前端按追加渲染,防重复)。
    """
    streamed: list[str] = []
    final: dict = {}
    root_run: str | None = None
    tool_starts: dict[str, float] = {}
    async for ev in _workflow.astream_events(payload, config=config):
        et = ev.get("event")
        if et == "on_chain_start":
            if root_run is None:
                root_run = ev.get("run_id")          # 第一个 chain start = 根图,用于取最终状态
        elif et == "on_tool_start":
            tool_starts[ev.get("run_id") or ""] = time.monotonic()
            yield _sse("tool_status", {"tool": ev.get("name"), "status": "calling",
                                       "args": ev.get("data", {}).get("input") or {}})
        elif et == "on_tool_end":
            frame: dict = {"tool": ev.get("name"), "status": "done"}
            started = tool_starts.pop(ev.get("run_id") or "", None)
            if started is not None:
                frame["durationMs"] = int((time.monotonic() - started) * 1000)
            yield _sse("tool_status", frame)
        elif et == "on_tool_error":
            tool_starts.pop(ev.get("run_id") or "", None)
            yield _sse("tool_status", {"tool": ev.get("name"), "status": "error"})
        elif et == "on_chat_model_stream":
            # 只放行 agent 节点的增量:classify/log 等节点的 LLM 调用不属于对话文本
            if (ev.get("metadata") or {}).get("langgraph_node") == "agent":
                piece = getattr(ev.get("data", {}).get("chunk"), "content", "") or ""
                if isinstance(piece, str) and piece:
                    streamed.append(piece)
                    yield _sse("token", {"content": piece})
        elif et == "on_chain_end" and root_run and ev.get("run_id") == root_run:
            final = ev.get("data", {}).get("output") or {}
    out["final"] = final
    answer = final.get("answer") or ""
    streamed_text = "".join(streamed)
    if answer and streamed_text != answer:
        if not streamed_text:
            for piece in _answer_chunks(answer):
                yield _sse("token", {"content": piece})
        elif answer.startswith(streamed_text):
            for piece in _answer_chunks(answer[len(streamed_text):]):
                yield _sse("token", {"content": piece})
        else:
            print(f"[wf] stream divergence: streamed={len(streamed_text)}B final={len(answer)}B,不补帧防重复")
    yield _sse("trace", _trace_payload(final))
    async for frame in _action_frames(final):
        yield frame


@app.post("/agent/workflow")
async def workflow_chat(request: Request, req: ChatRequest) -> EventSourceResponse:
    """Ch04 确定性编排入口;Ch07 增补建单确认帧。"""
    if _workflow is None:
        raise HTTPException(status_code=503, detail={"message": "workflow 未就绪(装配失败)"})
    user_id = resolve_user_id(request, req.userId)  # Ch09:JWT 验签,claims 优先
    session_id = req.sessionId or uuid4().hex
    config = {"configurable": {"thread_id": session_id}}
    if (handler := get_handler()) is not None:  # Ch08:图级 callback,LLM generation 自动入 trace
        config["callbacks"] = [handler]
    if await _has_pending_interrupt(config):
        raise HTTPException(status_code=409, detail={"message": "请先确认或取消当前工单"})

    async def gen() -> AsyncIterator[bytes]:
        yield _sse("meta", {"sessionId": session_id})
        final: dict = {}
        payload = {
            "session_id": session_id,
            "userid": user_id,
            "user_input": req.message,
            "selected_poem_id": req.selectedPoemId,
            "started_at": time.monotonic(),
            "messages": [],
            "tool_trace": [],
        }
        try:
            with trace_turn(session_id, user_id, req.message) as lf_root:
                if hasattr(_workflow, "astream_events"):
                    # 真流式:LLM delta 与工具进度实时下发;trace/action 图结束后补发
                    out: dict = {}
                    async for frame in _stream_frames(payload, config, session_id, out):
                        yield frame
                    final = out.get("final") or {}
                else:
                    # 伪流式回退(测试替身等无 astream_events 的装配),帧序契约与旧版一致
                    final = await _workflow.ainvoke(payload, config=config)
                    async for frame in _final_frames(final, session_id):
                        yield frame
                finish_turn(lf_root, final)
                lf_trace_id = current_trace_id()  # 块内取,块外上下文已失效
            _schedule_self_eval(final, session_id, lf_trace_id)
        except Exception as exc:  # noqa: BLE001 - 单请求失败不崩服务,补 error 帧
            yield _sse("error", {"message": str(exc)[:200]})
        yield _sse("done", {"sessionId": session_id, "source": _answer_source(final),
                            "status": _done_status(final)})

    return EventSourceResponse(gen())


class ResumeRequest(BaseModel):
    sessionId: str
    confirmed: bool


@app.post("/agent/workflow/resume")
async def workflow_resume(req: ResumeRequest) -> EventSourceResponse:
    """前端确认/取消建单:以 Command(resume=...) 放行同一 thread 的 interrupt。"""
    if _workflow is None:
        raise HTTPException(status_code=503, detail={"message": "workflow 未就绪(装配失败)"})
    config = {"configurable": {"thread_id": req.sessionId}}
    if (handler := get_handler()) is not None:
        config["callbacks"] = [handler]
    if not await _has_pending_interrupt(config):
        raise HTTPException(status_code=409, detail={"message": "当前没有待确认的工单"})

    async def gen() -> AsyncIterator[bytes]:
        yield _sse("meta", {"sessionId": req.sessionId})
        final: dict = {}
        payload = Command(resume={"confirmed": req.confirmed})
        try:
            with trace_turn(req.sessionId, None, "(工单确认/取消)") as lf_root:
                if hasattr(_workflow, "astream_events"):
                    out: dict = {}
                    async for frame in _stream_frames(payload, config, req.sessionId, out):
                        yield frame
                    final = out.get("final") or {}
                else:
                    final = await _workflow.ainvoke(payload, config=config)
                    async for frame in _final_frames(final, req.sessionId):
                        yield frame
                finish_turn(lf_root, final)
                lf_trace_id = current_trace_id()
            _schedule_self_eval(final, req.sessionId, lf_trace_id)
        except Exception as exc:  # noqa: BLE001
            yield _sse("error", {"message": str(exc)[:200]})
        yield _sse("done", {"sessionId": req.sessionId, "source": _answer_source(final),
                            "status": _done_status(final)})

    return EventSourceResponse(gen())


class NegativeFeedbackRequest(BaseModel):
    sessionId: str
    message: str


@app.post("/agent/feedback/negative")
async def negative_feedback(req: NegativeFeedbackRequest):
    """聊天页 👎:把不满意的上一问连同当时的召回快照写入待审池。"""
    if _workflow is None:
        raise HTTPException(status_code=503, detail={"message": "workflow 未就绪(装配失败)"})
    config = {"configurable": {"thread_id": req.sessionId}}
    hits: list[dict] = []
    try:
        snapshot = await _workflow.aget_state(config)
        values = getattr(snapshot, "values", {}) or {}
        if values.get("user_input") == req.message:
            hits = values.get("retrieved") or []
    except Exception as exc:  # noqa: BLE001 - 快照回捞失败不阻断入池
        print(f"[wf] feedback snapshot fail: {str(exc)[:160]}")
    try:
        pending_id = knowledge_storage.add_pending_question(
            req.message, req.sessionId,
            source_entry="user_dislike", retrieved_snapshot=snapshot_hits(hits),
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail={"message": f"入池失败: {str(exc)[:120]}"})
    if workflow_deps.flywheel is not None:
        workflow_deps.flywheel.schedule(pending_id)
    return {"ok": True, "pendingId": pending_id}


@app.post("/agent/feedback")
def agent_feedback(request: Request, req: FeedbackRequest) -> dict:
    """建工单落点:写 feedback 表(前端「提交反馈」按钮调用;后端不自动触发)。"""
    verified = resolve_user_id(request, req.userId)  # Ch09:JWT 验签,claims 优先
    userid = int(verified) if verified and verified.isdigit() else None
    try:
        feedback_id = app_storage.add_feedback(req.message, userid=userid)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail={"message": str(exc)[:200]})
    return {"ok": True, "feedbackId": feedback_id}


class CorrectionRequest(BaseModel):
    userId: str | None = None
    sessionId: str | None = None
    poemId: int | None = None
    category: str
    detail: str | None = None


@app.post("/agent/correction")
def agent_correction(req: CorrectionRequest) -> dict:
    """纠错/复核单落点:写 corrections 表(前端「提交纠错单」按钮调用;后端不自动触发)。"""
    userid = int(req.userId) if req.userId and req.userId.isdigit() else None
    try:
        correction_id = app_storage.add_correction(
            category=req.category, detail=req.detail, poem_id=req.poemId,
            session_id=req.sessionId, userid=userid,
        )
    except ValueError as exc:      # 类目非法 → 400(边界校验)
        raise HTTPException(status_code=400, detail={"message": str(exc)[:200]})
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail={"message": str(exc)[:200]})
    return {"ok": True, "correctionId": correction_id}