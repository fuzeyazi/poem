package com.fuze.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class PoemLunTanCommentVo {
    //评论id
    private Integer id;
    //评论
    private String context;
    //
    private Integer blogid;
}
