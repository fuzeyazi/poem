package com.fuze.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class FourmCommentDto {
    private static final long serialVersionUID = 1L;
    private Integer blogId;
    private String context;
    private Integer parentId;
    private String tagerrName;
}
