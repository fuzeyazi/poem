package com.fuze.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class UserBlogListVo {
    private String images;
    private String title;
    private Integer liked;
    private Integer conmments;
    private Integer blogid;
}
