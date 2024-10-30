package com.fuze.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;


import java.util.Set;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class TypeDateVo {
    private int count;
    private Set<String> type;
}
