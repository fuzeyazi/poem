package com.fuze.potryservice.controller.admin;

import com.fuze.potryservice.Aspect.AutoLog;
import com.fuze.potryservice.cache.CacheWarmUpRunner;
import com.fuze.potryservice.cache.MultiLevelCacheManager;
import com.fuze.result.Result;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/admin/cache")
@Slf4j
@Api(tags = "多级缓存管理与观测接口")
public class AdminCacheController {

    @Autowired
    private MultiLevelCacheManager multiLevelCacheManager;

    @Autowired
    private CacheWarmUpRunner cacheWarmUpRunner;

    @ApiOperation("手动触发布隆过滤器与缓存全量预热")
    @AutoLog("多级缓存全量预热")
    @PostMapping("/warmup")
    public Result<CacheWarmUpRunner.WarmUpResult> warmUp() {
        log.info("[Admin] 管理端触发多级缓存手动预热");
        CacheWarmUpRunner.WarmUpResult result = cacheWarmUpRunner.warmUpBloomFilters();
        return Result.success(result);
    }

    @ApiOperation("获取多级缓存实时性能指标 (L1 命中率、元素预估量、防穿透布隆过滤统计)")
    @GetMapping("/stats")
    public Result<Map<String, Object>> getStats() {
        return Result.success(multiLevelCacheManager.getCacheStats());
    }

    @ApiOperation("清空当前微服务节点本地 L1 Caffeine 缓存")
    @AutoLog("清空本地 L1 缓存")
    @PostMapping("/clear")
    public Result<String> clearLocalCache() {
        multiLevelCacheManager.clearAllLocalCache();
        return Result.success("本地 L1 缓存已成功清空");
    }
}
