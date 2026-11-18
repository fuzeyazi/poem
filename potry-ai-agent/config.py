"""从 .env 加载配置,缺关键变量直接报错(fail fast)。"""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_REQUIRED = ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "MYSQL_URL", "EMBEDDING_MODEL_PATH")
# 默认值单一来源:Settings 字段默认值与 load_settings 共用,避免两处字面量漂移
# MYSQL_URL 含凭据,不允许代码内置默认值,必须由 .env 提供(fail-fast)
_DEFAULT_TOOL_TIMEOUT_SECONDS = 5.0
_DEFAULT_TOOL_MAX_RETRIES = 1
# Ch03:向量库/切分/挖知识默认值(与 Settings 共用,单一来源)
_DEFAULT_MILVUS_DB_PATH = str(Path(__file__).resolve().parent / "milvus_data" / "knowledge.db")
_DEFAULT_MILVUS_COLLECTION = "knowledge"
_DEFAULT_MILVUS_TOPK = 5
_DEFAULT_SIMILARITY_THRESHOLD = 0.5
_DEFAULT_CHUNK_SIZE = 400
_DEFAULT_CHUNK_OVERLAP = 60
_DEFAULT_MINING_BATCH_SIZE = 20
_DEFAULT_MINING_CRON = "0 3 * * *"
# Ch04:Workflow 编排默认值(与 Settings 共用,单一来源)
_DEFAULT_WORKFLOW_MAX_ITER = 4
_DEFAULT_WORKFLOW_MAX_TOKENS = 8000
_DEFAULT_WORKFLOW_CHECKPOINT_PATH = str(
    Path(__file__).resolve().parent / "checkpoints" / "graph.sqlite"
)
# Ch06:上下文预算/三层截短默认值(与 Settings 共用,单一来源)
_DEFAULT_MODEL_CONTEXT_WINDOW = 64000
_DEFAULT_MAX_OUTPUT_TOKENS = 4000
_DEFAULT_MAX_USER_INPUT_TOKENS = 2000
_DEFAULT_TOOL_RESULT_MAX_TOKENS = 1200
_DEFAULT_RERANK_TOP_K = 5
_DEFAULT_SYSTEM_RESERVE_TOKENS = 1500
_DEFAULT_EVIDENCE_PER_CHUNK_TOKENS = 250
_DEFAULT_SUMMARY_RESERVE_TOKENS = 500
_DEFAULT_SAFETY_RESERVE_TOKENS = 1500
_DEFAULT_KEEP_TURNS = 40
_DEFAULT_TURN_STEADY_TOKENS = 400
_DEFAULT_BOUNDARY_RESERVE_TOKENS = 1
_DEFAULT_SUMMARY_BATCH_MAX_TOKENS = 3000
_DEFAULT_HISTORY_CTX_MAX_TOKENS = 2000
_DEFAULT_LAYER2_ASSISTANT_PREFIX_CHARS = 40
_DEFAULT_LAYER2_BLOB_CHARS = 400
# Ch07:MCP 接入默认值(与 Settings 共用,单一来源)
_DEFAULT_MCP_POETRY_ARCHIVE_URL = "http://127.0.0.1:9101/mcp"
_DEFAULT_MCP_JUDGEMENT_URL = "http://127.0.0.1:9102/mcp"
_DEFAULT_MCP_TOOL_REFRESH_SECONDS = 5.0
_DEFAULT_MCP_CONNECT_TIMEOUT_SECONDS = 2.0
# Ch08:证据置信度闸默认值(阈值最终由评估集校准后写入 .env)
_DEFAULT_EVIDENCE_MIN_SCORE = 0.30
_DEFAULT_EVIDENCE_CONFIDENCE_THRESHOLD = 0.60
_DEFAULT_FLYWHEEL_DRAIN_MINUTES = 5.0


@dataclass(frozen=True)
class Settings:
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    history_max_tokens: int
    llm_temperature: float
    mysql_url: str  # 必填,连接串含凭据,不设默认值
    embedding_model_path: str  # 必填,本地 BGE-M3 模型目录(BGE-M3 从 modelscope 下载)
    embedding_engine: str = "torch"  # torch|onnx;onnx 与 torch 数值对齐(见 evals/verify_onnx_parity.py),单条嵌入约 2.8x
    tool_timeout_seconds: float = _DEFAULT_TOOL_TIMEOUT_SECONDS
    tool_max_retries: int = _DEFAULT_TOOL_MAX_RETRIES
    milvus_db_path: str = _DEFAULT_MILVUS_DB_PATH
    milvus_collection: str = _DEFAULT_MILVUS_COLLECTION
    milvus_topk: int = _DEFAULT_MILVUS_TOPK
    similarity_threshold: float = _DEFAULT_SIMILARITY_THRESHOLD
    chunk_size: int = _DEFAULT_CHUNK_SIZE
    chunk_overlap: int = _DEFAULT_CHUNK_OVERLAP
    mining_batch_size: int = _DEFAULT_MINING_BATCH_SIZE
    mining_cron: str = _DEFAULT_MINING_CRON
    workflow_max_iter: int = _DEFAULT_WORKFLOW_MAX_ITER
    workflow_max_tokens: int = _DEFAULT_WORKFLOW_MAX_TOKENS
    workflow_checkpoint_path: str = _DEFAULT_WORKFLOW_CHECKPOINT_PATH
    model_context_window: int = _DEFAULT_MODEL_CONTEXT_WINDOW
    max_output_tokens: int = _DEFAULT_MAX_OUTPUT_TOKENS
    max_user_input_tokens: int = _DEFAULT_MAX_USER_INPUT_TOKENS
    max_agent_steps: int = _DEFAULT_WORKFLOW_MAX_ITER
    tool_result_max_tokens: int = _DEFAULT_TOOL_RESULT_MAX_TOKENS
    rerank_top_k: int = _DEFAULT_RERANK_TOP_K
    system_reserve_tokens: int = _DEFAULT_SYSTEM_RESERVE_TOKENS
    evidence_per_chunk_tokens: int = _DEFAULT_EVIDENCE_PER_CHUNK_TOKENS
    summary_reserve_tokens: int = _DEFAULT_SUMMARY_RESERVE_TOKENS
    safety_reserve_tokens: int = _DEFAULT_SAFETY_RESERVE_TOKENS
    keep_turns: int = _DEFAULT_KEEP_TURNS
    turn_steady_tokens: int = _DEFAULT_TURN_STEADY_TOKENS
    boundary_reserve_tokens: int = _DEFAULT_BOUNDARY_RESERVE_TOKENS
    summary_batch_max_tokens: int = _DEFAULT_SUMMARY_BATCH_MAX_TOKENS
    history_ctx_max_tokens: int = _DEFAULT_HISTORY_CTX_MAX_TOKENS
    layer2_assistant_prefix_chars: int = _DEFAULT_LAYER2_ASSISTANT_PREFIX_CHARS
    layer2_blob_chars: int = _DEFAULT_LAYER2_BLOB_CHARS
    warmup_on_start: bool = True  # 启动时预热嵌入模型与向量库(冷启动加载 2.3GB 模型远超工具体 5s 超时)
    mcp_poetry_archive_url: str = _DEFAULT_MCP_POETRY_ARCHIVE_URL
    mcp_judgement_url: str = _DEFAULT_MCP_JUDGEMENT_URL
    mcp_tool_refresh_seconds: float = _DEFAULT_MCP_TOOL_REFRESH_SECONDS
    mcp_connect_timeout_seconds: float = _DEFAULT_MCP_CONNECT_TIMEOUT_SECONDS
    evidence_min_score: float = _DEFAULT_EVIDENCE_MIN_SCORE
    evidence_confidence_threshold: float = _DEFAULT_EVIDENCE_CONFIDENCE_THRESHOLD
    flywheel_drain_minutes: float = _DEFAULT_FLYWHEEL_DRAIN_MINUTES


def load_settings() -> Settings:
    missing = [k for k in _REQUIRED if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"缺少必要环境变量: {', '.join(missing)}(请在 .env 中配置)")
    # Ch03 新增可选项统一语义:未设置或空串 → 走默认值(数值项与字符串项一致)
    try:
        history_max_tokens = int(os.getenv("HISTORY_MAX_TOKENS", "2000"))
        llm_temperature = float(os.getenv("LLM_TEMPERATURE", "0.7"))
        tool_timeout_seconds = float(os.getenv("TOOL_TIMEOUT_SECONDS", str(_DEFAULT_TOOL_TIMEOUT_SECONDS)))
        tool_max_retries = int(os.getenv("TOOL_MAX_RETRIES", str(_DEFAULT_TOOL_MAX_RETRIES)))
        milvus_topk = int(os.getenv("MILVUS_TOPK") or str(_DEFAULT_MILVUS_TOPK))
        similarity_threshold = float(os.getenv("SIMILARITY_THRESHOLD") or str(_DEFAULT_SIMILARITY_THRESHOLD))
        chunk_size = int(os.getenv("CHUNK_SIZE") or str(_DEFAULT_CHUNK_SIZE))
        chunk_overlap = int(os.getenv("CHUNK_OVERLAP") or str(_DEFAULT_CHUNK_OVERLAP))
        mining_batch_size = int(os.getenv("MINING_BATCH_SIZE") or str(_DEFAULT_MINING_BATCH_SIZE))
        # 布尔开关:仅 "0"/"false"(不区分大小写、忽略首尾空白)关闭,
        # 其它任意值(含 "no"/"off"/"2")均视为开启;未设置或空串 → 走默认(True)
        warmup_on_start = os.getenv("WARMUP_ON_START", "1").strip().lower() not in ("0", "false")
        workflow_max_iter = int(os.getenv("WORKFLOW_MAX_ITER") or str(_DEFAULT_WORKFLOW_MAX_ITER))
        workflow_max_tokens = int(os.getenv("WORKFLOW_MAX_TOKENS") or str(_DEFAULT_WORKFLOW_MAX_TOKENS))
        model_context_window = int(os.getenv("MODEL_CONTEXT_WINDOW") or str(_DEFAULT_MODEL_CONTEXT_WINDOW))
        max_output_tokens = int(os.getenv("MAX_OUTPUT_TOKENS") or str(_DEFAULT_MAX_OUTPUT_TOKENS))
        max_user_input_tokens = int(os.getenv("MAX_USER_INPUT_TOKENS") or str(_DEFAULT_MAX_USER_INPUT_TOKENS))
        max_agent_steps = int(os.getenv("MAX_AGENT_STEPS") or str(workflow_max_iter))
        tool_result_max_tokens = int(os.getenv("TOOL_RESULT_MAX_TOKENS") or str(_DEFAULT_TOOL_RESULT_MAX_TOKENS))
        rerank_top_k = int(os.getenv("RERANK_TOP_K") or str(_DEFAULT_RERANK_TOP_K))
        system_reserve_tokens = int(os.getenv("SYSTEM_RESERVE_TOKENS") or str(_DEFAULT_SYSTEM_RESERVE_TOKENS))
        evidence_per_chunk_tokens = int(os.getenv("EVIDENCE_PER_CHUNK_TOKENS") or str(_DEFAULT_EVIDENCE_PER_CHUNK_TOKENS))
        summary_reserve_tokens = int(os.getenv("SUMMARY_RESERVE_TOKENS") or str(_DEFAULT_SUMMARY_RESERVE_TOKENS))
        safety_reserve_tokens = int(os.getenv("SAFETY_RESERVE_TOKENS") or str(_DEFAULT_SAFETY_RESERVE_TOKENS))
        keep_turns = int(os.getenv("KEEP_TURNS") or str(_DEFAULT_KEEP_TURNS))
        turn_steady_tokens = int(os.getenv("TURN_STEADY_TOKENS") or str(_DEFAULT_TURN_STEADY_TOKENS))
        boundary_reserve_tokens = int(os.getenv("BOUNDARY_RESERVE_TOKENS") or str(_DEFAULT_BOUNDARY_RESERVE_TOKENS))
        summary_batch_max_tokens = int(os.getenv("SUMMARY_BATCH_MAX_TOKENS") or str(_DEFAULT_SUMMARY_BATCH_MAX_TOKENS))
        history_ctx_max_tokens = int(os.getenv("HISTORY_CTX_MAX_TOKENS") or str(_DEFAULT_HISTORY_CTX_MAX_TOKENS))
        layer2_assistant_prefix_chars = int(os.getenv("LAYER2_ASSISTANT_PREFIX_CHARS") or str(_DEFAULT_LAYER2_ASSISTANT_PREFIX_CHARS))
        layer2_blob_chars = int(os.getenv("LAYER2_BLOB_CHARS") or str(_DEFAULT_LAYER2_BLOB_CHARS))
        mcp_tool_refresh_seconds = float(
            os.getenv("MCP_TOOL_REFRESH_SECONDS") or str(_DEFAULT_MCP_TOOL_REFRESH_SECONDS)
        )
        mcp_connect_timeout_seconds = float(
            os.getenv("MCP_CONNECT_TIMEOUT_SECONDS") or str(_DEFAULT_MCP_CONNECT_TIMEOUT_SECONDS)
        )
        evidence_min_score = float(
            os.getenv("EVIDENCE_MIN_SCORE") or str(_DEFAULT_EVIDENCE_MIN_SCORE)
        )
        evidence_confidence_threshold = float(
            os.getenv("EVIDENCE_CONFIDENCE_THRESHOLD")
            or str(_DEFAULT_EVIDENCE_CONFIDENCE_THRESHOLD)
        )
        flywheel_drain_minutes = float(
            os.getenv("FLYWHEEL_DRAIN_MINUTES") or str(_DEFAULT_FLYWHEEL_DRAIN_MINUTES)
        )
    except ValueError as exc:
        raise RuntimeError(
            f"环境变量格式错误: {exc}(HISTORY_MAX_TOKENS/TOOL_MAX_RETRIES/MILVUS_TOPK/"
            "CHUNK_SIZE/CHUNK_OVERLAP/MINING_BATCH_SIZE/WORKFLOW_MAX_ITER/"
            "WORKFLOW_MAX_TOKENS 须为整数,"
            "LLM_TEMPERATURE/TOOL_TIMEOUT_SECONDS/SIMILARITY_THRESHOLD 须为小数)"
        )
    # MILVUS_TOPK 为 0/负数时 Milvus search 会抛 ParamError,故 fail-fast 单点治理
    if milvus_topk <= 0:
        raise RuntimeError(f"MILVUS_TOPK 必须为正整数(当前: {milvus_topk})")
    # MINING_BATCH_SIZE 为 0/负数时 range(0, n, batch_size) 会抛错崩掉整轮挖知识,同样 fail-fast
    if mining_batch_size <= 0:
        raise RuntimeError("MINING_BATCH_SIZE 必须为正整数(当前: %s)" % mining_batch_size)
    if workflow_max_iter <= 0:
        raise RuntimeError(f"WORKFLOW_MAX_ITER 必须为正整数(当前: {workflow_max_iter})")
    if workflow_max_tokens <= 0:
        raise RuntimeError(f"WORKFLOW_MAX_TOKENS 必须为正整数(当前: {workflow_max_tokens})")
    for name, value in (
        ("MODEL_CONTEXT_WINDOW", model_context_window),
        ("MAX_OUTPUT_TOKENS", max_output_tokens),
        ("MAX_USER_INPUT_TOKENS", max_user_input_tokens),
        ("MAX_AGENT_STEPS", max_agent_steps),
        ("TOOL_RESULT_MAX_TOKENS", tool_result_max_tokens),
        ("RERANK_TOP_K", rerank_top_k),
        ("KEEP_TURNS", keep_turns),
        ("TURN_STEADY_TOKENS", turn_steady_tokens),
        ("SUMMARY_BATCH_MAX_TOKENS", summary_batch_max_tokens),
        ("HISTORY_CTX_MAX_TOKENS", history_ctx_max_tokens),
        ("LAYER2_ASSISTANT_PREFIX_CHARS", layer2_assistant_prefix_chars),
        ("LAYER2_BLOB_CHARS", layer2_blob_chars),
    ):
        if value <= 0:
            raise RuntimeError(f"{name} 必须为正整数(当前: {value})")
    for name, value in (
        ("SYSTEM_RESERVE_TOKENS", system_reserve_tokens),
        ("EVIDENCE_PER_CHUNK_TOKENS", evidence_per_chunk_tokens),
        ("SUMMARY_RESERVE_TOKENS", summary_reserve_tokens),
        ("SAFETY_RESERVE_TOKENS", safety_reserve_tokens),
        ("BOUNDARY_RESERVE_TOKENS", boundary_reserve_tokens),
    ):
        if value < 0:
            raise RuntimeError(f"{name} 不得为负数(当前: {value})")
    if mcp_tool_refresh_seconds <= 0:
        raise RuntimeError(f"MCP_TOOL_REFRESH_SECONDS 必须为正数(当前: {mcp_tool_refresh_seconds})")
    if mcp_connect_timeout_seconds <= 0:
        raise RuntimeError(f"MCP_CONNECT_TIMEOUT_SECONDS 必须为正数(当前: {mcp_connect_timeout_seconds})")
    if not 0 <= evidence_min_score <= 1:
        raise RuntimeError(f"EVIDENCE_MIN_SCORE 必须在 0–1(当前: {evidence_min_score})")
    if not 0 <= evidence_confidence_threshold <= 1:
        raise RuntimeError(
            f"EVIDENCE_CONFIDENCE_THRESHOLD 必须在 0–1(当前: {evidence_confidence_threshold})"
        )
    if flywheel_drain_minutes <= 0:
        raise RuntimeError(
            f"FLYWHEEL_DRAIN_MINUTES 必须为正数(当前: {flywheel_drain_minutes})"
        )
    return Settings(
        llm_base_url=os.environ["LLM_BASE_URL"],
        llm_api_key=os.environ["LLM_API_KEY"],
        llm_model=os.environ["LLM_MODEL"],
        history_max_tokens=history_max_tokens,
        llm_temperature=llm_temperature,
        mysql_url=os.environ["MYSQL_URL"],
        embedding_model_path=os.environ["EMBEDDING_MODEL_PATH"],
        embedding_engine=os.environ.get("EMBEDDING_ENGINE", "torch"),
        tool_timeout_seconds=tool_timeout_seconds,
        tool_max_retries=tool_max_retries,
        milvus_db_path=os.getenv("MILVUS_DB_PATH") or _DEFAULT_MILVUS_DB_PATH,
        milvus_collection=os.getenv("MILVUS_COLLECTION") or _DEFAULT_MILVUS_COLLECTION,
        milvus_topk=milvus_topk,
        similarity_threshold=similarity_threshold,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        mining_batch_size=mining_batch_size,
        mining_cron=os.getenv("MINING_CRON") or _DEFAULT_MINING_CRON,
        workflow_max_iter=workflow_max_iter,
        workflow_max_tokens=workflow_max_tokens,
        workflow_checkpoint_path=(
            os.getenv("WORKFLOW_CHECKPOINT_PATH") or _DEFAULT_WORKFLOW_CHECKPOINT_PATH
        ),
        model_context_window=model_context_window,
        max_output_tokens=max_output_tokens,
        max_user_input_tokens=max_user_input_tokens,
        max_agent_steps=max_agent_steps,
        tool_result_max_tokens=tool_result_max_tokens,
        rerank_top_k=rerank_top_k,
        system_reserve_tokens=system_reserve_tokens,
        evidence_per_chunk_tokens=evidence_per_chunk_tokens,
        summary_reserve_tokens=summary_reserve_tokens,
        safety_reserve_tokens=safety_reserve_tokens,
        keep_turns=keep_turns,
        turn_steady_tokens=turn_steady_tokens,
        boundary_reserve_tokens=boundary_reserve_tokens,
        summary_batch_max_tokens=summary_batch_max_tokens,
        history_ctx_max_tokens=history_ctx_max_tokens,
        layer2_assistant_prefix_chars=layer2_assistant_prefix_chars,
        layer2_blob_chars=layer2_blob_chars,
        warmup_on_start=warmup_on_start,
        mcp_poetry_archive_url=(
            os.getenv("MCP_POETRY_ARCHIVE_URL") or _DEFAULT_MCP_POETRY_ARCHIVE_URL
        ),
        mcp_judgement_url=(
            os.getenv("MCP_JUDGEMENT_URL") or _DEFAULT_MCP_JUDGEMENT_URL
        ),
        mcp_tool_refresh_seconds=mcp_tool_refresh_seconds,
        mcp_connect_timeout_seconds=mcp_connect_timeout_seconds,
        evidence_min_score=evidence_min_score,
        evidence_confidence_threshold=evidence_confidence_threshold,
        flywheel_drain_minutes=flywheel_drain_minutes,
    )
