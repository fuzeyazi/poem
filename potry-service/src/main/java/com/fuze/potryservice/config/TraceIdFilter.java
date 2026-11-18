package com.fuze.potryservice.config;

import jakarta.servlet.Filter;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.ServletRequest;
import jakarta.servlet.ServletResponse;
import jakarta.servlet.http.HttpServletRequest;
import org.slf4j.MDC;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.util.UUID;

/**
 * 全链路 traceId: 取网关透传的 X-Trace-Id(无则自生成)写入 MDC,
 * 日志 pattern 输出 [traceId]; MQ 生产者在同线程 afterCommit 投递时读取 MDC 继续透传,
 * 消费者取出回填 MDC —— 一个发帖请求的日志可贯穿 网关→服务→MQ消费者 串联检索
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class TraceIdFilter implements Filter {

    public static final String TRACE_HEADER = "X-Trace-Id";

    @Override
    public void doFilter(ServletRequest req, ServletResponse resp, FilterChain chain)
            throws IOException, ServletException {
        HttpServletRequest request = (HttpServletRequest) req;
        String traceId = request.getHeader(TRACE_HEADER);
        if (traceId == null || traceId.isBlank()) {
            traceId = newTraceId();
        }
        MDC.put("traceId", traceId);
        try {
            chain.doFilter(req, resp);
        } finally {
            MDC.remove("traceId");
        }
    }

    static String newTraceId() {
        return UUID.randomUUID().toString().replace("-", "").substring(0, 16);
    }
}
