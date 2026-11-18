package com.fuze.potryservice.service.impl;

import com.fuze.potry.entity.Allusion;
import com.fuze.potryservice.mapper.AllusionMapper;
import com.fuze.potryservice.service.AllusionService;
import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.Collections;
import java.util.List;
import java.util.concurrent.TimeUnit;

/**
 * 诗词文化典故服务实现类
 * 集成高性能 Caffeine 本地内存多级缓存（L1 级）
 */
@Service
@Slf4j
public class AllusionServiceImpl implements AllusionService {

    private static final String CACHE_KEY_ALL = "ALL_ACTIVE_ALLUSIONS";

    @Autowired
    private AllusionMapper allusionMapper;

    /**
     * L1: 全量典故列表本地缓存（容量 10，写入后 1 小时过期，开启统计）
     */
    private final Cache<String, List<Allusion>> listCache = Caffeine.newBuilder()
            .maximumSize(10)
            .expireAfterWrite(1, TimeUnit.HOURS)
            .recordStats()
            .build();

    /**
     * L1: 典故主键ID详情缓存（容量 500，写入后 1 小时过期）
     */
    private final Cache<Integer, Allusion> idCache = Caffeine.newBuilder()
            .maximumSize(500)
            .expireAfterWrite(1, TimeUnit.HOURS)
            .recordStats()
            .build();

    /**
     * L1: 典故名称详情缓存（容量 500，写入后 1 小时过期）
     */
    private final Cache<String, Allusion> nameCache = Caffeine.newBuilder()
            .maximumSize(500)
            .expireAfterWrite(1, TimeUnit.HOURS)
            .recordStats()
            .build();

    @Override
    public List<Allusion> getAllAllusions() {
        List<Allusion> cached = listCache.getIfPresent(CACHE_KEY_ALL);
        if (cached != null) {
            log.debug("Hit Caffeine L1 cache for allusion list, count: {}", cached.size());
            return cached;
        }

        log.info("Caffeine L1 miss for allusion list, querying DB");
        List<Allusion> list = allusionMapper.selectAllActive();
        if (list == null || list.isEmpty()) {
            list = allusionMapper.selectList(null);
        }

        if (list != null && !list.isEmpty()) {
            listCache.put(CACHE_KEY_ALL, list);
            // 预热 ID 与 Name 缓存
            for (Allusion allusion : list) {
                if (allusion.getId() != null) {
                    idCache.put(allusion.getId(), allusion);
                }
                if (allusion.getName() != null) {
                    nameCache.put(allusion.getName(), allusion);
                }
            }
            return list;
        }

        return Collections.emptyList();
    }

    @Override
    public Allusion getAllusionById(Integer id) {
        if (id == null) {
            return null;
        }

        Allusion cached = idCache.getIfPresent(id);
        if (cached != null) {
            log.debug("Hit Caffeine L1 cache for allusion id: {}", id);
            return cached;
        }

        log.info("Caffeine L1 miss for allusion id: {}, querying DB", id);
        Allusion allusion = allusionMapper.selectByIdDirect(id);
        if (allusion == null) {
            allusion = allusionMapper.selectById(id);
        }

        if (allusion != null) {
            idCache.put(id, allusion);
            if (allusion.getName() != null) {
                nameCache.put(allusion.getName(), allusion);
            }
        }

        return allusion;
    }

    @Override
    public Allusion getAllusionByName(String name) {
        if (name == null || name.trim().isEmpty()) {
            return null;
        }

        String trimmed = name.trim();
        Allusion cached = nameCache.getIfPresent(trimmed);
        if (cached != null) {
            log.debug("Hit Caffeine L1 cache for allusion name: {}", trimmed);
            return cached;
        }

        log.info("Caffeine L1 miss for allusion name: {}, querying DB", trimmed);
        Allusion allusion = allusionMapper.selectByName(trimmed);
        if (allusion != null) {
            nameCache.put(trimmed, allusion);
            if (allusion.getId() != null) {
                idCache.put(allusion.getId(), allusion);
            }
        }

        return allusion;
    }

    @Override
    public void clearCache() {
        log.info("Evicting all allusion Caffeine L1 caches");
        listCache.invalidateAll();
        idCache.invalidateAll();
        nameCache.invalidateAll();
    }
}
