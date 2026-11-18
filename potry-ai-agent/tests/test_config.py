import pytest

from config import load_settings


def test_missing_required_env_fails_fast(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    try:
        load_settings()
        assert False, "应抛出 RuntimeError"
    except RuntimeError as exc:
        assert "LLM_API_KEY" in str(exc)


def test_missing_mysql_url_fails_fast(monkeypatch):
    # MYSQL_URL 含凭据,不得有代码内默认值:缺失须 fail-fast 并指明变量名
    monkeypatch.delenv("MYSQL_URL", raising=False)
    with pytest.raises(RuntimeError, match="MYSQL_URL"):
        load_settings()


def test_defaults_applied(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_MODEL", "deepseek-chat")
    monkeypatch.delenv("HISTORY_MAX_TOKENS", raising=False)
    monkeypatch.delenv("LLM_TEMPERATURE", raising=False)
    s = load_settings()
    assert s.llm_model == "deepseek-chat"
    assert s.history_max_tokens == 2000
    assert s.llm_temperature == 0.7


def test_load_settings_reads_tool_and_mysql_configs(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://fake")
    monkeypatch.setenv("LLM_API_KEY", "sk-fake")
    monkeypatch.setenv("LLM_MODEL", "fake")
    monkeypatch.setenv("MYSQL_URL", "mysql+pymysql://root:pw@localhost:3306/poem")
    monkeypatch.setenv("TOOL_TIMEOUT_SECONDS", "3")
    monkeypatch.setenv("TOOL_MAX_RETRIES", "2")
    s = load_settings()
    assert s.mysql_url == "mysql+pymysql://root:pw@localhost:3306/poem"
    assert s.tool_timeout_seconds == 3.0
    assert s.tool_max_retries == 2


def test_load_settings_bad_tool_number_reports_variable(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://fake")
    monkeypatch.setenv("LLM_API_KEY", "sk-fake")
    monkeypatch.setenv("LLM_MODEL", "fake")
    monkeypatch.setenv("TOOL_TIMEOUT_SECONDS", "abc")
    with pytest.raises(RuntimeError, match="TOOL_TIMEOUT_SECONDS"):
        load_settings()


def test_load_settings_reads_ch03_knowledge_configs(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://fake")
    monkeypatch.setenv("LLM_API_KEY", "sk-fake")
    monkeypatch.setenv("LLM_MODEL", "fake")
    monkeypatch.setenv("MYSQL_URL", "sqlite:///:memory:")
    monkeypatch.setenv("EMBEDDING_MODEL_PATH", "E:/models/bge-m3")
    monkeypatch.setenv("MILVUS_TOPK", "7")
    monkeypatch.setenv("SIMILARITY_THRESHOLD", "0.6")
    monkeypatch.setenv("CHUNK_SIZE", "300")
    monkeypatch.setenv("MINING_CRON", "15 4 * * *")
    s = load_settings()
    assert s.embedding_model_path == "E:/models/bge-m3"
    assert s.milvus_collection == "knowledge"
    assert s.milvus_topk == 7
    assert s.similarity_threshold == 0.6
    assert s.chunk_size == 300
    assert s.chunk_overlap == 60
    assert s.mining_cron == "15 4 * * *"


def test_missing_embedding_model_path_fails_fast(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://fake")
    monkeypatch.setenv("LLM_API_KEY", "sk-fake")
    monkeypatch.setenv("LLM_MODEL", "fake")
    monkeypatch.setenv("MYSQL_URL", "sqlite:///:memory:")
    monkeypatch.delenv("EMBEDDING_MODEL_PATH", raising=False)
    with pytest.raises(RuntimeError, match="EMBEDDING_MODEL_PATH"):
        load_settings()


def test_load_settings_bad_milvus_topk_reports_variable(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://fake")
    monkeypatch.setenv("LLM_API_KEY", "sk-fake")
    monkeypatch.setenv("LLM_MODEL", "fake")
    monkeypatch.setenv("MYSQL_URL", "sqlite:///:memory:")
    monkeypatch.setenv("EMBEDDING_MODEL_PATH", "fake-model-path")
    monkeypatch.setenv("MILVUS_TOPK", "abc")
    with pytest.raises(RuntimeError, match="MILVUS_TOPK"):
        load_settings()


def test_load_settings_rejects_non_positive_milvus_topk(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://fake")
    monkeypatch.setenv("LLM_API_KEY", "sk-fake")
    monkeypatch.setenv("LLM_MODEL", "fake")
    monkeypatch.setenv("MYSQL_URL", "sqlite:///:memory:")
    monkeypatch.setenv("EMBEDDING_MODEL_PATH", "fake-model-path")
    monkeypatch.setenv("MILVUS_TOPK", "0")
    with pytest.raises(RuntimeError, match="MILVUS_TOPK"):
        load_settings()


def test_load_settings_rejects_non_positive_mining_batch_size(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://fake")
    monkeypatch.setenv("LLM_API_KEY", "sk-fake")
    monkeypatch.setenv("LLM_MODEL", "fake")
    monkeypatch.setenv("MYSQL_URL", "sqlite:///:memory:")
    monkeypatch.setenv("EMBEDDING_MODEL_PATH", "fake-model-path")
    monkeypatch.setenv("MINING_BATCH_SIZE", "0")
    with pytest.raises(RuntimeError, match="MINING_BATCH_SIZE"):
        load_settings()


@pytest.mark.parametrize(
    "raw,expected",
    [(None, True), ("", True), ("0", False), ("false", False), ("FALSE", False), (" 0 ", False)],
)
def test_warmup_on_start_parsing(monkeypatch, raw, expected):
    monkeypatch.setenv("LLM_BASE_URL", "http://fake")
    monkeypatch.setenv("LLM_API_KEY", "sk-fake")
    monkeypatch.setenv("LLM_MODEL", "fake")
    monkeypatch.setenv("MYSQL_URL", "sqlite:///:memory:")
    monkeypatch.setenv("EMBEDDING_MODEL_PATH", "fake-model-path")
    if raw is None:
        monkeypatch.delenv("WARMUP_ON_START", raising=False)
    else:
        monkeypatch.setenv("WARMUP_ON_START", raw)
    assert load_settings().warmup_on_start is expected


def test_load_settings_reads_ch04_workflow_configs(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://fake")
    monkeypatch.setenv("LLM_API_KEY", "sk-fake")
    monkeypatch.setenv("LLM_MODEL", "fake")
    monkeypatch.setenv("MYSQL_URL", "sqlite:///:memory:")
    monkeypatch.setenv("EMBEDDING_MODEL_PATH", "fake-model-path")
    monkeypatch.setenv("WORKFLOW_MAX_ITER", "3")
    monkeypatch.setenv("WORKFLOW_MAX_TOKENS", "1234")
    s = load_settings()
    assert s.workflow_max_iter == 3
    assert s.workflow_max_tokens == 1234


def test_workflow_defaults_applied(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://fake")
    monkeypatch.setenv("LLM_API_KEY", "sk-fake")
    monkeypatch.setenv("LLM_MODEL", "fake")
    monkeypatch.setenv("MYSQL_URL", "sqlite:///:memory:")
    monkeypatch.setenv("EMBEDDING_MODEL_PATH", "fake-model-path")
    monkeypatch.delenv("WORKFLOW_MAX_ITER", raising=False)
    monkeypatch.delenv("WORKFLOW_MAX_TOKENS", raising=False)
    monkeypatch.delenv("WORKFLOW_CHECKPOINT_PATH", raising=False)
    s = load_settings()
    assert s.workflow_max_iter == 4
    assert s.workflow_max_tokens == 8000
    assert s.workflow_checkpoint_path.endswith("graph.sqlite")


def test_rejects_non_positive_workflow_max_iter(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://fake")
    monkeypatch.setenv("LLM_API_KEY", "sk-fake")
    monkeypatch.setenv("LLM_MODEL", "fake")
    monkeypatch.setenv("MYSQL_URL", "sqlite:///:memory:")
    monkeypatch.setenv("EMBEDDING_MODEL_PATH", "fake-model-path")
    monkeypatch.setenv("WORKFLOW_MAX_ITER", "0")
    with pytest.raises(RuntimeError, match="WORKFLOW_MAX_ITER"):
        load_settings()
