"""Ch08 可观测:Langfuse 链路接入(spec §3.2)。

约定:
- `LANGFUSE_HOST` / `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` 任一缺失 →
  tracing 整体关闭并打印 `[langfuse] disabled: ...`,聊天主流程不受影响。
- 回合级根 observation `chat-turn` 由 `trace_turn` 创建,`propagate_attributes`
  把 session_id/user_id 传播给图内 handler 生成的子 span/generation。
- 节点级 `@observe` 装饰见 workflow/nodes.py 与 workflow/agent_react.py;
  `ticket_confirm_node` 涉及 interrupt,不套 @observe(spec 明确)。
- SDK 无凭据时 `@observe` 自动 no-op,测试环境零影响。
"""
from __future__ import annotations

import os
from contextlib import contextmanager

_REQUIRED_ENV = ("LANGFUSE_HOST", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")

_handler = None
_handler_checked = False
_client_checked = False
_client = None


def _missing_env() -> list[str]:
    return [name for name in _REQUIRED_ENV if not os.getenv(name)]


def get_handler():
    """懒加载 `langfuse.langchain.CallbackHandler`;环境不全/导入失败返回 None。"""
    global _handler, _handler_checked
    if _handler_checked:
        return _handler
    _handler_checked = True
    missing = _missing_env()
    if missing:
        print(f"[langfuse] disabled: missing env {missing}")
        return None
    try:
        from langfuse.langchain import CallbackHandler
    except Exception as exc:  # noqa: BLE001 - 可观测挂掉不影响聊天
        print(f"[langfuse] disabled: import failed: {exc}")
        return None
    _handler = CallbackHandler()
    return _handler


def _get_client():
    """配置齐全时返回 Langfuse 客户端单例,否则 None。"""
    global _client, _client_checked
    if _client_checked:
        return _client
    _client_checked = True
    if _missing_env():
        return None
    try:
        from langfuse import Langfuse

        _client = Langfuse()
    except Exception as exc:  # noqa: BLE001
        print(f"[langfuse] disabled: client init failed: {exc}")
        _client = None
    return _client


@contextmanager
def trace_turn(session_id: str, user_id: str | None, message: str):
    """回合级根 span(`chat-turn`),input=用户消息;无凭据时 yield None。

    v5 SDK 语义:根 span 必须是"当前 observation"(start_as_current_observation),
    之后 propagate_attributes 才能挂 session/user,且回合内 @observe 节点 span
    与 CallbackHandler 生成的 LLM generation 都会自动挂到该根下。
    """
    client = _get_client()
    cm = None
    prop = None
    if client is not None:
        try:
            from langfuse import propagate_attributes

            # v5:propagate_attributes 返回上下文管理器,必须 with 使用才生效;
            # 包住根 span 创建,session/user/trace_name 才会挂到 trace 属性上。
            prop = propagate_attributes(
                session_id=session_id,
                user_id=user_id or "anonymous",
                trace_name="chat-turn",
            )
            prop.__enter__()
            cm = client.start_as_current_observation(
                name="chat-turn", as_type="span", input=message
            )
            root = cm.__enter__()
        except Exception as exc:  # noqa: BLE001 - 链路失败不拖垮对话
            print(f"[langfuse] trace_turn failed: {exc}")
            cm = None
    try:
        yield None if cm is None else root
    finally:
        for closer in (cm, prop):
            if closer is not None:
                try:
                    closer.__exit__(None, None, None)
                except Exception:  # noqa: BLE001
                    pass


def finish_turn(root, final: dict) -> None:
    """回合收尾:intent/route/gate/证据置信度写根元数据,回答写 output。"""
    if root is None:
        return
    try:
        answer = ""
        for msg in reversed(final.get("messages") or []):
            content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", "")
            if content:
                answer = content
                break
        root.update(
            metadata={
                "intent": final.get("intent"),
                "route": final.get("route"),
                "gate_status": final.get("gate_status"),
                "evidence_confidence": final.get("evidence_confidence"),
                "fallback_reason": final.get("fallback_reason"),
            },
            output=answer,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[langfuse] finish_turn failed: {exc}")


@contextmanager
def tag_llm(metadata: dict):
    """把回合级元数据(如 intent)传播给节点内新建的子观测(LLM generation)。

    v5:propagate_attributes 返回上下文管理器;metadata 会写到当前 span 并
    传播给上下文内新建的子 span —— 由此 GENERATION 携带 metadata.intent,
    验收5 的按意图成本聚合才有分组键。
    """
    client = _get_client()
    if client is None:
        yield
        return
    cm = None
    try:
        from langfuse import propagate_attributes

        cm = propagate_attributes(metadata=metadata)
        cm.__enter__()
    except Exception as exc:  # noqa: BLE001 - 元数据失败不影响调用
        print(f"[langfuse] tag_llm failed: {exc}")
        cm = None
    try:
        yield
    finally:
        for closer in (cm, prop):
            if closer is not None:
                try:
                    closer.__exit__(None, None, None)
                except Exception:  # noqa: BLE001
                    pass


def current_trace_id() -> str | None:
    """当前上下文的 trace id(须在 trace_turn 块内调用);未启用链路返回 None。"""
    if _get_client() is None:
        return None
    try:
        from langfuse import get_client

        return get_client().get_current_trace_id()
    except Exception:  # noqa: BLE001
        return None


@contextmanager
def linked_span(trace_id: str | None, name: str, metadata: dict | None = None,
                session_id: str | None = None):
    """把后台任务(如回合后自评)挂回主回合 trace:同 trace_id + 子 span。

    无凭据或无 trace_id 时 no-op;元数据(如 intent)写入 span,
    使后台 LLM 调用的成本在报表中按意图归因而非落入 unknown。
    """
    client = _get_client()
    if client is None or not trace_id:
        yield None
        return
    cm = prop = None
    try:
        if session_id:
            from langfuse import propagate_attributes

            prop = propagate_attributes(session_id=session_id)
            prop.__enter__()
        cm = client.start_as_current_observation(
            name=name, as_type="span", trace_context={"trace_id": trace_id},
            metadata=metadata or {},
        )
        root = cm.__enter__()
    except Exception as exc:  # noqa: BLE001 - 观测失败不影响业务
        print(f"[langfuse] linked_span failed: {exc}")
        cm = None
    try:
        yield None if cm is None else root
    finally:
        if cm is not None:
            try:
                cm.__exit__(None, None, None)
            except Exception:  # noqa: BLE001
                pass
