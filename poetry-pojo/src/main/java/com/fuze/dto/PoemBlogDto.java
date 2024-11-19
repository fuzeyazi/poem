package com.fuze.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Builder
@Data
@AllArgsConstructor
@NoArgsConstructor
public class PoemBlogDto {
    private String title;
    private String images;
    private String content;
    private String type;
    private Integer poemId;
    private String poemWord;
}