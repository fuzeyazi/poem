package com.fuze.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class PoemDataVo {
    private Integer id;
    private String title;
    private String content;
    private String  writer;
    private String type;
    private String dynasty;
}
