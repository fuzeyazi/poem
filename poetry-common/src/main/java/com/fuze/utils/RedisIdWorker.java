package com.fuze.utils;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;

@Component
public class RedisIdWorker {
    private static final int COUNT_BITS = 32;
    // 基准时间戳：2024-11-16 00:00:00 UTC，秒级时间戳 (约 1731715200L)
    private static final long BEGIN_TIMESTAMP = 1731715200L;

    @Autowired
    private StringRedisTemplate stringRedisTemplate;

    /**
     * 生成全局唯一分布式有序 ID
     * 结构：1位符号位(0) + 31位时间戳差值(秒) + 32位 Redis 自增序列号
     *
     * @param keyprefix 业务前缀
     * @return 64 位正整型分布式 ID
     */
    public long nextId(String keyprefix) {
        LocalDateTime now = LocalDateTime.now();
        long nowSecond = now.toEpochSecond(ZoneOffset.UTC);
        long timestampDelta = nowSecond - BEGIN_TIMESTAMP;

        // 获取当天的时间作为 key 维度
        String format = now.format(DateTimeFormatter.ofPattern("yyyy:MM:dd"));
        // Redis 原子自增
        Long count = stringRedisTemplate.opsForValue().increment("icr:" + keyprefix + ":" + format);
        long sequence = (count != null) ? count : 0L;

        // 时间戳差值左移 32 位并拼接序列号
        return (timestampDelta << COUNT_BITS) | sequence;
    }
}
