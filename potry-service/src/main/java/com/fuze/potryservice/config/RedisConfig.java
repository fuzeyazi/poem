package com.fuze.potryservice.config;

import com.fuze.potryservice.cache.CacheEvictMessageListener;
import com.fuze.potryservice.cache.MultiLevelCacheManager;
import org.redisson.Redisson;
import org.redisson.api.RedissonClient;
import org.redisson.config.Config;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.listener.ChannelTopic;
import org.springframework.data.redis.listener.RedisMessageListenerContainer;
import org.springframework.data.redis.listener.adapter.MessageListenerAdapter;

@Configuration
public class RedisConfig {
    @Bean
    public RedissonClient redissonClient(){
        Config config = new Config();
        config.useSingleServer().setAddress("redis://127.0.0.1:6379");
        return Redisson.create(config);
    }

    @Bean
    public RedisMessageListenerContainer redisMessageListenerContainer(
            RedisConnectionFactory connectionFactory,
            MessageListenerAdapter cacheEvictListenerAdapter) {
        RedisMessageListenerContainer container = new RedisMessageListenerContainer();
        container.setConnectionFactory(connectionFactory);
        container.addMessageListener(cacheEvictListenerAdapter, new ChannelTopic(MultiLevelCacheManager.CACHE_EVICT_TOPIC));
        return container;
    }

    @Bean
    public MessageListenerAdapter cacheEvictListenerAdapter(CacheEvictMessageListener listener) {
        return new MessageListenerAdapter(listener, "onMessage");
    }
}
