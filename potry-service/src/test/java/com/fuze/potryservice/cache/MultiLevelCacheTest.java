package com.fuze.potryservice.cache;

import com.fuze.entity.Poem;
import com.fuze.entity.WriterEndVo;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.redisson.api.RBloomFilter;
import org.redisson.api.RedissonClient;
import org.springframework.data.redis.connection.DefaultMessage;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;
import org.springframework.test.util.ReflectionTestUtils;

import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class MultiLevelCacheTest {

    private MultiLevelCacheManager cacheManager;
    private StringRedisTemplate mockRedisTemplate;
    private ValueOperations<String, String> mockValueOps;
    private RedissonClient mockRedissonClient;
    @SuppressWarnings("unchecked")
    private RBloomFilter<Long> mockPoemBloomFilter = Mockito.mock(RBloomFilter.class);

    @BeforeEach
    @SuppressWarnings("unchecked")
    void setUp() {
        cacheManager = new MultiLevelCacheManager();
        mockRedisTemplate = Mockito.mock(StringRedisTemplate.class);
        mockValueOps = Mockito.mock(ValueOperations.class);
        mockRedissonClient = Mockito.mock(RedissonClient.class);

        when(mockRedisTemplate.opsForValue()).thenReturn(mockValueOps);
        doReturn(mockPoemBloomFilter).when(mockRedissonClient).getBloomFilter(anyString());

        ReflectionTestUtils.setField(cacheManager, "stringRedisTemplate", mockRedisTemplate);
        ReflectionTestUtils.setField(cacheManager, "redissonClient", mockRedissonClient);
    }

    @Test
    @DisplayName("测试 L1 本地 Caffeine 缓存命中与命中率指标统计")
    void testL1CaffeineHitAndStats() {
        // 布隆过滤器放行
        when(mockPoemBloomFilter.isExists()).thenReturn(true);
        when(mockPoemBloomFilter.contains(101L)).thenReturn(true);
        when(mockValueOps.get(anyString())).thenReturn(null);

        AtomicInteger dbHits = new AtomicInteger(0);
        Poem poemFixture = Poem.builder()
                .id("101")
                .title("静夜思")
                .writer("李白")
                .dynasty("唐")
                .content("床前明月光，疑是地上霜。举头望明月，低头思故乡。")
                .build();

        // 第一次读取：Miss L1、Miss L2 -> 回源 DB
        Poem firstRead = cacheManager.getPoem(101L, () -> {
            dbHits.incrementAndGet();
            return poemFixture;
        });

        assertNotNull(firstRead);
        assertEquals("静夜思", firstRead.getTitle());
        assertEquals(1, dbHits.get(), "首次查询必须回源 DB");

        // 第二次读取：必须命中 L1 Caffeine，不再回源 DB 且不访问 Redis
        Poem secondRead = cacheManager.getPoem(101L, () -> {
            dbHits.incrementAndGet();
            return poemFixture;
        });

        assertNotNull(secondRead);
        assertEquals(1, dbHits.get(), "第二次查询必须命中 L1 本地缓存，DB 回源次数保持为 1");

        // 校验监控指标
        Map<String, Object> stats = cacheManager.getCacheStats();
        assertTrue((Long) stats.get("poemL1HitCount") >= 1, "L1 命中计数必须大于等于 1");
        assertEquals(1L, stats.get("poemL1EstimatedSize"), "L1 缓存中应持有 1 条记录");
    }

    @Test
    @DisplayName("测试布隆过滤器拦截非法古诗 ID，0.1ms 内直接拦截不打 DB")
    void testBloomFilterInterceptsNonExistentId() {
        when(mockPoemBloomFilter.isExists()).thenReturn(true);
        // 模拟非法 ID：布隆过滤器判定不存在
        when(mockPoemBloomFilter.contains(999999L)).thenReturn(false);

        AtomicInteger dbHits = new AtomicInteger(0);
        Poem poem = cacheManager.getPoem(999999L, () -> {
            dbHits.incrementAndGet();
            return null;
        });

        assertNull(poem, "布隆过滤器判不存在的 ID 必须直接返回 null");
        assertEquals(0, dbHits.get(), "布隆拦截生效时绝不允许回源 DB");
        verify(mockValueOps, never()).get(anyString());
    }

    @Test
    @DisplayName("测试淘汰与本地协同失效：主动 evictPoem 后 L1 立即清退")
    void testLocalCacheEviction() {
        when(mockPoemBloomFilter.isExists()).thenReturn(false); // 跳过布隆直接测缓存
        when(mockValueOps.get(anyString())).thenReturn(null);

        AtomicInteger dbHits = new AtomicInteger(0);
        Poem fixture = Poem.builder().id("202").title("将进酒").writer("李白").build();

        // 1. 填入缓存
        cacheManager.getPoem(202L, () -> {
            dbHits.incrementAndGet();
            return fixture;
        });
        assertEquals(1, dbHits.get());

        // 2. 本地失效 (模拟收到 PubSub 广播或者自身更新)
        cacheManager.invalidateLocalPoem(202L);

        // 3. 再次读取应触发重新加载
        cacheManager.getPoem(202L, () -> {
            dbHits.incrementAndGet();
            return fixture;
        });
        assertEquals(2, dbHits.get(), "本地缓存失效后，再次查询应重新回源");
    }

    @Test
    @DisplayName("测试 Pub/Sub 广播监听器收到 POEM:xxx 消息后正确协同清空本地 L1")
    void testCacheEvictMessageListener() {
        CacheEvictMessageListener listener = new CacheEvictMessageListener();
        ReflectionTestUtils.setField(listener, "multiLevelCacheManager", cacheManager);

        Poem fixture = Poem.builder().id("303").title("春晓").writer("孟浩然").build();
        when(mockPoemBloomFilter.isExists()).thenReturn(false);

        // 写入缓存
        cacheManager.getPoem(303L, () -> fixture);
        assertEquals(1L, cacheManager.getCacheStats().get("poemL1EstimatedSize"));

        // 模拟收到 Redis Pub/Sub 广播: "POEM:303"
        DefaultMessage message = new DefaultMessage(
                MultiLevelCacheManager.CACHE_EVICT_TOPIC.getBytes(StandardCharsets.UTF_8),
                "POEM:303".getBytes(StandardCharsets.UTF_8)
        );
        listener.onMessage(message, null);

        // 验证 L1 对应 Key 已被协同逐出
        assertEquals(0L, cacheManager.getCacheStats().get("poemL1EstimatedSize"), "收到广播后对应 L1 缓存应被清除");
    }

    @Test
    @DisplayName("测试诗人名片多级缓存与监控指标获取")
    void testWriterMultiLevelCache() {
        AtomicInteger dbHits = new AtomicInteger(0);
        WriterEndVo writer = WriterEndVo.builder().id(1).name("苏轼").dynasty("宋").build();

        WriterEndVo r1 = cacheManager.getWriter(1, () -> {
            dbHits.incrementAndGet();
            return writer;
        });
        assertNotNull(r1);
        assertEquals(1, dbHits.get());

        // 命中 L1
        WriterEndVo r2 = cacheManager.getWriter(1, () -> {
            dbHits.incrementAndGet();
            return writer;
        });
        assertNotNull(r2);
        assertEquals(1, dbHits.get(), "第二次查询命中本地缓存，不触发 DB 访问");

        Map<String, Object> stats = cacheManager.getCacheStats();
        assertTrue((Long) stats.get("writerL1HitCount") >= 1);
    }
}
