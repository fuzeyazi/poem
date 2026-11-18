"""Ch09 打通(一):与 Java 侧(potry-service)共享密钥的 JWT 验签。

Java 端用户 token:HS256、密钥 UTF-8 字节(JwtUtil.signWith)、请求头 `token`
(application.yml userTokenName),claims 含 userId / exp / dgarreId。

策略(向后兼容既有聊天页 / evals 验收脚本):
- 带了 token:验签失败或过期 → 401;成功 → 以 claims.userId 为准(忽略请求体裸传值);
- 未带 token:回退请求体 userId(遗留本地模式);`.env` 配 AUTH_STRICT=1 后无 token 一律 401。
"""
from __future__ import annotations

import os

import jwt
from fastapi import HTTPException, Request

_HEADER = "token"  # 与 Java 侧 application.yml 的 userTokenName 一致
_CLAIM_USER_ID = "userId"


def _secret() -> str | None:
    value = os.getenv("JWT_USER_SECRET_KEY", "").strip()
    return value or None


def _legacy_secrets() -> list[str]:
    """密钥轮换过渡(与 Java 侧 JWT_USER_LEGACY_KEYS 同源): 主密钥验签失败依次回退旧密钥,
    旧 token 在 TTL 内继续有效,实现三端(Java/网关/agent)同步无缝轮换。"""
    raw = os.getenv("JWT_USER_LEGACY_KEYS", "")
    return [k.strip() for k in raw.split(",") if k.strip()]


def resolve_user_id(request: Request, claimed: str | None) -> str | None:
    """从请求头 token 验签解析真实 userId;无可信身份时回退/拒绝。"""
    secret = _secret()
    token = request.headers.get(_HEADER)
    strict = os.getenv("AUTH_STRICT") == "1"
    if not token:
        if strict:
            raise HTTPException(
                status_code=401, detail={"message": "缺少 token,请先登录"}
            )
        return claimed  # 遗留模式:本地聊天页/验收脚本不带 token
    if not secret:
        return claimed  # 未配置密钥则不验签(本地演示)
    claims = None
    err: jwt.PyJWTError | None = None
    for key in [secret, *_legacy_secrets()]:
        try:
            claims = jwt.decode(token, key, algorithms=["HS256"])
            break
        except jwt.PyJWTError as exc:
            err = err or exc
    if claims is None:
        raise HTTPException(
            status_code=401, detail={"message": f"token 无效: {type(err).__name__}"}
        ) from None
    user_id = claims.get(_CLAIM_USER_ID)
    if user_id is None:
        raise HTTPException(
            status_code=401, detail={"message": "token 缺少 userId 声明"}
        )
    return str(user_id)


def resolve_admin(request: Request) -> None:
    """管理端接口鉴权:配置了 ADMIN_JWT_SECRET_KEY(与 Java admin-secret-key 同值)时,
    /api/admin/** 必须携带有效的管理端 token(HS256,claims.userId);未配置则开放(本地演示)。
    静态页(/admin/*)本身不设防,由其调用的 API 把关。"""
    secret = os.getenv("ADMIN_JWT_SECRET_KEY", "").strip()
    if not secret:
        return
    token = request.headers.get(_HEADER)
    if not token:
        raise HTTPException(status_code=401, detail={"message": "管理接口需要 token"})
    try:
        claims = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=401, detail={"message": f"管理 token 无效: {type(exc).__name__}"}
        ) from None
    if claims.get(_CLAIM_USER_ID) is None:
        raise HTTPException(status_code=401, detail={"message": "管理 token 缺少 userId 声明"})
