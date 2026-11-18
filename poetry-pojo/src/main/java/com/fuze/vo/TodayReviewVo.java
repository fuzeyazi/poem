package com.fuze.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 今日应复习的诗(艾宾浩斯间隔重复调度)
 */
@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class TodayReviewVo {
    private Integer poemid;
    private String title;
    private String writer;
    private String content;
    private String dynasty;
    /** 已完成复习轮次(0=尚未复习过,4=只剩最后一轮) */
    private Integer reviewCount;
    /** 下次应复习时间(next<=now 即当前到期) */
    private LocalDateTime nextReviewDate;
    /** 轮次文案,如"第1轮·间隔3天" */
    private String dueStage;
}
