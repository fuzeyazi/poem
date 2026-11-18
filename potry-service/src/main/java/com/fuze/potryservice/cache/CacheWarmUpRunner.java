package com.fuze.potryservice.cache;

import com.fuze.potryservice.mapper.PotryMapper;
import com.fuze.potryservice.mapper.WriterMapper;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.redisson.api.RBloomFilter;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.concurrent.CompletableFuture;

/**
 * 缓存预热组件
 * 1. 异步启动预热：Spring Boot 启动后，在独立后台线程扫描全量古诗与诗人 ID 注入 Redisson 分布式布隆过滤器；
 * 2. 运维手动预热：暴露给管理端 Controller，支持在测试/面试演练时按需触发全量重热。
 */
@Component
@Slf4j
public class CacheWarmUpRunner implements ApplicationRunner {

    @Autowired
    private MultiLevelCacheManager multiLevelCacheManager;

    @Autowired
    private PotryMapper potryMapper;

    @Autowired
    private WriterMapper writerMapper;

    @Override
    public void run(ApplicationArguments args) {
        // 异步后台线程执行，避免阻塞应用就绪
        CompletableFuture.runAsync(this::warmUpBloomFilters);
    }

    public synchronized WarmUpResult warmUpBloomFilters() {
        long start = System.currentTimeMillis();
        log.info("[MultiCache Warmup] 开始预热分布式布隆过滤器...");
        int poemCount = 0;
        int writerCount = 0;

        try {
            RBloomFilter<Long> poemBloom = multiLevelCacheManager.getPoemBloomFilter();
            if (poemBloom != null) {
                // 初始化容量 100,000，容错率 1%
                poemBloom.tryInit(100_000L, 0.01);
                List<Integer> poemIds = potryMapper.GetAllIds();
                if (poemIds != null && !poemIds.isEmpty()) {
                    for (Integer id : poemIds) {
                        if (id != null) {
                            poemBloom.add(id.longValue());
                            poemCount++;
                        }
                    }
                }
            }

            RBloomFilter<Integer> writerBloom = multiLevelCacheManager.getWriterBloomFilter();
            if (writerBloom != null) {
                // 初始化容量 10,000，容错率 1%
                writerBloom.tryInit(10_000L, 0.01);
                List<Integer> writerIds = writerMapper.selectAllWriterIds();
                if (writerIds != null && !writerIds.isEmpty()) {
                    for (Integer id : writerIds) {
                        if (id != null) {
                            writerBloom.add(id);
                            writerCount++;
                        }
                    }
                }
            }
            long duration = System.currentTimeMillis() - start;
            log.info("[MultiCache Warmup] 布隆过滤器全量预热完成: 古诗 ID {} 条, 诗人 ID {} 条, 耗时 {} ms",
                    poemCount, writerCount, duration);
            return new WarmUpResult(true, poemCount, writerCount, duration, "预热成功");
        } catch (Exception e) {
            long duration = System.currentTimeMillis() - start;
            log.warn("[MultiCache Warmup] 布隆过滤器预热异常(降级运行): {}", e.getMessage());
            return new WarmUpResult(false, poemCount, writerCount, duration, "预热异常: " + e.getMessage());
        }
    }

    @Data
    @AllArgsConstructor
    @NoArgsConstructor
    public static class WarmUpResult {
        private boolean success;
        private int poemCount;
        private int writerCount;
        private long durationMs;
        private String message;
    }
}
