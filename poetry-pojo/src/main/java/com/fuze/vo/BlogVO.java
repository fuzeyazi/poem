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
public class BlogVO {
    private Integer id;
    private String title;
    private Integer liked;
    private String content;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
    private String type;
}
