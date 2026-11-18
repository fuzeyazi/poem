package com.fuze.potryservice.config;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import java.util.Collections;
import java.util.List;
import java.util.concurrent.TimeUnit;
import java.util.function.Supplier;

/**
 * 通用 Redis 随机 id 池: SRANDMEMBER 抽样 + 主键 IN 回表, 替代 ORDER BY RAND() 的全表扫描+filesort;
 * 池空(首次访问/过期)时经 loader 回源装载全量 id, 池 1 小时过期自愈(后台增删数据后最多 1 小时同步);
 * Redis 异常时返回空列表, 由调用方降级回原 ORDER BY RAND() 查询
 */
@Component
@Slf4j
public class RandomIdPool {

    public static final String POTRY_POOL = "potry:idpool";
    public static final String RHESIS_POOL = "rhesis:idpool";
    public static final String WRITER_POOL = "writer:idpool";
    public static final String BLOG_POOL = "luntan:blog:idpool";

    private static final long POOL_TTL_HOURS = 1;

    @Autowired
    private StringRedisTemplate stringRedisTemplate;

    public List<Integer> randomIds(String poolKey, int n, Supplier<List<Integer>> loader) {
        try {
            List<String> ids = stringRedisTemplate.opsForSet().randomMembers(poolKey, n);
            if (ids == null || ids.isEmpty()) {
                List<Integer> all = loader.get();
                if (all == null || all.isEmpty()) {
                    return Collections.emptyList();
                }
                stringRedisTemplate.opsForSet().add(poolKey,
                        all.stream().map(String::valueOf).toArray(String[]::new));
                stringRedisTemplate.expire(poolKey, POOL_TTL_HOURS, TimeUnit.HOURS);
                ids = stringRedisTemplate.opsForSet().randomMembers(poolKey, n);
            }
            return ids.stream().map(Integer::valueOf).toList();
        } catch (Exception e) {
            log.warn("随机id池[{}]异常,调用方将降级回ORDER BY RAND()", poolKey, e);
            return Collections.emptyList();
        }
    }
}
