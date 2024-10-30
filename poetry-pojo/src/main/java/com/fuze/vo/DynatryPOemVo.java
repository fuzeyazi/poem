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
public class DynatryPOemVo {
    private String dynasty;
    private Integer poemcount;
    private List<String>  titlepoem;
}
