package com.fuze.potryservice.cache;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Lazy;
import org.springframework.data.redis.connection.Message;
import org.springframework.data.redis.connection.MessageListener;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;

/**
 * 分布式缓存协同失效监听器 (Redis Pub/Sub Subscriber)
 * 监听 cache:evict:topic，当任意微服务节点执行更新/删除时，广播通知当前 JVM 失效本地 L1 Caffeine 缓存。
 */
@Component
@Slf4j
public class CacheEvictMessageListener implements MessageListener {

    @Autowired
    @Lazy
    private MultiLevelCacheManager multiLevelCacheManager;

    @Override
    public void onMessage(Message message, byte[] pattern) {
        try {
            if (message == null || message.getBody() == null) return;
            String payload = new String(message.getBody(), StandardCharsets.UTF_8);
            log.info("[MultiCache PubSub] 收到多级缓存协同失效广播: {}", payload);

            if (payload.startsWith("POEM:")) {
                Long poemId = Long.valueOf(payload.substring(5).trim());
                multiLevelCacheManager.invalidateLocalPoem(poemId);
            } else if (payload.startsWith("WRITER:")) {
                Integer writerId = Integer.valueOf(payload.substring(7).trim());
                multiLevelCacheManager.invalidateLocalWriter(writerId);
            }
        } catch (Exception e) {
            log.warn("[MultiCache PubSub] 处理多级缓存失效广播异常", e);
        }
    }
}
