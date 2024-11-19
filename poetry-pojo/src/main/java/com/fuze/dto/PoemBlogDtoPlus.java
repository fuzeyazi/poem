package com.fuze.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Builder
@Data
@AllArgsConstructor
@NoArgsConstructor
public class PoemBlogDtoPlus {
    private String title;
    private String images;
    private String content;
    private String type;
    private Integer poemid;
    private String poemword;
    private Integer bolgid;
    private Integer userid;

}
