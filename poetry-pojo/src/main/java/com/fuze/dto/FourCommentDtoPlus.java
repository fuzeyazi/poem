package com.fuze.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class FourCommentDtoPlus {
    private static final long serialVersionUID = 1L;
    private Integer blogId;
    private String context;
    private Integer parentId;
    private Integer userId;
}
