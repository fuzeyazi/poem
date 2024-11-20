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
    private Integer blogId;
    private String context;
    private Integer parentId;
    private String tagerrName;
}
