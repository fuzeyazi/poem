package com.fuze.result;

import lombok.Data;

import java.util.List;

@Data
public class ScrollResult {
    private List<?> list;
    private Long offset;
    private Long minTime;
}
