package com.fuze.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class DefaultPoom {
    //主题
    private String theme;
    //古诗要求
    private String poemRequire;
    //四言诗：每句四个字，如《诗经》中的很多作品。
    //
    //五言诗：每句五个字，是最常见的古诗形式之一，如唐代的绝句和律诗。
    //
    //七言诗：每句七个字，也是常见的古诗形式，如唐代的七言绝句和七言律诗。
    //
    //杂言诗：不拘泥于固定的字数，句式长短不一，如李白的《将进酒》。
    //
    //绝句：通常指五言或七言的四句诗，分为五绝和七绝。
    //
    //律诗：通常指五言或七言的八句诗，分为五律和七律，对仗工整，平仄严格。
    //
    //排律：律诗的一种，句数超过八句，但仍然遵循律诗的规则。
    //
    //古风：不拘泥于格律，形式自由，如李白的《古风》系列。
    //
    //乐府诗：古代音乐机关“乐府”收集整理的诗歌，后来也指模仿这种风格的诗歌。
    //
    //歌行：一种较长的叙事诗，如白居易的《琵琶行》。
    //
    //赋：一种介于诗和散文之间的文学形式，如司马相如的《子虚赋》。
    //
    //词：一种配合音乐歌唱的诗歌形式，起源于唐，盛行于宋，如苏轼的《水调歌头》。
    //曲
    private String appearance;
    //风格
    private String style;
}
