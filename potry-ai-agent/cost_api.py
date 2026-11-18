"""Ch08 验收5:按意图的 LLM token/成本报表。

数据源:Langfuse ClickHouse `default.events_full`(GENERATION 观测含 usage_details 与
metadata.intent)。Langfuse v4 服务器为 events_only 模式,旧 observations 读接口已关闭,
故直查 ClickHouse(spec §3.3 的 get_many 方案按 v4 现实调整,spec 意图不变)。

价格原则(可观测技能约定):按精确模型名键控、集中维护、未知模型不计价只计数,
保留原始 token 用量以便调价后重算。价格为 DeepSeek 官网 2026-10 高峰价(USD/百万 token):
deepseek-flash 输入未命中 0.30 / 缓存命中 0.006 / 输出 1.20。
Langfuse 平台侧计价(models 表)由启动同步托管,配置不进 DB,故在此自算。
"""
from __future__ import annotations

import os
from decimal import Decimal

import httpx
from fastapi import APIRouter, HTTPException, Request

PRICE_TABLE_PER_MTOK: dict[str, dict[str, float]] = {
    "deepseek-flash": {"input": 0.30, "input_cache_read": 0.006, "output": 1.20},
}

DEFAULT_TIER_FALLBACK = "unknown"  # intent 为空的 generation 归入此桶

_QUERY = """
WITH trace_intent AS (
  SELECT trace_id,
         arrayElement(metadata_values, indexOf(metadata_names, 'intent')) AS intent
  FROM default.events_full
  WHERE name = 'chat-turn' AND has(metadata_names, 'intent')
)
SELECT
  coalesce(nullIf(t.intent, ''), 'unknown') AS intent,
  any(g.provided_model_name) AS model,
  count() AS calls,
  sum(g.usage_details['input']) AS input_tokens,
  sum(g.usage_details['input_cache_read']) AS cache_read_tokens,
  sum(g.usage_details['output']) AS output_tokens
FROM default.events_full AS g
LEFT JOIN trace_intent AS t ON t.trace_id = g.trace_id
WHERE g.type = 'GENERATION'
  AND g.start_time >= now() - INTERVAL toUInt32({days}) DAY
GROUP BY intent, g.provided_model_name
ORDER BY calls DESC
FORMAT JSON
"""


def _ch_conf() -> tuple[str, str, str]:
    url = os.getenv("CLICKHOUSE_URL", "http://127.0.0.1:8123")
    user = os.getenv("CLICKHOUSE_USER", "clickhouse")
    password = os.getenv("CLICKHOUSE_PASSWORD", "")
    return url, user, password


def fetch_cost_rows(days: int) -> list[dict]:
    """直查 ClickHouse 聚合;不可达时抛 503(由路由转 HTTPException)。"""
    url, user, password = _ch_conf()
    try:
        resp = httpx.post(
            url, params={"query": _QUERY.format(days=days)},
            auth=(user, password), timeout=10,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
    except httpx.HTTPStatusError:
        raise RuntimeError("ClickHouse 查询失败(认证或权限)") from None
    except httpx.HTTPError:
        raise RuntimeError("Langfuse ClickHouse 不可达") from None

    rows: list[dict] = []
    for r in data:
        model = r.get("model") or "unknown"
        price = PRICE_TABLE_PER_MTOK.get(model)
        tokens = {
            "input": int(r.get("input_tokens") or 0),
            "input_cache_read": int(r.get("cache_read_tokens") or 0),
            "output": int(r.get("output_tokens") or 0),
        }
        if price:  # 未知模型不计价,只计数(避免默认价造成错误成本)
            cost = (
                Decimal(str(tokens["input"])) / 1_000_000 * Decimal(str(price["input"]))
                + Decimal(str(tokens["input_cache_read"])) / 1_000_000 * Decimal(str(price["input_cache_read"]))
                + Decimal(str(tokens["output"])) / 1_000_000 * Decimal(str(price["output"]))
            )
        else:
            cost = Decimal(0)
        rows.append({
            "intent": r.get("intent") or DEFAULT_TIER_FALLBACK,
            "model": model,
            "calls": int(r.get("calls") or 0),
            **tokens,
            "costUsd": float(round(cost, 6)),
        })
    return rows


def create_cost_router() -> APIRouter:
    router = APIRouter()

    @router.get("/api/admin/cost")
    def cost_report(request: Request, days: int = 7):
        from auth import resolve_admin

        resolve_admin(request)
        """按意图聚合的 token 与成本窗口报表(spec §3.3)。"""
        if not 1 <= days <= 90:
            raise HTTPException(status_code=400, detail={"message": "days 需在 1..90"})
        try:
            rows = fetch_cost_rows(days)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail={"message": str(exc)}) from None
        return {
            "window": {"days": days},
            "rows": rows,
            "total": {
                "calls": sum(r["calls"] for r in rows),
                "tokens": sum(r["input"] + r["input_cache_read"] + r["output"] for r in rows),
                "costUsd": round(sum(r["costUsd"] for r in rows), 6),
            },
            "priceTable": PRICE_TABLE_PER_MTOK,
        }

    return router
