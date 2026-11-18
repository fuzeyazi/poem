package com.fuze.potryservice.service;

import com.fuze.potry.entity.Allusion;

import java.util.List;

/**
 * 诗词文化典故服务接口
 */
public interface AllusionService {

    /**
     * 获取全部已启用的典故列表（带 Caffeine 本地缓存）
     *
     * @return 典故列表
     */
    List<Allusion> getAllAllusions();

    /**
     * 根据主键ID获取典故详情（带 Caffeine 本地缓存）
     *
     * @param id 典故主键ID
     * @return 典故详情，不存在时返回 null
     */
    Allusion getAllusionById(Integer id);

    /**
     * 根据典故名称获取典故详情（带 Caffeine 本地缓存）
     *
     * @param name 典故名称（如：折柳）
     * @return 典故详情，不存在时返回 null
     */
    Allusion getAllusionByName(String name);

    /**
     * 清理所有本地 Caffeine 缓存
     */
    void clearCache();
}
