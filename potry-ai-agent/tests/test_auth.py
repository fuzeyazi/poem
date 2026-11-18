"""Ch09 打通(一):JWT 验签单测 —— 与 Java 侧 HS256/token 头/claims.userId 契约对齐。"""
import time

import jwt
import pytest
from fastapi import HTTPException

from auth import resolve_user_id

SECRET = "publication-placeholder-jwt_user_secret"  # 与 Java application.yml userSecretKey 一致(测试专用)


class _FakeRequest:
    def __init__(self, token: str | None) -> None:
        self.headers = {"token": token} if token else {}


def _mint(user_id=7, exp_offset=3600, secret=SECRET):
    return jwt.encode(
        {"userId": user_id, "exp": int(time.time()) + exp_offset, "dgarreId": 99},
        secret, algorithm="HS256",
    )


def test_no_token_falls_back_to_claimed(monkeypatch):
    monkeypatch.setenv("JWT_USER_SECRET_KEY", SECRET)
    assert resolve_user_id(_FakeRequest(None), "u-raw") == "u-raw"


def test_valid_token_overrides_claimed(monkeypatch):
    monkeypatch.setenv("JWT_USER_SECRET_KEY", SECRET)
    req = _FakeRequest(_mint(user_id=7))
    assert resolve_user_id(req, "someone-else") == "7"


def test_expired_token_rejected(monkeypatch):
    monkeypatch.setenv("JWT_USER_SECRET_KEY", SECRET)
    req = _FakeRequest(_mint(exp_offset=-10))
    with pytest.raises(HTTPException) as e:
        resolve_user_id(req, "u-raw")
    assert e.value.status_code == 401


def test_wrong_secret_rejected(monkeypatch):
    monkeypatch.setenv("JWT_USER_SECRET_KEY", SECRET)
    req = _FakeRequest(_mint(secret="not-the-secret"))
    with pytest.raises(HTTPException) as e:
        resolve_user_id(req, "u-raw")
    assert e.value.status_code == 401


def test_token_without_userid_claim_rejected(monkeypatch):
    monkeypatch.setenv("JWT_USER_SECRET_KEY", SECRET)
    token = jwt.encode({"exp": int(time.time()) + 60}, SECRET, algorithm="HS256")
    with pytest.raises(HTTPException) as e:
        resolve_user_id(_FakeRequest(token), "u-raw")
    assert e.value.status_code == 401


def test_strict_mode_requires_token(monkeypatch):
    monkeypatch.setenv("JWT_USER_SECRET_KEY", SECRET)
    monkeypatch.setenv("AUTH_STRICT", "1")
    with pytest.raises(HTTPException) as e:
        resolve_user_id(_FakeRequest(None), "u-raw")
    assert e.value.status_code == 401


def test_unconfigured_secret_ignores_token(monkeypatch):
    monkeypatch.delenv("JWT_USER_SECRET_KEY", raising=False)
    # .env 经 load_dotenv 注入,先摘掉;未配置密钥时不验签(本地演示模式)
    assert resolve_user_id(_FakeRequest(_mint()), "u-raw") == "u-raw"
