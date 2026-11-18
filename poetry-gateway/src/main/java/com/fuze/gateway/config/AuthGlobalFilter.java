package com.fuze.gateway.config;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.http.server.reactive.ServerHttpResponse;
import org.springframework.stereotype.Component;
import org.springframework.util.AntPathMatcher;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import java.nio.charset.StandardCharsets;
import java.util.List;

/**
 * 网关统一鉴权:按路径前缀选择密钥实现角色隔离——
 * /admin/** /notice/** 用管理端密钥(adminSecretKey),/user/** /ai/** /agent/** 用用户端密钥(userSecretKey);
 * 普通用户token在admin路径必然验签失败,白名单放行登录注册等;服务端拦截器作第二道防线。
 * SSE 的 EventSource 无法自定义请求头,前端经 query 参数携带 token,两者兼容。
 */
@Component
public class AuthGlobalFilter implements GlobalFilter, Ordered {

    private static final List<String> USER_PROTECTED = List.of("/user/**", "/ai/**", "/agent/**");
    private static final List<String> ADMIN_PROTECTED = List.of("/admin/**", "/notice/**");
    private static final List<String> WHITELIST = List.of(
            "/user/login", "/user/register", "/user/login/code", "/user/login/email", "/user/forget",
            "/admin/login", "/admin/getCode", "/admin/login/code",
            "/notice/get", "/notice/getList");  //游客可见公告接口

    private final AntPathMatcher matcher = new AntPathMatcher();

    @Value("${gateway.jwt.secret}")
    private String userSecret;

    @Value("${gateway.jwt.admin-secret}")
    private String adminSecret;

    @Value("${gateway.jwt.user-legacy-secrets:}")
    private String userLegacySecrets;
    @Value("${gateway.jwt.admin-legacy-secrets:}")
    private String adminLegacySecrets;

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        ServerHttpRequest request = exchange.getRequest();
        String path = request.getURI().getPath();

        // 安全防御: 彻底剔除外部客户端可能伪造的内部透传请求头
        ServerHttpRequest.Builder reqBuilder = request.mutate();
        reqBuilder.headers(headers -> {
            headers.remove("X-User-Id");
            headers.remove("X-Internal-Token");
            headers.remove("X-Internal-User");
        });

        if (HttpMethod.OPTIONS.equals(request.getMethod()) || isWhitelisted(path)) {
            return chain.filter(exchange.mutate().request(reqBuilder.build()).build());
        }
        boolean isAdmin = ADMIN_PROTECTED.stream().anyMatch(p -> matcher.match(p, path));
        boolean isUser = USER_PROTECTED.stream().anyMatch(p -> matcher.match(p, path));
        if (!isAdmin && !isUser) {
            return chain.filter(exchange.mutate().request(reqBuilder.build()).build());
        }
        String secret = isAdmin ? adminSecret : userSecret;
        String token = request.getHeaders().getFirst("token");
        if (token == null || token.isEmpty()) {
            token = request.getQueryParams().getFirst("token");
        }
        try {
            Claims claims = verifyWithLegacy(secret,
                    (isAdmin ? adminLegacySecrets : userLegacySecrets).split(","), token);
            // 验签通过, 由网关权威写入用户/管理员id透传给下游服务
            ServerHttpRequest mutated = reqBuilder
                    .header("X-User-Id", String.valueOf(claims.get("userId")))
                    .build();
            return chain.filter(exchange.mutate().request(mutated).build());
        } catch (Exception e) {
            ServerHttpResponse response = exchange.getResponse();
            response.setStatusCode(HttpStatus.UNAUTHORIZED);
            response.getHeaders().setContentType(MediaType.APPLICATION_JSON);
            String body = isAdmin
                    ? "{\"status\":401,\"message\":\"管理员未登录或凭证无效\"}"
                    : "{\"status\":401,\"message\":\"token无效或已过期\"}";
            DataBuffer buffer = response.bufferFactory().wrap(body.getBytes(StandardCharsets.UTF_8));
            return response.writeWith(Mono.just(buffer));
        }
    }

    private boolean isWhitelisted(String path) {
        return WHITELIST.stream().anyMatch(p -> matcher.match(p, path));
    }

    @Override
    public int getOrder() {
        return -100;
    }

    /**
     * 密钥轮换过渡: 主密钥验签失败依次尝试legacy旧密钥(与potry-service的
     * JwtUtil.parseJWTWithLegacy同语义),旧token在TTL内继续可用
     */
    private Claims verifyWithLegacy(String primarySecret, String[] legacySecrets, String token) {
        try {
            return Jwts.parser()
                    .setSigningKey(primarySecret.getBytes(StandardCharsets.UTF_8))
                    .parseClaimsJws(token)
                    .getBody();
        } catch (Exception primaryEx) {
            if (legacySecrets != null) {
                for (String legacy : legacySecrets) {
                    String k = legacy.trim();
                    if (k.isEmpty()) {
                        continue;
                    }
                    try {
                        return Jwts.parser()
                                .setSigningKey(k.getBytes(StandardCharsets.UTF_8))
                                .parseClaimsJws(token)
                                .getBody();
                    } catch (Exception ignore) {
                    }
                }
            }
            throw primaryEx;
        }
    }

}
