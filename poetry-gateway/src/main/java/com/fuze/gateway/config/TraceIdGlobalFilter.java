package com.fuze.gateway.config;

import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import java.util.UUID;

/**
 * traceId 起点: 入口无 X-Trace-Id 则生成,统一向下游服务透传并回写响应头;
 * 下游 potry-service 的 TraceIdFilter 从此头写入 MDC 贯穿日志链路。
 * (网关为 WebFlux 反应式线程模型,MDC/ThreadLocal 不可靠,故网关只负责生成与透传)
 */
@Component
public class TraceIdGlobalFilter implements GlobalFilter, Ordered {

    public static final String TRACE_HEADER = "X-Trace-Id";

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        String traceId = exchange.getRequest().getHeaders().getFirst(TRACE_HEADER);
        if (traceId == null || traceId.isBlank()) {
            traceId = UUID.randomUUID().toString().replace("-", "").substring(0, 16);
        }
        final String tid = traceId;
        ServerWebExchange mutated = exchange.mutate()
                .request(r -> r.headers(h -> h.set(TRACE_HEADER, tid)))
                .build();
        exchange.getResponse().getHeaders().add(TRACE_HEADER, tid);
        return chain.filter(mutated);
    }

    @Override
    public int getOrder() {
        return Ordered.HIGHEST_PRECEDENCE;
    }
}
