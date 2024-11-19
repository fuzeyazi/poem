package com.fuze.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Builder
@Data
@AllArgsConstructor
@NoArgsConstructor
public class PoemBlogDtoSuper {
     private String title;
    private String images;
    private String content;
    private String type;
    private Integer poemId;
    private String poemWord;
    private Integer liked;
    private Integer conmments;
    private LocalDateTime createTime;
    private Integer userId;

}
