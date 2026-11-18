"""测试环境兜底:import main 时模块级 load_settings() 需要这些变量,
CI / 新环境无本地 .env 时也能跑测试(仅测试进程内生效,不落盘)。"""
import os

os.environ.setdefault("LLM_BASE_URL", "http://fake-upstream/v1")
os.environ.setdefault("LLM_API_KEY", "sk-fake-for-tests")
os.environ.setdefault("LLM_MODEL", "fake-model")
os.environ.setdefault("MYSQL_URL", "sqlite:///:memory:")
os.environ.setdefault("TOOL_TIMEOUT_SECONDS", "5")
os.environ.setdefault("TOOL_MAX_RETRIES", "1")
os.environ.setdefault("EMBEDDING_MODEL_PATH", "fake-model-path")
os.environ.setdefault("WARMUP_ON_START", "0")  # 测试不预热:避免加载真 BGE-M3、避免在仓库建出 milvus_data/
os.environ.setdefault("WORKFLOW_CHECKPOINT_PATH", ":memory:")  # 测试用内存库,不在仓库建 checkpoints/
os.environ.setdefault("CTX_LOG_DISABLE", "1")

# Ch08:测试进程禁用 Langfuse(置空而非删除——load_dotenv(override=False) 不会覆盖已存在的键,
# 删除则会被本地 .env 重新注入)。避免 ainvoke 注入 callbacks 且测试流量发往本地 Langfuse。
os.environ["LANGFUSE_HOST"] = ""
os.environ["LANGFUSE_PUBLIC_KEY"] = ""
os.environ["LANGFUSE_SECRET_KEY"] = ""
os.environ["ADMIN_JWT_SECRET_KEY"] = ""  # Ch09:测试禁用管理鉴权(与 Langfuse 同法:置空防 .env 注入)
