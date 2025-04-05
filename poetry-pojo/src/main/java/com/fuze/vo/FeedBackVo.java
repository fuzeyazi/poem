package com.fuze.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class FeedBackVo {
    private static final long serialVersionUID = 1L;

    private Integer id;
    private Integer userid;
    private String messsage;
    private LocalDateTime createtime;
}
