package com.fuze.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class DynatryPoemResultVO {
    //一个朝代的诗的数量还有诗的名字
    private String dynasty;
    private Integer poemcount;
    private String titlepoem;
}
