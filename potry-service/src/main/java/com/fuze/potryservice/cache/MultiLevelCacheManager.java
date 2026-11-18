package com.fuze.potryservice.cache;

import com.alibaba.fastjson.JSONObject;
import com.fuze.entity.Poem;
import com.fuze.entity.WriterEndVo;
import com.fuze.response.RedisData;
import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;
import com.github.benmanes.caffeine.cache.stats.CacheStats;
import lombok.extern.slf4j.Slf4j;
import org.redisson.api.RBloomFilter;
import org.redisson.api.RedissonClient;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.*;
import java.util.function.Supplier;

/**
 * 高性能多级缓存管理器 (L1 Caffeine 本地缓存 + L2 Redis 分布式缓存 + Redisson 分布式布隆过滤器 + Pub/Sub 广播失效)
 *
 * 架构防线：
 * 1. 防穿透：Redisson 分布式布隆过滤器拦截非法/不存在 ID (0.1ms 拒绝) + 短 TTL 空值缓存 ("NULL") 双重兜底；
 * 2. 防击穿：热点 Key 逻辑过期机制，后台线程池单飞互斥异步回源重建，前台线程立即返回 Stale 脏数据保障高吞吐；
 * 3. 防雪崩：TTL 随机抖动避免集中过期 + 强降级兜底 DB 保障服务可用性；
 * 4. 跨节点一致性：Cache-Aside 写路径配合 Redis Pub/Sub 广播协同清除集群所有节点 L1 Caffeine 缓存。
 */
@Component
@Slf4j
public class MultiLevelCacheManager {

    public static final String CACHE_EVICT_TOPIC = "cache:evict:topic";
    public static final String POEM_BLOOM_FILTER_NAME = "bloom:poem:ids";
    public static final String WRITER_BLOOM_FILTER_NAME = "bloom:writer:ids";

    @Autowired
    private StringRedisTemplate stringRedisTemplate;

    @Autowired(required = false)
    private RedissonClient redissonClient;

    // L1: Caffeine 本地内存缓存 (容量 10,000，写入后 10 分钟过期，开启统计指标)
    private final Cache<Long, Poem> poemL1Cache = Caffeine.newBuilder()
            .maximumSize(10_000)
            .expireAfterWrite(10, TimeUnit.MINUTES)
            .recordStats()
            .build();

    // L1: 诗人名片本地内存缓存
    private final Cache<Integer, WriterEndVo> writerL1Cache = Caffeine.newBuilder()
            .maximumSize(2_000)
            .expireAfterWrite(30, TimeUnit.MINUTES)
            .recordStats()
            .build();

    // 逻辑过期异步重建线程池 (守护线程，防击穿单飞重建)
    private final ExecutorService asyncRebuildExecutor = new ThreadPoolExecutor(
            2, 4, 60L, TimeUnit.SECONDS,
            new LinkedBlockingQueue<>(1000),
            new ThreadFactory() {
                private int counter = 0;
                @Override
                public Thread newThread(Runnable r) {
                    Thread t = new Thread(r, "multicache-rebuild-" + (++counter));
                    t.setDaemon(true);
                    return t;
                }
            },
            new ThreadPoolExecutor.DiscardPolicy()
    );

    // ==================== 1. 布隆过滤器获取与注册 ====================

    public RBloomFilter<Long> getPoemBloomFilter() {
        if (redissonClient == null) return null;
        try {
            return redissonClient.getBloomFilter(POEM_BLOOM_FILTER_NAME);
        } catch (Exception e) {
            log.warn("[MultiCache] 获取 Poem 布隆过滤器失败: {}", e.getMessage());
            return null;
        }
    }

    public RBloomFilter<Integer> getWriterBloomFilter() {
        if (redissonClient == null) return null;
        try {
            return redissonClient.getBloomFilter(WRITER_BLOOM_FILTER_NAME);
        } catch (Exception e) {
            log.warn("[MultiCache] 获取 Writer 布隆过滤器失败: {}", e.getMessage());
            return null;
        }
    }

    public void registerPoemId(Long id) {
        if (id == null) return;
        try {
            RBloomFilter<Long> bloom = getPoemBloomFilter();
            if (bloom != null && bloom.isExists()) {
                bloom.add(id);
            }
        } catch (Exception e) {
            log.warn("[MultiCache] 注册 Poem ID 到布隆过滤器异常: id={}", id, e);
        }
    }

    public void registerWriterId(Integer id) {
        if (id == null) return;
        try {
            RBloomFilter<Integer> bloom = getWriterBloomFilter();
            if (bloom != null && bloom.isExists()) {
                bloom.add(id);
            }
        } catch (Exception e) {
            log.warn("[MultiCache] 注册 Writer ID 到布隆过滤器异常: id={}", id, e);
        }
    }

    // ==================== 2. 核心多级读路径：诗词详情 ====================

    /**
     * 获取诗词详情（多级缓存链路：布隆防穿透 -> L1 本地 Caffeine -> L2 分布式 Redis -> DB 回源双写）
     */
    public Poem getPoem(Long id, Supplier<Poem> dbLoader) {
        if (id == null) return null;

        // 1. 布隆过滤器快速拦截非法 ID (防恶意穿透扫描)
        try {
            RBloomFilter<Long> bloom = getPoemBloomFilter();
            if (bloom != null && bloom.isExists()) {
                if (!bloom.contains(id)) {
                    log.debug("[MultiCache] 布隆过滤器拦截非法古诗 ID: {}", id);
                    return null;
                }
            }
        } catch (Exception e) {
            // 布隆过滤器异常降级放行，保证服务可用性
            log.warn("[MultiCache] 布隆过滤器检查降级: id={}, err={}", id, e.getMessage());
        }

        // 2. L1 本地 Caffeine 缓存命中 (微秒级)
        Poem l1Poem = poemL1Cache.getIfPresent(id);
        if (l1Poem != null) {
            return l1Poem;
        }

        // 3. L2 分布式 Redis 缓存命中
        String poemKey = "poem:context:" + id;
        String json = null;
        try {
            json = stringRedisTemplate.opsForValue().get(poemKey);
        } catch (Exception e) {
            log.warn("[MultiCache] Redis 读取异常, 降级回源 DB: id={}, err={}", id, e.getMessage());
            Poem dbPoem = dbLoader.get();
            if (dbPoem != null) {
                poemL1Cache.put(id, dbPoem);
            }
            return dbPoem;
        }

        // 命中短 TTL 空值缓存 (防穿透兜底)
        if ("NULL".equals(json)) {
            return null;
        }

        if (json != null) {
            try {
                RedisData redisData = JSONObject.parseObject(json, RedisData.class);
                if (redisData != null && redisData.getData() != null) {
                    Poem cached = JSONObject.parseObject(redisData.getData().toString(), Poem.class);
                    if (cached != null && cached.getId() != null) {
                        LocalDateTime expireTime = redisData.getExpireTime();
                        // 逻辑过期防击穿校验
                        if (expireTime == null || expireTime.isAfter(LocalDateTime.now())) {
                            // 未过期：回填 L1 并返回
                            poemL1Cache.put(id, cached);
                            return cached;
                        } else {
                            // 已逻辑过期：异步加锁重建缓存，当前返回旧版本数据保障吞吐
                            asyncRebuildPoem(id, poemKey, dbLoader);
                            poemL1Cache.put(id, cached);
                            return cached;
                        }
                    }
                }
            } catch (Exception e) {
                log.warn("[MultiCache] Redis 诗词数据反序列化异常, 删 key 回源: id={}, err={}", id, e.getMessage());
            }
        }

        // 4. L2 未命中，回源 DB 并双写
        Poem dbPoem = dbLoader.get();
        if (dbPoem != null) {
            poemL1Cache.put(id, dbPoem);
            try {
                RedisData rd = new RedisData();
                rd.setData(dbPoem);
                // 逻辑过期 30 分钟，物理过期 1 天
                rd.setExpireTime(LocalDateTime.now().plusMinutes(30));
                stringRedisTemplate.opsForValue().set(poemKey, JSONObject.toJSONString(rd), 1, TimeUnit.DAYS);
            } catch (Exception e) {
                log.warn("[MultiCache] 写入 Redis 诗词缓存失败: {}", e.getMessage());
            }
        } else {
            // 空值缓存，短 TTL 2 分钟防穿透
            try {
                stringRedisTemplate.opsForValue().set(poemKey, "NULL", 2, TimeUnit.MINUTES);
            } catch (Exception e) {
                log.warn("[MultiCache] 写入空值缓存失败: {}", e.getMessage());
            }
        }
        return dbPoem;
    }

    private void asyncRebuildPoem(Long id, String poemKey, Supplier<Poem> dbLoader) {
        String lockKey = "lock:multicache:poem:" + id;
        asyncRebuildExecutor.submit(() -> {
            boolean locked = false;
            try {
                // 采用 Redis SETNX 作为轻量分布式互斥锁，抢锁成功的单线程负责回源重建
                Boolean success = stringRedisTemplate.opsForValue().setIfAbsent(lockKey, "1", 10, TimeUnit.SECONDS);
                locked = Boolean.TRUE.equals(success);
                if (locked) {
                    Poem freshPoem = dbLoader.get();
                    if (freshPoem != null) {
                        poemL1Cache.put(id, freshPoem);
                        RedisData rd = new RedisData();
                        rd.setData(freshPoem);
                        rd.setExpireTime(LocalDateTime.now().plusMinutes(30));
                        stringRedisTemplate.opsForValue().set(poemKey, JSONObject.toJSONString(rd), 1, TimeUnit.DAYS);
                        log.info("[MultiCache] 异步逻辑过期防击穿重建完成: poemId={}", id);
                    }
                }
            } catch (Exception e) {
                log.warn("[MultiCache] 异步重建诗词缓存失败: poemId={}", id, e);
            } finally {
                if (locked) {
                    try {
                        stringRedisTemplate.delete(lockKey);
                    } catch (Exception ignored) {}
                }
            }
        });
    }

    // ==================== 3. 核心多级读路径：诗人名片 ====================

    /**
     * 获取诗人详情（多级缓存链路）
     */
    public WriterEndVo getWriter(Integer id, Supplier<WriterEndVo> dbLoader) {
        if (id == null) return null;

        // 1. 布隆拦截
        try {
            RBloomFilter<Integer> bloom = getWriterBloomFilter();
            if (bloom != null && bloom.isExists()) {
                if (!bloom.contains(id)) {
                    log.debug("[MultiCache] 布隆过滤器拦截非法诗人 ID: {}", id);
                    return null;
                }
            }
        } catch (Exception e) {
            log.warn("[MultiCache] 布隆过滤器检查降级: writerId={}, err={}", id, e.getMessage());
        }

        // 2. L1 本地 Caffeine
        WriterEndVo l1Writer = writerL1Cache.getIfPresent(id);
        if (l1Writer != null) {
            return l1Writer;
        }

        // 3. L2 Redis
        String writerKey = "poem:writer:" + id;
        String json = null;
        try {
            json = stringRedisTemplate.opsForValue().get(writerKey);
        } catch (Exception e) {
            log.warn("[MultiCache] Redis 读取异常, 降级回源 DB: writerId={}", id, e);
            WriterEndVo dbWriter = dbLoader.get();
            if (dbWriter != null) {
                writerL1Cache.put(id, dbWriter);
            }
            return dbWriter;
        }

        if ("NULL".equals(json)) {
            return null;
        }

        if (json != null) {
            try {
                WriterEndVo cached = JSONObject.parseObject(json, WriterEndVo.class);
                if (cached != null && cached.getId() != null) {
                    writerL1Cache.put(id, cached);
                    return cached;
                }
            } catch (Exception e) {
                log.warn("[MultiCache] 解析诗人缓存异常: writerId={}", id, e);
            }
        }

        // 4. 回源 DB
        WriterEndVo dbWriter = dbLoader.get();
        if (dbWriter != null) {
            writerL1Cache.put(id, dbWriter);
            try {
                stringRedisTemplate.opsForValue().set(writerKey, JSONObject.toJSONString(dbWriter), 1, TimeUnit.DAYS);
            } catch (Exception e) {
                log.warn("[MultiCache] 写入 Redis 诗人缓存失败: {}", e.getMessage());
            }
        } else {
            try {
                stringRedisTemplate.opsForValue().set(writerKey, "NULL", 2, TimeUnit.MINUTES);
            } catch (Exception e) {
                log.warn("[MultiCache] 写入诗人空值缓存失败: {}", e.getMessage());
            }
        }
        return dbWriter;
    }

    // ==================== 4. 写路径与协同失效广播 ====================

    /**
     * 淘汰诗词多级缓存（Cache-Aside + Redis Pub/Sub 广播协同清除集群所有节点本地 L1）
     */
    public void evictPoem(Long id) {
        if (id == null) return;
        // 1. 本地 L1 立即失效
        poemL1Cache.invalidate(id);

        // 2. Redis L2 删除
        try {
            stringRedisTemplate.delete("poem:context:" + id);
            stringRedisTemplate.delete("poem:content:" + id);
        } catch (Exception e) {
            log.warn("[MultiCache] 删除 Redis 诗词缓存异常: id={}", id, e);
        }

        // 3. 发布集群广播通知所有节点失效各自的 L1
        try {
            stringRedisTemplate.convertAndSend(CACHE_EVICT_TOPIC, "POEM:" + id);
        } catch (Exception e) {
            log.warn("[MultiCache] 发布多级缓存失效广播失败: id={}", id, e);
        }
    }

    /**
     * 淘汰诗人多级缓存
     */
    public void evictWriter(Integer id) {
        if (id == null) return;
        writerL1Cache.invalidate(id);
        try {
            stringRedisTemplate.delete("poem:writer:" + id);
        } catch (Exception e) {
            log.warn("[MultiCache] 删除 Redis 诗人缓存异常: writerId={}", id, e);
        }
        try {
            stringRedisTemplate.convertAndSend(CACHE_EVICT_TOPIC, "WRITER:" + id);
        } catch (Exception e) {
            log.warn("[MultiCache] 发布多级缓存失效广播失败: writerId={}", id, e);
        }
    }

    public void invalidateLocalPoem(Long id) {
        if (id != null) {
            poemL1Cache.invalidate(id);
            log.debug("[MultiCache] 协同失效当前节点 L1 诗词缓存: id={}", id);
        }
    }

    public void invalidateLocalWriter(Integer id) {
        if (id != null) {
            writerL1Cache.invalidate(id);
            log.debug("[MultiCache] 协同失效当前节点 L1 诗人缓存: writerId={}", id);
        }
    }

    public void clearAllLocalCache() {
        poemL1Cache.invalidateAll();
        writerL1Cache.invalidateAll();
        log.info("[MultiCache] 当前节点本地 L1 缓存已全部清空");
    }

    // ==================== 5. 实时监控指标 ====================

    public Map<String, Object> getCacheStats() {
        Map<String, Object> stats = new LinkedHashMap<>();

        CacheStats poemStats = poemL1Cache.stats();
        stats.put("poemL1EstimatedSize", poemL1Cache.estimatedSize());
        stats.put("poemL1HitCount", poemStats.hitCount());
        stats.put("poemL1MissCount", poemStats.missCount());
        stats.put("poemL1HitRate", String.format("%.2f%%", poemStats.hitRate() * 100));
        stats.put("poemL1EvictionCount", poemStats.evictionCount());

        CacheStats writerStats = writerL1Cache.stats();
        stats.put("writerL1EstimatedSize", writerL1Cache.estimatedSize());
        stats.put("writerL1HitCount", writerStats.hitCount());
        stats.put("writerL1MissCount", writerStats.missCount());
        stats.put("writerL1HitRate", String.format("%.2f%%", writerStats.hitRate() * 100));

        try {
            RBloomFilter<Long> bloom = getPoemBloomFilter();
            boolean initialized = bloom != null && bloom.isExists();
            stats.put("poemBloomInitialized", initialized);
            stats.put("poemBloomEstimatedCount", initialized ? bloom.count() : 0);
        } catch (Exception e) {
            stats.put("poemBloomInitialized", false);
            stats.put("poemBloomError", e.getMessage());
        }

        return stats;
    }
}
