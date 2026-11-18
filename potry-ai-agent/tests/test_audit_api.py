"""Ch09 管理补全:工具审计 API + 管理端鉴权契约。"""
import time

import jwt as pyjwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app_storage import AppBase, AppStorage
from audit_api import create_audit_router

ADMIN_SECRET = "test-admin-secret"


def _seeded_client(monkeypatch, admin_secret=""):
    """内存库 + 预置两条审计;admin_secret 空串=开放模式。"""
    monkeypatch.setenv("ADMIN_JWT_SECRET_KEY", admin_secret)
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    AppBase.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    AppStorage(factory).add_tool_audit(
        session_id="s1", tool_call_id="c1", tool_name="query_poem",
        source="builtin", arguments='{"q":"月"}', result_summary='{"ok":true}',
        status="done", duration_ms=12,
    )
    AppStorage(factory).add_tool_audit(
        session_id="s1", tool_call_id="c2", tool_name="create_ticket",
        source="builtin", arguments="{}", result_summary="{}",
        status="error", error="boom", retry_count=1, duration_ms=30,
    )
    app = FastAPI()
    app.include_router(create_audit_router(factory))
    return TestClient(app), factory


def test_audit_list_open_mode(monkeypatch):
    client, _ = _seeded_client(monkeypatch, admin_secret="")
    r = client.get("/api/admin/audit")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert body["rows"][0]["toolName"] == "create_ticket"  # 新在前
    assert body["rows"][0]["status"] == "error"


def test_audit_filter_by_tool(monkeypatch):
    client, _ = _seeded_client(monkeypatch, admin_secret="")
    r = client.get("/api/admin/audit", params={"tool_name": "query_poem"})
    assert r.json()["total"] == 1
    assert r.json()["rows"][0]["durationMs"] == 12


def test_audit_requires_admin_token_when_configured(monkeypatch):
    client, _ = _seeded_client(monkeypatch, admin_secret=ADMIN_SECRET)
    assert client.get("/api/admin/audit").status_code == 401
    token = pyjwt.encode(
        {"userId": 1, "exp": int(time.time()) + 600}, ADMIN_SECRET, algorithm="HS256"
    )
    r = client.get("/api/admin/audit", headers={"token": token})
    assert r.status_code == 200 and r.json()["total"] == 2


def test_audit_rejects_user_token_for_admin(monkeypatch):
    """用户端密钥签的 token 不能过管理端(密钥隔离)。"""
    client, _ = _seeded_client(monkeypatch, admin_secret=ADMIN_SECRET)
    user_token = pyjwt.encode(
        {"userId": 7, "exp": int(time.time()) + 600}, "publication-placeholder-jwt_user_secret", algorithm="HS256"
    )
    assert client.get("/api/admin/audit", headers={"token": user_token}).status_code == 401
