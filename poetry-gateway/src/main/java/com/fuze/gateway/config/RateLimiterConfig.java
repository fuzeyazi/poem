package com.fuze.gateway.config;

import org.springframework.cloud.gateway.filter.ratelimit.KeyResolver;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import reactor.core.publisher.Mono;

/**
 * 限流键解析:按来源IP(经X-Forwarded-For/远程地址),配合 yml 中 RequestRateLimiter 使用
 */
@Configuration
public class RateLimiterConfig {

    @Bean
    public KeyResolver ipKeyResolver() {
        return exchange -> {
            String ip = exchange.getRequest().getHeaders().getFirst("X-Forwarded-For");
            if (ip != null && !ip.isBlank()) {
                // 多层代理场景下取首个客户端IP，防止头部伪造与逗号拼接
                int commaIdx = ip.indexOf(',');
                if (commaIdx >= 0) {
                    ip = ip.substring(0, commaIdx).trim();
                } else {
                    ip = ip.trim();
                }
            } else {
                ip = exchange.getRequest().getRemoteAddress() != null
                        ? exchange.getRequest().getRemoteAddress().getAddress().getHostAddress()
                        : "unknown";
            }
            return Mono.just(ip);
        };
    }
}
