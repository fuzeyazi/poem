package com.fuze.vo;

import io.swagger.annotations.ApiModelProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class PoemBlogVo {
    private static final long serialVersionUID = 1L;
    private Integer poemId;
    private Integer userId;
    private String title;
    private String images;
    private String content;
    private Integer liked;
    private Integer conmments;
    private LocalDateTime createTime;
    private String type;
    private String poemWord;
    //博客的id
     private Integer id;
    //用户
    private boolean isBlogLike;
    private String touxiang;
    private String username;
    private String nameTager;
    private Integer fans;

}
