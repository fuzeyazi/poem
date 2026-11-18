package com.fuze.potryservice.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.fuze.potry.entity.Allusion;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.io.Serializable;
import java.util.List;

/**
 * 诗词文化典故 Mapper 持久层
 */
@Mapper
public interface AllusionMapper extends BaseMapper<Allusion> {

    /**
     * 查询所有已启用的典故列表
     */
    @Select("SELECT id, name, pinyin, dynasty, origin, origin_quote AS originQuote, story, related_quotes AS relatedQuotes, sentiment, status, create_time AS createTime, update_time AS updateTime FROM poem_allusion WHERE status = 1 ORDER BY id ASC")
    List<Allusion> selectAllActive();

    /**
     * 根据主键ID精准查询
     */
    @Select("SELECT id, name, pinyin, dynasty, origin, origin_quote AS originQuote, story, related_quotes AS relatedQuotes, sentiment, status, create_time AS createTime, update_time AS updateTime FROM poem_allusion WHERE id = #{id}")
    Allusion selectByIdDirect(@Param("id") Integer id);

    /**
     * 根据主键查询（覆盖 BaseMapper，确保直接命中 poem_allusion）
     */
    @Override
    @Select("SELECT id, name, pinyin, dynasty, origin, origin_quote AS originQuote, story, related_quotes AS relatedQuotes, sentiment, status, create_time AS createTime, update_time AS updateTime FROM poem_allusion WHERE id = #{id}")
    Allusion selectById(Serializable id);

    /**
     * 根据典故名称精准查询
     */
    @Select("SELECT id, name, pinyin, dynasty, origin, origin_quote AS originQuote, story, related_quotes AS relatedQuotes, sentiment, status, create_time AS createTime, update_time AS updateTime FROM poem_allusion WHERE name = #{name} AND status = 1 LIMIT 1")
    Allusion selectByName(@Param("name") String name);
}
