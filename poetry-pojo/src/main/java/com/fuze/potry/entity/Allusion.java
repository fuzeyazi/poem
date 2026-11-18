package com.fuze.potry.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 诗词文化典故实体
 */
@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class Allusion implements Serializable {
    private static final long serialVersionUID = 1L;

    /**
     * 主键ID
     */
    private Integer id;

    /**
     * 典故名称（如：折柳、豆蔻、尺素）
     */
    private String name;

    /**
     * 拼音注音（如：zhé liǔ）
     */
    private String pinyin;

    /**
     * 起源朝代（如：汉代、唐代、先秦）
     */
    private String dynasty;

    /**
     * 出处文献（如：《三辅黄图·卷六·桥》）
     */
    private String origin;

    /**
     * 最早出处原文引句
     */
    private String originQuote;

    /**
     * 典故背景故事及源流解析
     */
    private String story;

    /**
     * 后世延伸名句（多行或经典引用）
     */
    private String relatedQuotes;

    /**
     * 文化意象寓意（如：惜别怀远、青春芳华）
     */
    private String sentiment;

    /**
     * 状态：1 启用，0 停用
     */
    private Integer status;

    /**
     * 创建时间
     */
    private LocalDateTime createTime;

    /**
     * 更新时间
     */
    private LocalDateTime updateTime;
}
