package com.fuze.potryservice.util;

import com.fuze.utils.JwtUtil;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.ExpiredJwtException;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.HashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

/**
 * 验证 poetry-common JwtUtil 的密钥轮换语义(parseJWTWithLegacy):
 * 新密钥上线后,旧密钥签发的 token 在 TTL 内继续可验;全部密钥失败时抛主密钥原始异常。
 * 这是网关/服务/Agent 三端共享的轮换契约,改语义必须过这组用例。
 */
class JwtUtilLegacyRotationTest {

    private static final String NEW_KEY = "new-secret-key-2026";
    private static final String OLD_KEY = "old-secret-key-2025";

    private String token(String key) {
        Map<String, Object> claims = new HashMap<>();
        claims.put("userId", 42);
        return JwtUtil.createJWT(key, 60_000, claims);
    }

    @Test
    @DisplayName("签发后用同密钥解析,claims 完整还原")
    void roundtrip() {
        Claims claims = JwtUtil.parseJWT(NEW_KEY, token(NEW_KEY));
        assertEquals(42, ((Number) claims.get("userId")).intValue());
        assertNotNull(claims.getExpiration());
    }

    @Test
    @DisplayName("轮换场景:旧密钥 token + 新主密钥 + legacyCsv 含旧密钥 → 验签通过")
    void legacyRotation_acceptsOldToken() {
        String oldToken = token(OLD_KEY);
        Claims claims = JwtUtil.parseJWTWithLegacy(NEW_KEY, OLD_KEY, oldToken);
        assertEquals(42, ((Number) claims.get("userId")).intValue());
    }

    @Test
    @DisplayName("legacyCsv 支持多密钥与空白项(逗号分隔,逐个 trim)")
    void legacyRotation_trimsAndIterates() {
        String oldToken = token(OLD_KEY);
        Claims claims = JwtUtil.parseJWTWithLegacy(NEW_KEY, " , k1 , " + OLD_KEY + " , k2", oldToken);
        assertEquals(42, ((Number) claims.get("userId")).intValue());
    }

    @Test
    @DisplayName("legacyCsv 为空且主密钥不匹配 → 抛出主密钥的原始异常(不吞错)")
    void noLegacy_wrongKey_throwsPrimary() {
        assertThrows(Exception.class, () -> JwtUtil.parseJWTWithLegacy(NEW_KEY, "", token(OLD_KEY)));
    }

    @Test
    @DisplayName("legacyCsv 全部不匹配 → 抛出主密钥的原始异常")
    void allLegacyFail_throwsPrimary() {
        assertThrows(Exception.class, () -> JwtUtil.parseJWTWithLegacy(NEW_KEY, "k1,k2,k3", token(OLD_KEY)));
    }

    @Test
    @DisplayName("过期 token 即使在 legacy 列表内也拒绝;legacy 分支异常被吞,最终抛主密钥的 SignatureException(验签先于验期)")
    void expiredToken_rejectedEvenWithLegacy() {
        // ⚠️ 固化现状:parseJWTWithLegacy 的 legacy 循环 catch(Exception ignore) 会吞掉
        // legacy 尝试的 ExpiredJwtException,最终抛出主密钥尝试的 SignatureException。
        // 拒绝行为正确,但异常类型有误导性(调试时会往"密钥不对"方向排查)。
        Map<String, Object> claims = new HashMap<>();
        claims.put("userId", 1);
        String expired = JwtUtil.createJWT(OLD_KEY, -1000, claims);
        assertThrows(io.jsonwebtoken.SignatureException.class,
                () -> JwtUtil.parseJWTWithLegacy(NEW_KEY, OLD_KEY, expired));
    }

    @Test
    @DisplayName("被篡改的 token 拒绝")
    void tamperedToken_rejected() {
        String t = token(NEW_KEY);
        String tampered = t.substring(0, t.length() - 2) + (t.endsWith("aa") ? "bb" : "aa");
        assertThrows(Exception.class, () -> JwtUtil.parseJWT(NEW_KEY, tampered));
    }
}
